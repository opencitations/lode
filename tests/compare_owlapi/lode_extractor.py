"""Extract per-type IRI sets from a populated LODE OwlLogic instance."""
from typing import Dict, Set

from rdflib import URIRef
from lode.models import (
    Concept, Relation, Attribute, Annotation, Individual, Datatype,
)
from .mapping import LODE_TO_ROBOT_TYPE, LODE_NON_ENTITY_CLASSES


def extract_entity_iris(logic) -> Dict[str, Set[str]]:
    """Walk logic._instance_cache, return {robot_type_label -> set of IRI strings}.

    Uses type(inst) is cls (exact-class), not isinstance, to respect LODE's
    granular hierarchy (e.g. Annotation should not collapse into Property).
    Only URIRef-keyed instances are reported (BNode entities have no OWLAPI
    counterpart at entity level).
    """
    out: Dict[str, Set[str]] = {label: set() for label in LODE_TO_ROBOT_TYPE.values()}

    for uri, instances in logic._instance_cache.items():
        if not isinstance(uri, URIRef):
            continue
        for inst in instances:
            cls = type(inst)
            label = LODE_TO_ROBOT_TYPE.get(cls)
            if label is not None:
                out[label].add(str(uri))
    return out


def extract_lode_class_counts(logic) -> Dict[str, int]:
    """Full LODE inventory including non-entity classes, for the report's
    'unmapped' section. Counts unique URI/BNode keys per exact class.
    """
    counts: Dict[str, int] = {}
    for instances in logic._instance_cache.values():
        for inst in instances:
            name = type(inst).__name__
            counts[name] = counts.get(name, 0) + 1
    return counts


def extract_unmapped_classes(logic) -> Dict[str, int]:
    """Subset of class counts for LODE classes with no OWLAPI entity counterpart.
    Useful to surface LODE-specific richness (Restriction, OneOf, ...).
    """
    full = extract_lode_class_counts(logic)
    return {k: v for k, v in full.items() if k in LODE_NON_ENTITY_CLASSES}
