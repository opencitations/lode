# owl_warnings.py
"""OWL warning checks. All functions take `logic` as first arg and push via logic.add_warning()."""

from rdflib import URIRef, BNode
from rdflib.namespace import OWL
from lode.models import (
    Concept, Datatype, DatatypeRestriction,
    Relation, Attribute, Annotation,
    TruthFunction, PropertyConceptRestriction,
)


# for integrity tests
def has_warning(logic, code: str, subject=None) -> bool:
    """Check if a warning with given code (and optional subject) was raised."""
    for w in logic._warnings:
        if w['code'] != code:
            continue
        if subject is None or w['subject'] == str(subject):
            return True
    return False

# ====================================================================
# PIPELINE-TIME (called inline from owl_logic during specific phases)
# ====================================================================

def flag_malformed_restrictions(logic, classified):
    axiom_preds = {
        p for p, cfg in logic._property_mapping.items()
        if isinstance(cfg.get('inferred_class'), type)
        and issubclass(cfg['inferred_class'], PropertyConceptRestriction)
    }
    by_parent = {}  # parent_uri -> set of axiom predicates seen
    for bnode in classified:
        axioms = set(logic.graph.predicates(subject=bnode)) & axiom_preds
        if len(axioms) <= 1:
            continue
        parents = sorted({
            str(s) for s in logic.graph.subjects(object=bnode)
            if isinstance(s, URIRef)
        })
        parent_key = parents[0] if parents else '<anonymous>'
        by_parent.setdefault(parent_key, set()).update(axioms)

    for parent, axioms in by_parent.items():
        names = sorted(p.n3(logic.graph.namespace_manager) for p in axioms)
        logic.add_warning('malformed_restriction', parent,
            f"OWL 2 DL: malformed restrictions on {parent} ({', '.join(names)})")

def empty_truth_function(logic, instance, bnode, operator):
    ident = instance.get_has_identifier()
    logic.add_warning('empty_truth_function', ident,
        f'§8.1.1: Truth Function ({ident}, {operator}) is empty — ignored (collection BNode: {bnode})')

def singleton_truth_function(logic, instance, bnode, operator):
    ident = instance.get_has_identifier()
    logic.add_warning('singleton_truth_function', ident,
        f'§8.1.1: TruthFunction ({ident}, {operator}) has a single element — ontology should be checked (collection BNode: {bnode})')


# ====================================================================
# POST-PIPELINE (single entry point)
# ====================================================================

def run_post_checks(logic):
    """Single sweep over cache + config-driven sweep."""
    for uri, instances in list(logic._instance_cache.items()):
        for instance in list(instances):
            _check_orphan_restriction(logic, instance, uri)
            _check_inverse_multiplicity(logic, instance, uri)
            # _check_self_inverse(logic, instance, uri)
            _check_empty_truth_function_post(logic, instance, uri)
            _check_property_hierarchy(logic, instance, uri)
            _check_class_datatype_hierarchy(logic, instance, uri)
        if isinstance(uri, URIRef):
            _check_punning_conflicts(logic, uri, instances)
    _check_config_mismatches(logic)


def _check_orphan_restriction(logic, instance, uri):
    if not isinstance(instance, PropertyConceptRestriction):
        return
    if instance.get_applies_on_property() is not None:
        return
    if isinstance(uri, BNode) and (uri, OWL.onProperty, None) not in logic.graph:
        logic.add_warning('orphan_restriction', uri,
            f'Orphan {type(instance).__name__}: no owl:onProperty in graph, removed')
        logic._instance_cache[uri].discard(instance)
    else:
        logic.add_warning('missing_on_property', uri,
            f'{type(instance).__name__} has owl:onProperty but applies_on_property is None')

def _check_inverse_multiplicity(logic, instance, uri):
    if not isinstance(instance, Relation):
        return
    inv = instance.get_is_inverse_of()
    if isinstance(inv, list) and len(inv) > 1:
        ids = ', '.join(i.get_has_identifier() for i in inv)
        logic.add_warning('multiple_inverse_of', uri,
            f'§9.2.4: Relation {uri} has {len(inv)} owl:inverseOf declarations ({ids})')

# def _check_self_inverse(logic, instance, uri):
#     if not isinstance(instance, Relation):
#         return
#     inv = instance.get_is_inverse_of()
#     candidates = inv if isinstance(inv, list) else ([inv] if inv else [])
#     if any(c is instance for c in candidates):
#         logic.add_warning('self_inverse', uri,
#             f'§6.1.1: Relation {uri} is inverse of itself')

def _check_empty_truth_function_post(logic, instance, uri):
    if isinstance(instance, TruthFunction) and len(instance.get_applies_on_concept()) == 0:
        logic.add_warning('empty_restriction', uri,
            f'{type(instance).__name__} has empty applies_on_concept')

def _check_property_hierarchy(logic, instance, uri):
    if not isinstance(instance, (Relation, Attribute, Annotation)):
        return
    for sup in (instance.get_is_sub_property_of() or []):
        if sup is not None and not isinstance(sup, type(instance)):
            logic.add_warning('property_type_mismatch_hierarchy', uri,
                f'§5.8.1: {type(instance).__name__} {uri} subPropertyOf '
                f'{type(sup).__name__} {sup.get_has_identifier()}')

def _check_class_datatype_hierarchy(logic, instance, uri):
    if not isinstance(instance, (Concept, Datatype)) or isinstance(instance, DatatypeRestriction):
        return
    for sup in (instance.get_is_sub_concept_of() or []):
        if sup is not None and not isinstance(sup, type(instance)):
            logic.add_warning('class_datatype_mismatch_hierarchy', uri,
                f'§5.8.1: {type(instance).__name__} {uri} subClassOf '
                f'{type(sup).__name__} {sup.get_has_identifier()}')

def _check_punning_conflicts(logic, uri, instances):
    types = {type(i) for i in instances}
    if Concept in types and Datatype in types:
        logic.add_warning('class_datatype_conflict', uri,
            f'§5.8.1: {uri} has both Concept and Datatype in cache')
    prop_types = types & {Relation, Attribute, Annotation}
    if len(prop_types) > 1:
        logic.add_warning('property_type_conflict', uri,
            f'§5.8.1: {uri} has multiple property types: {sorted(t.__name__ for t in prop_types)}')

def _check_config_mismatches(logic):
    for pred, cfg in logic._property_mapping.items():
        target_classes = cfg.get('target_classes', [])
        if not target_classes:
            continue
        target_tuple = tuple(target_classes)
        expected = [c.__name__ for c in target_classes]
        for uri in logic.graph.subjects(pred, None):
            if not isinstance(uri, URIRef):
                continue
            instances = logic._instance_cache.get(uri, set())
            if instances and not any(isinstance(i, target_tuple) for i in instances):
                actual = [type(i).__name__ for i in instances]
                logic.add_warning('config_type_mismatch', uri,
                    f'{uri} subject of {pred} (expected {expected}) got {actual}')