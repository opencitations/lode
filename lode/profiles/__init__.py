"""Profile registry: the single place where an artefact format is wired.

A profile is a package (lode/profiles/<name>/) holding everything one format needs: its
reader mapper (reader.yaml), its viewer config (viewer.yaml), optional templates, and the
logic and viewer classes. Its __init__ registers a Profile. Classes are given as
"module:Name" strings and resolved on use, so this module imports neither the reader nor
the viewers and every layer can read it.
"""

import logging
from dataclasses import dataclass
from importlib import import_module
from importlib.metadata import entry_points
from pathlib import Path
from typing import Any, Dict, List, Optional

from lode.exceptions import ArtefactValidationError

logger = logging.getLogger(__name__)

# ==========================================================================
# 1. PROFILE
# ==========================================================================

@dataclass(frozen=True)
class Profile:
    """Everything LODE needs to read and show one artefact format.

    `package` is the profile's own package: reader.yaml, viewer.yaml and templates/ live
    there. `logic`, `viewer` and `artefact` are "module:Name" paths to the logic class, the
    viewer class and the Artefact subclass of the format; `post_checks` is an optional path
    to a function that takes the logic after extraction. A module that starts with a dot is
    relative to `package` (".logic:OwlLogic"), so a profile never repeats its own package
    name. `enabled` gates the format where it is named by a string (lode.read, hence the
    API and the CLI).
    """

    name: str
    package: str
    logic: str
    viewer: str
    artefact: str
    post_checks: Optional[str] = None
    enabled: bool = True

    def path(self) -> Path:
        """Return the folder of the profile's package.

        Taken from the module file, like the other data folders, so it also works when
        the package is installed from the wheel.
        """
        return Path(import_module(self.package).__file__).parent

    def artefact_class(self) -> type:
        """Return the Artefact subclass of this format, imported on use."""
        return resolve(self.artefact, self.package)

    def make_logic(self, graph: Any, cache: dict, configuration: Any) -> Any:
        """Build the logic of this format on `graph`, filling `cache`.

        The class is imported now and not at registration, so this module stays free of
        reader imports; the reader asks the profile and never resolves the path itself.
        """
        return resolve(self.logic, self.package)(graph, cache, configuration)

    def make_viewer(self, artefact: Any) -> Any:
        """Build the viewer of this format for `artefact` (imported on use, like the logic)."""
        return resolve(self.viewer, self.package)(artefact)

    def run_post_checks(self, logic: Any) -> None:
        """Run the post-extraction checks of this format on `logic`; no-op without any."""
        if self.post_checks:
            resolve(self.post_checks, self.package)(logic)


# ==========================================================================
# 2. REGISTRY
# ==========================================================================

_PROFILES: Dict[str, Profile] = {}

# Imported on first use, by name: the engine must not import a profile package, and the
# import registers it. Third-party profiles join them through the entry point group below.
_BUILTIN = ("lode.profiles.owl", "lode.profiles.skos")
_ENTRY_POINT_GROUP = "lode.profiles"
_loaded = False

def _ensure_loaded() -> None:
    """Register the built-in profiles and the plugins, once.

    Built-ins first, so a plugin can never take the name of a format LODE ships.
    """
    global _loaded
    if _loaded:
        return
    _loaded = True  # set first: a profile's __init__ imports this module again
    for module in _BUILTIN:
        import_module(module)
    for entry_point in entry_points(group=_ENTRY_POINT_GROUP):
        _register_plugin(entry_point)


def _register_plugin(entry_point) -> None:
    """Load the Profile an entry point names and register it.

    A broken plugin must not take LODE down, so a failure is logged with the plugin's
    name (the traceback stays in the server log) and the plugin is skipped. A plugin
    that reuses the name of a registered profile is refused for the same reason.
    """
    try:
        profile = entry_point.load()
    except Exception:
        logger.warning("Profile plugin '%s' failed to load", entry_point.name, exc_info=True)
        return
    if not isinstance(profile, Profile):
        logger.warning("Profile plugin '%s' is not a Profile, skipped", entry_point.name)
    elif profile.name in _PROFILES:
        logger.warning("Profile plugin '%s' redefines '%s', skipped", entry_point.name, profile.name)
    else:
        register(profile)

def register(profile: Profile) -> None:
    """Add a profile to the registry, replacing any profile with the same name."""
    _PROFILES[profile.name] = profile


def find(name: Optional[str]) -> Optional[Profile]:
    """Return the profile called `name`, ignoring case, or None when there is none.

    The only place where a format name is normalised: the reader, the viewer and the
    artefact all ask here, so 'OWL' and 'owl' can never be treated differently.
    """
    _ensure_loaded()
    return _PROFILES.get((name or "").lower())


def get(name: str) -> Profile:
    """Return the profile called `name`; raise ValueError listing the available ones."""
    profile = find(name)
    if profile is None:
        raise ValueError(f"Unknown configuration: '{name}'. Available: {', '.join(names())}")
    return profile


def get_enabled(name: Optional[str]) -> Profile:
    """Return the enabled profile called `name`, ignoring case.

    The gate of every caller that names a format with a string (lode.read, hence the API
    and the CLI). An unknown name and a disabled one get the same error, with the list of
    valid formats. Asked every time, not cached, because plugins register on first use.
    """
    profile = find(name)
    if profile is None or not profile.enabled:
        raise ArtefactValidationError(
            f"Format '{name}' is not available",
            context={"requested": name, "supported": names(enabled_only=True)},
        )
    return profile


def _artefact_classes() -> List[tuple]:
    """Return (profile, Artefact class) for every profile whose class can be imported.

    A plugin whose class cannot be imported is logged and skipped: it must not stop the
    others from reading.
    """
    found = []
    for profile in _PROFILES.values():
        try:
            found.append((profile, profile.artefact_class()))
        except (ImportError, AttributeError):
            logger.warning("Profile '%s': artefact class '%s' cannot be imported",
                           profile.name, profile.artefact, exc_info=True)
    return found


def of(cls: type) -> Optional[Profile]:
    """Return the profile whose Artefact subclass is `cls` or one of its bases, or None.

    Walks the MRO, so a user's subclass of OwlOntology is still read as OWL. Built-ins are
    registered first, so they win when a plugin points to the same class.
    """
    _ensure_loaded()
    classes = _artefact_classes()
    for klass in cls.__mro__:
        for profile, artefact in classes:
            if artefact is klass:
                return profile
    return None


def artefact_class_named(name: str) -> Optional[type]:
    """Return the Artefact subclass called `name` among the registered profiles, or None.

    Backs `from lode import OwlOntology`: the package root imports no profile, it asks here
    on first use, and the classes of plugins are found too. Disabled profiles are included:
    `enabled` gates the formats named by a string, not the classes a program imports.
    """
    _ensure_loaded()
    for _, artefact in _artefact_classes():
        if artefact.__name__ == name:
            return artefact
    return None


def names(enabled_only: bool = False) -> List[str]:
    """Return the sorted profile names, optionally only the enabled ones."""
    _ensure_loaded()
    return sorted(p.name for p in _PROFILES.values() if p.enabled or not enabled_only)


def resolve(path: str, package: Optional[str] = None) -> Any:
    """Import and return the object a "module:Name" path points to.

    A module that starts with a dot is relative to `package`; without a package a relative
    path raises TypeError, so a typo fails loudly. Done at call time, not at registration,
    to keep this module free of reader and viewer imports (and of circular imports).
    """
    module, _, attr = path.partition(":")
    return getattr(import_module(module, package), attr)
