"""Stateless helpers shared by the viewers.

Nothing here needs a Reader or a model instance: serialization formats, the
deterministic order of the header metadata, label cleaning, URL heuristics and
the loader of the per-format YAML configuration.
"""
import re
import urllib.parse
from pathlib import Path
from typing import Dict, Optional, Tuple

import yaml

_CONFIG_DIR = Path(__file__).parent / "config"

# ==========================================================================
# 1. SERIALIZATION FORMATS
# ==========================================================================

# Export formats: triples of the loaded artefact only.
SERIALIZATION_FORMATS = [
    {"label": "Turtle",   "fmt": "turtle",  "mime": "text/turtle",           "ext": "ttl",    "icon": "bi-filetype-raw"},
    {"label": "RDF/XML",   "fmt": "xml",     "mime": "application/rdf+xml",   "ext": "rdf",    "icon": "bi-file-code"},
    {"label": "JSON-LD",   "fmt": "json-ld", "mime": "application/ld+json",   "ext": "jsonld", "icon": "bi-filetype-json"},
    {"label": "N-Triples", "fmt": "nt",      "mime": "application/n-triples", "ext": "nt",     "icon": "bi-file-text"},
]

# Provenance formats: quads, the named graph of each triple is always shown.
QUAD_SERIALIZATION_FORMATS = [
    {"label": "TriG",      "fmt": "trig",    "mime": "application/trig",      "ext": "trig",   "icon": "bi-filetype-raw"},
    {"label": "JSON-LD",   "fmt": "json-ld", "mime": "application/ld+json",   "ext": "jsonld", "icon": "bi-filetype-json"},
    {"label": "N-Quads",   "fmt": "nquads",  "mime": "application/n-quads",   "ext": "nq",     "icon": "bi-file-text"},
]


def safe_serialize(g, fmt: str) -> str:
    """Serialize a graph, returning a comment with the error instead of raising.

    One format that fails must not break the page that shows all of them.
    """
    try:
        return g.serialize(format=fmt)
    except Exception as e:
        return f"# serialization error ({fmt}): {e}"


# ==========================================================================
# 2. HEADER METADATA ORDER
# ==========================================================================

_ANNOTATION_ORDER_FILE = _CONFIG_DIR / "model_annotations_deterministic_sorting.yaml"


def _normalize_annotation_key(key: str) -> str:
    """Reduce a displayed metadata key to a comparable form.

    Case, spaces, underscores and hyphens are dropped so that 'version info',
    'versionInfo' and 'version_info' land in the same slot of the order list.
    """
    return re.sub(r"[\s_\-]+", "", key.lower())


def _load_annotation_order() -> Dict[str, int]:
    """Read the YAML order list and map each normalized key to its rank.

    Loaded once at import time. A missing or malformed file raises: a silent
    fallback would make the page order depend on the environment again.
    """
    with open(_ANNOTATION_ORDER_FILE, encoding="utf-8") as f:
        order = yaml.safe_load(f)["order"]
    return {_normalize_annotation_key(k): i for i, k in enumerate(order)}


_ANNOTATION_RANK = _load_annotation_order()


def annotation_sort_key(key: str) -> Tuple[int, str]:
    """Sort key for a header metadata entry: configured rank, then alphabetical.

    Unlisted keys get a rank past the last listed one, so they follow the known
    ones and stay in alphabetical order among themselves.
    """
    return (_ANNOTATION_RANK.get(_normalize_annotation_key(key), len(_ANNOTATION_RANK)), key.lower())


# ==========================================================================
# 3. LABELS AND URLS
# ==========================================================================

def clean_name(name: str, vocabulary: Optional[Dict[str, str]] = None) -> str:
    """Turn an attribute or getter name into a display label.

    Drops the has_/get_ prefix, splits camelCase, replaces underscores with
    spaces and lowercases. The vocabulary of the viewer (internal word -> shown
    word) is applied last, on whole words only, so that e.g. "concept" does not
    touch "conceptual".
    """
    if not name:
        return ""

    name = re.sub(r'^(get_has_|get_|has_)', '', name)
    # Put space between camelCase letters
    name = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', name)
    name = name.replace('_', ' ')

    # Strip extra spaces and lowercase everything
    name = ' '.join(name.split()).lower()

    for word, shown in (vocabulary or {}).items():
        name = re.sub(rf'\b{re.escape(word)}\b', shown, name)

    return name


def is_likely_ontology(url: str) -> bool:
    """Determines if a URL likely points to an ontology based on naming patterns."""
    if not url or not isinstance(url, str) or not url.startswith('http'):
        return False

    # 1. Clean the string
    clean_url = url.strip().lower()

    # 2. Safely parse the URL to ignore fragments (#) and queries (?) for extension checking
    parsed = urllib.parse.urlparse(clean_url)
    path = parsed.path.rstrip('/')

    # 3. Standard Ontology File Extensions
    ontology_exts = ['.owl', '.rdf', '.ttl', '.nt', '.n3', '.jsonld']
    if any(path.endswith(ext) for ext in ontology_exts):
        return True

    # Match registries against the parsed hostname, not the raw string:
    # a substring check would also match e.g. https://evil.com/w3id.org/x
    host = parsed.hostname or ''

    def _host_is(domain: str) -> bool:
        """True if the URL host is the domain or one of its subdomains."""
        return host == domain or host.endswith('.' + domain)

    # 4. Common Ontology Registries & Permanent URLs
    ontology_domains = [
        'w3id.org',
        'purl.org',
        'xmlns.com'  # Often used for FOAF
    ]
    if any(_host_is(domain) for domain in ontology_domains):
        return True

    # 5. Core W3C Namespaces
    w3c_core = ['/1999/02/22-rdf-syntax-ns', '/2000/01/rdf-schema', '/2002/07/owl']
    if _host_is('w3.org') and any(ns in path for ns in w3c_core):
        return True

    # 6. Broad Keywords & Famous Standard Acronyms
    # Looking for these anywhere in the URL string
    path_keywords = [
        'ontology', 'vocab', 'schema', # General terms
        'skos', 'foaf', 'crm', 'cidoc' # Famous standards
    ]
    if any(keyword in clean_url for keyword in path_keywords):
        return True

    return False


# ==========================================================================
# 4. PER-FORMAT VIEWER CONFIGURATION
# ==========================================================================

_REQUIRED_CONFIG_KEYS = ("type_map", "toc", "card")


def load_viewer_config(name: str) -> dict:
    """Read config/<name>_viewer.yaml and fill in the optional keys.

    The file holds everything that differs between formats (display names, table
    of contents, hierarchy getters, card template, display vocabulary), so the
    viewer classes carry no per-format data. A missing file or required key
    raises: a silent default would change the page without any trace.
    """
    path = _CONFIG_DIR / f"{name}_viewer.yaml"
    with open(path, encoding="utf-8") as f:
        config = yaml.safe_load(f)
    missing = [k for k in _REQUIRED_CONFIG_KEYS if k not in config]
    if missing:
        raise ValueError(f"{path.name}: missing required keys {missing}")
    config.setdefault("vocabulary", {})
    config.setdefault("hierarchy", {})
    config.setdefault("characteristics", [])
    return config
