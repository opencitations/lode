"""Profile registry: the single place where an artefact format is wired.

A profile ties a format name to its reader logic, its viewer and its post-pipeline
checks. Classes are given as "module:Name" strings and resolved on use, so this
module imports neither the reader nor the viewers and every layer can read it.
"""
from dataclasses import dataclass
from importlib import import_module
from typing import Any, Dict, List, Optional


# ==========================================================================
# 1. PROFILE
# ==========================================================================

@dataclass(frozen=True)
class Profile:
    """Everything LODE needs to read and show one artefact format.

    `logic` and `viewer` are "module:Name" paths, `post_checks` an optional path to a
    function that takes the logic after extraction. The YAML mappers are found by
    `name` (reader/config/<name>.yaml, viewer/config/<name>_viewer.yaml).
    `enabled` gates the format in the API and the CLI.
    """

    name: str
    logic: str
    viewer: str
    post_checks: Optional[str] = None
    enabled: bool = True


# ==========================================================================
# 2. REGISTRY
# ==========================================================================

PROFILES: Dict[str, Profile] = {}


def register(profile: Profile) -> None:
    """Add a profile to the registry, replacing any profile with the same name."""
    PROFILES[profile.name] = profile


def get(name: str) -> Profile:
    """Return the profile called `name`; raise ValueError listing the available ones."""
    try:
        return PROFILES[name]
    except KeyError:
        raise ValueError(
            f"Unknown configuration: '{name}'. Available: {', '.join(sorted(PROFILES))}"
        ) from None


def names(enabled_only: bool = False) -> List[str]:
    """Return the sorted profile names, optionally only the enabled ones."""
    return sorted(p.name for p in PROFILES.values() if p.enabled or not enabled_only)


def resolve(path: str) -> Any:
    """Import and return the object a "module:Name" path points to.

    Done at call time, not at registration, to keep this module free of reader and
    viewer imports (and of circular imports).
    """
    module, _, attr = path.partition(":")
    return getattr(import_module(module), attr)


# ==========================================================================
# 3. BUILT-IN PROFILES
# ==========================================================================

# Every format keeps the OWL post-checks: this is what the reader did before profiles
# existed. Narrow them per format in a later step, with the SPAR tests as safety net.
_POST_CHECKS = "lode.reader.warnings.owl_warnings:run_post_checks"

register(Profile("owl", "lode.reader.logic:OwlLogic",
                 "lode.viewer.owl_viewer:OwlViewer", _POST_CHECKS))
register(Profile("skos", "lode.reader.logic:SkosLogic",
                 "lode.viewer.skos_viewer:SkosViewer", _POST_CHECKS))
