# lode/helpers/formats.py
"""Semantic artefact format registry.

Single source of truth for which formats exist and which are enabled.
Imported by both api.py and cli.py so the gate is enforced identically
in both entry points.
"""
from enum import Enum
from lode.exceptions import ArtefactValidationError


# Format name -> logic class name in lode.reader.logic. Plain strings on purpose: this
# module must not import the reader or the viewers, so every layer can read it.
# A new format is one line here, plus its YAML mapper and its logic class.
CONFIGURATION_REGISTRY = {
    'owl': 'OwlLogic',
    'rdf': 'RdfLogic',
    'skos': 'SkosLogic',
}

# Formats enabled in this release. Add a value here when the reader
# and viewer for that format are stable and tested.
ENABLED_FORMATS = {"owl", "skos"}

class ReadAsFormat(str, Enum):
    """Semantic artefact type. Note: currently only `owl` is enabled."""
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