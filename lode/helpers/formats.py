# lode/helpers/formats.py
"""The export formats shared by every layer.

The artefact formats live in the profile registry (lode.profiles), which also gates them:
see lode.profiles.get_enabled.
"""

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