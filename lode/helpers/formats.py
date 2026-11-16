# lode/helpers/formats.py
"""Semantic artefact formats and the export formats shared by every layer.

The artefact formats (ReadAsFormat) and the enabled ones (ENABLED_FORMATS) are derived
from the profile registry in lode.profiles, where a format is declared. Imported by both
api.py and cli.py so the gate is enforced identically in both entry points.
"""
from enum import Enum
from lode import profiles
from lode.exceptions import ArtefactValidationError


# Both values derive from the profile registry (lode.profiles), the one place where a
# format is declared. `enabled` there decides what the API and the CLI accept.
ENABLED_FORMATS = set(profiles.names(enabled_only=True))

class ReadAsFormat(str, Enum):
    """Semantic artefact type: one member per registered profile.

    Written out as a class, not built from the registry, so type checkers and the
    OpenAPI schema see real members. tests/test_formats_registry.py fails when it
    drifts from lode.profiles.
    """
    owl = "owl"
    rdf = "rdf"
    skos = "skos"



# Export formats: triples of the loaded artefact only. Shared by the viewers,
# the static builder and the API, so they live here and not in a viewer.
SERIALIZATION_FORMATS = [
    {"label": "Turtle",   "fmt": "turtle",  "mime": "text/turtle",           "ext": "ttl",    "icon": "bi-filetype-raw"},
    {"label": "RDF/XML",   "fmt": "xml",     "mime": "application/rdf+xml",   "ext": "xml",    "icon": "bi-file-code"},
    {"label": "JSON-LD",   "fmt": "json-ld", "mime": "application/ld+json",   "ext": "jsonld", "icon": "bi-filetype-json"},
    {"label": "N-Triples", "fmt": "nt",      "mime": "application/n-triples", "ext": "nt",     "icon": "bi-file-text"},
]

# Provenance formats: quads, the named graph of each triple is always shown.
QUAD_SERIALIZATION_FORMATS = [
    {"label": "TriG",      "fmt": "trig",    "mime": "application/trig",      "ext": "trig",   "icon": "bi-filetype-raw"},
    {"label": "JSON-LD",   "fmt": "json-ld", "mime": "application/ld+json",   "ext": "jsonld", "icon": "bi-filetype-json"},
    {"label": "N-Quads",   "fmt": "nquads",  "mime": "application/n-quads",   "ext": "nq",     "icon": "bi-file-text"},
]


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

