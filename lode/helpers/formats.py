# lode/helpers/formats.py
"""Semantic artefact formats and the export formats shared by every layer.

The artefact formats are derived from the profile registry in lode.profiles, 
where a format is declared. Imported by both api.py and cli.py so 
the gate is enforced identically in both entry points.
"""
from lode import profiles
from lode.exceptions import ArtefactValidationError

def check_format_enabled(read_as: str) -> None:
    """Raise ArtefactValidationError unless `read_as` names an enabled profile.

    The single gate of the CLI and the API. Asked every time, not cached, because plugins
    register on first use. An unknown name and a disabled one get the same error, with the
    list of valid formats.
    """
    enabled = profiles.names(enabled_only=True)
    if read_as not in enabled:
        raise ArtefactValidationError(
            f"Format '{read_as}' is not available",
            context={"requested": read_as, "supported": enabled},
        )

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