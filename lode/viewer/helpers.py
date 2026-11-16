"""Stateless helpers shared by the viewers.

Nothing here needs a Reader or a model instance: serialization formats, the
deterministic order of the header metadata, label cleaning, URL heuristics and
the loader of the per-format YAML configuration.
"""
import re
from pathlib import Path
from typing import Dict, Optional, Tuple

import yaml

_CONFIG_DIR = Path(__file__).parent / "config"

# ==========================================================================
# 1. SERIALIZATION
# ==========================================================================
# The format lists live in lode.helpers.formats: the builder and the API need
# them too and must not import a viewer for a constant.

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


# ==========================================================================
# 4. PER-FORMAT VIEWER CONFIGURATION
# ==========================================================================

_REQUIRED_CONFIG_KEYS = ("type_map", "toc")


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
