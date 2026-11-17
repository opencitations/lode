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

logger = logging.getLogger(__name__)

# ==========================================================================
# 1. PROFILE
# ==========================================================================

@dataclass(frozen=True)
class Profile:
    """Everything LODE needs to read and show one artefact format.

    `package` is the profile's own package: reader.yaml, viewer.yaml and templates/ live
    there. `logic` and `viewer` are "module:Name" paths, `post_checks` an optional path to
    a function that takes the logic after extraction. `enabled` gates the format in the
    API and the CLI.
    """

    name: str
    package: str
    logic: str
    viewer: str
    post_checks: Optional[str] = None
    enabled: bool = True

    def path(self) -> Path:
        """Return the folder of the profile's package.

        Taken from the module file, like the other data folders, so it also works when
        the package is installed from the wheel.
        """
        return Path(import_module(self.package).__file__).parent


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


def names(enabled_only: bool = False) -> List[str]:
    """Return the sorted profile names, optionally only the enabled ones."""
    _ensure_loaded()
    return sorted(p.name for p in _PROFILES.values() if p.enabled or not enabled_only)


def resolve(path: str) -> Any:
    """Import and return the object a "module:Name" path points to.

    Done at call time, not at registration, to keep this module free of reader and
    viewer imports (and of circular imports).
    """
    module, _, attr = path.partition(":")
    return getattr(import_module(module), attr)
