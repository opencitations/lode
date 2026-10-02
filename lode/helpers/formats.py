# lode/helpers/formats.py
"""Semantic artefact format registry.

Single source of truth for which formats exist and which are enabled.
Imported by both api.py and cli.py so the gate is enforced identically
in both entry points.
"""
from enum import Enum
from lode.exceptions import ArtefactValidationError

# Formats enabled in this release. Add a value here when the reader
# and viewer for that format are stable and tested.
ENABLED_FORMATS = {"owl"}


class ReadAsFormat(str, Enum):
    """Semantic artefact type. Note: currently only `owl` is enabled."""
    owl = "owl"
    rdf = "rdf"
    skos = "skos"


def check_format_enabled(read_as: "ReadAsFormat") -> None:
    """Raise ArtefactValidationError if the format is not yet available."""
    if read_as.value not in ENABLED_FORMATS:
        raise ArtefactValidationError(
            f"Format '{read_as.value}' is not available yet",
            context={
                "requested": read_as.value,
                "supported": sorted(ENABLED_FORMATS),
            },
        )