# tests/test_skos_integrity.py
# Reference: https://www.w3.org/TR/skos-reference/
#
# Checks, on real SKOS vocabularies, that the graph and the model built by
# SkosLogic agree. It is not a SKOS validator: vocabularies that already break
# the spec are skipped (guards), so a failure points at LODE and not at the data.
#
# Run a single vocabulary with:
#     TEST_VOCABULARY_URI=<uri> uv run pytest tests/test_skos_integrity.py -v

import json
import os
from pathlib import Path

import pytest
from rdflib import URIRef, Literal as RDFLiteral
from rdflib.collection import Collection as RDFLibCollection
from rdflib.namespace import RDF, SKOS

from lode.models import Concept, Collection, Model, Literal

VOCABULARIES_PATH = Path(__file__).parent / "taxonomies_skos.json"


def _load_uris():
    """Return the vocabulary URIs: TEST_VOCABULARY_URI if set, else the JSON list."""
    single = os.environ.get("TEST_VOCABULARY_URI")
    if single:
        return [single]
    with open(VOCABULARIES_PATH) as f:
        return [entry["uri"] for entry in json.load(f)["uris"]]


@pytest.fixture(scope="module", params=_load_uris())
def skos_logic(request):
    """Load one vocabulary as SKOS and yield its logic; skip when it cannot be loaded.

    warnings=False on purpose: the reader warnings are OWL-only.
    """
    from lode.reader import Reader
    reader = Reader()
    try:
        reader.load_instances(request.param, "skos", warnings=False)
    except Exception as e:
        pytest.skip(f"Could not load {request.param}: {e}")
    logic = reader._logic
    yield logic
    logic._instance_cache.clear()
    logic._triples_map.clear()


def _inst(logic, uri, cls):
    """Return the cached instance of `uri` that is a `cls`, or None."""
    return next((i for i in logic._instance_cache.get(uri, set()) if isinstance(i, cls)), None)


def _uri_triples(logic, predicate):
    """Yield (s, o) for triples with `predicate` where both ends are URIRefs."""
    for s, _, o in logic.graph.triples((None, predicate, None)):
        if isinstance(s, URIRef) and isinstance(o, URIRef):
            yield s, o


def _pairs(literals):
    """Return the set of (lexical value, language) of model Literals."""
    return {(l.get_has_value(), l.get_has_language()) for l in literals}


#############################################################################################
# §3 Concepts, §4 Concept Schemes, §9 Collections: declarations
#
# Extraction rule: every URI typed skos:Concept / skos:ConceptScheme / skos:Collection
# (also skos:OrderedCollection) must be Concept / Model / Collection in cache.
#############################################################################################

def test_concept_declaration_produces_concept(skos_logic):
    """§3: Every URI declared as skos:Concept must be Concept in cache."""
    for uri in skos_logic.graph.subjects(RDF.type, SKOS.Concept):
        if isinstance(uri, URIRef):
            assert _inst(skos_logic, uri, Concept) is not None, f"§3: {uri} not Concept in cache"


def test_concept_scheme_declaration_produces_model(skos_logic):
    """§4: Every URI declared as skos:ConceptScheme must be Model in cache."""
    for uri in skos_logic.graph.subjects(RDF.type, SKOS.ConceptScheme):
        if isinstance(uri, URIRef):
            assert _inst(skos_logic, uri, Model) is not None, f"§4: {uri} not Model in cache"


def test_collection_declaration_produces_collection(skos_logic):
    """§9: Every skos:Collection / skos:OrderedCollection must be Collection in cache;
    an OrderedCollection must have is_ordered=True."""
    for rdf_type in (SKOS.Collection, SKOS.OrderedCollection):
        for uri in skos_logic.graph.subjects(RDF.type, rdf_type):
            if not isinstance(uri, URIRef):
                continue
            coll = _inst(skos_logic, uri, Collection)
            assert coll is not None, f"§9: {uri} not Collection in cache"
            if rdf_type == SKOS.OrderedCollection:
                assert coll.get_is_ordered() is True, f"§9: {uri} OrderedCollection not ordered"


@pytest.mark.parametrize("cls_a, cls_b, rdf_a, rdf_b", [
    (Concept, Collection, SKOS.Concept, SKOS.Collection),
    (Concept, Model, SKOS.Concept, SKOS.ConceptScheme),
    (Collection, Model, SKOS.Collection, SKOS.ConceptScheme),
])
def test_disjoint_classes_not_mixed_in_cache(skos_logic, cls_a, cls_b, rdf_a, rdf_b):
    """§4.6.2 / §9.6.2: Concept, ConceptScheme and Collection are pairwise disjoint.
    Guard: if the vocabulary itself declares both types, it is malformed, not a LODE bug."""
    for uri, instances in skos_logic._instance_cache.items():
        if not isinstance(uri, URIRef):
            continue
        if (uri, RDF.type, rdf_a) in skos_logic.graph and (uri, RDF.type, rdf_b) in skos_logic.graph:
            continue
        has_a = any(isinstance(i, cls_a) for i in instances)
        has_b = any(isinstance(i, cls_b) for i in instances)
        assert not (has_a and has_b), (
            f"{uri} is both {cls_a.__name__} and {cls_b.__name__} in cache"
        )


def test_no_duplicate_instances_of_same_type(skos_logic):
    """A URIRef must not have two instances of the same type in cache."""
    for uri, instances in skos_logic._instance_cache.items():
        if not isinstance(uri, URIRef):
            continue
        types = [type(i) for i in instances]
        for t in types:
            assert types.count(t) == 1, f"{uri} has {types.count(t)} instances of {t.__name__}"


def test_no_instance_has_none_identifier(skos_logic):
    """Every non-Literal instance must have an identifier."""
    for instances in skos_logic._instance_cache.values():
        for inst in instances:
            if not isinstance(inst, Literal):
                assert inst.get_has_identifier() is not None, f"{type(inst).__name__} has None identifier"


def test_all_literals_have_value(skos_logic):
    """Every Literal in cache must have has_value set."""
    for instances in skos_logic._instance_cache.values():
        for inst in instances:
            if isinstance(inst, Literal):
                assert inst.get_has_value() is not None, "Literal has no value"


#############################################################################################
# §5 Lexical Labels, §6 Notations, §7 Documentation Properties
#
# Extraction rule: every (s, p, literal) triple with a mapped predicate must appear
# in the matching getter of s with the same lexical value AND language tag.
#############################################################################################

_LITERAL_PROPERTIES = {
    SKOS.prefLabel: "get_has_preferred_label",
    SKOS.altLabel: "get_has_alternative_label",
    SKOS.hiddenLabel: "get_has_hidden_label",
    SKOS.notation: "get_has_notation",
    SKOS.note: "get_has_note",
    SKOS.definition: "get_has_definition",
    SKOS.scopeNote: "get_has_scope_note",
    SKOS.example: "get_has_example",
    SKOS.historyNote: "get_has_history_note",
    SKOS.editorialNote: "get_has_editorial_note",
    SKOS.changeNote: "get_has_change_note",
}


@pytest.mark.parametrize("predicate, getter", list(_LITERAL_PROPERTIES.items()),
                         ids=lambda v: str(v).rsplit("#", 1)[-1])
def test_literal_properties_are_populated(skos_logic, predicate, getter):
    """§5-§7: each literal of a mapped SKOS property is in the subject's getter,
    with its language tag."""
    for s, _, o in skos_logic.graph.triples((None, predicate, None)):
        if not isinstance(s, URIRef) or not isinstance(o, RDFLiteral):
            continue
        holders = [i for i in skos_logic._instance_cache.get(s, set()) if hasattr(i, getter)]
        assert holders, f"{s} has {predicate} in graph but no instance with {getter}"
        assert any((str(o), o.language) in _pairs(getattr(h, getter)()) for h in holders), (
            f"{s} {predicate} {o!r}: not in {getter}() (value or language lost)"
        )


#############################################################################################
# §8 Semantic Relations, §10 Mapping Properties
#
# Extraction rule: both ends are Concept in cache, the relation is populated on the
# subject and the inverse (or symmetric) link is populated on the object.
#############################################################################################

_CONCEPT_RELATIONS = [
    # (predicate, getter on subject, getter on object)
    (SKOS.broader, "get_is_sub_concept_of", "get_is_super_concept_of"),
    (SKOS.narrower, "get_is_super_concept_of", "get_is_sub_concept_of"),
    (SKOS.related, "get_is_related_to", "get_is_related_to"),
    (SKOS.broadMatch, "get_has_broad_match", "get_has_narrow_match"),
    (SKOS.narrowMatch, "get_has_narrow_match", "get_has_broad_match"),
    (SKOS.closeMatch, "get_has_close_match", "get_has_close_match"),
    (SKOS.exactMatch, "get_has_exact_match", "get_has_exact_match"),
    (SKOS.relatedMatch, "get_has_related_match", "get_has_related_match"),
]


@pytest.mark.parametrize("predicate, subj_getter, obj_getter", _CONCEPT_RELATIONS,
                         ids=[str(r[0]).rsplit("#", 1)[-1] for r in _CONCEPT_RELATIONS])
def test_concept_relations_are_wired_both_sides(skos_logic, predicate, subj_getter, obj_getter):
    """§8, §10: each relation between two concepts is populated on both ends."""
    for s, o in _uri_triples(skos_logic, predicate):
        s_inst = _inst(skos_logic, s, Concept)
        o_inst = _inst(skos_logic, o, Concept)
        assert s_inst is not None, f"{s} is subject of {predicate} but not Concept in cache"
        assert o_inst is not None, f"{o} is object of {predicate} but not Concept in cache"
        assert o_inst in getattr(s_inst, subj_getter)(), f"{s} {predicate} {o}: {subj_getter} missing"
        assert s_inst in getattr(o_inst, obj_getter)(), f"{s} {predicate} {o}: inverse {obj_getter} missing"


#############################################################################################
# §4 Concept Schemes
#
# Extraction rule: inScheme fills is_included_in; hasTopConcept / topConceptOf fill
# Model.has_top_concept and Concept.is_top_concept_of, each as the inverse of the other.
#############################################################################################

def test_in_scheme_populated(skos_logic):
    """§4.4: skos:inScheme must fill is_included_in with the scheme Model."""
    for s, o in _uri_triples(skos_logic, SKOS.inScheme):
        scheme = _inst(skos_logic, o, Model)
        assert scheme is not None, f"{o} is object of skos:inScheme but not Model in cache"
        assert any(scheme in i.get_is_included_in()
                   for i in skos_logic._instance_cache.get(s, set()) if hasattr(i, "get_is_included_in")), (
            f"{s} skos:inScheme {o}: is_included_in missing"
        )


def test_top_concepts_wired_both_sides(skos_logic):
    """§4.6: hasTopConcept and topConceptOf must be wired in both directions."""
    for scheme_uri, concept_uri in _uri_triples(skos_logic, SKOS.hasTopConcept):
        scheme, concept = _inst(skos_logic, scheme_uri, Model), _inst(skos_logic, concept_uri, Concept)
        assert scheme is not None and concept is not None, f"{scheme_uri} hasTopConcept {concept_uri}: wrong types"
        assert concept in scheme.get_has_top_concept()
        assert scheme in concept.get_is_top_concept_of()
    for concept_uri, scheme_uri in _uri_triples(skos_logic, SKOS.topConceptOf):
        scheme, concept = _inst(skos_logic, scheme_uri, Model), _inst(skos_logic, concept_uri, Concept)
        assert scheme is not None and concept is not None, f"{concept_uri} topConceptOf {scheme_uri}: wrong types"
        assert concept in scheme.get_has_top_concept()
        assert scheme in concept.get_is_top_concept_of()


#############################################################################################
# §9 Collections
#
# Extraction rule: every skos:member is in has_member; every skos:memberList keeps
# the RDF list order and marks the collection as ordered.
#############################################################################################

def test_collection_members_populated(skos_logic):
    """§9.3: each skos:member must be in the collection's has_member."""
    for c, m in _uri_triples(skos_logic, SKOS.member):
        coll = _inst(skos_logic, c, Collection)
        assert coll is not None, f"{c} has skos:member but is not Collection in cache"
        members = {i.get_has_identifier() for i in coll.get_has_member()}
        assert str(m) in members, f"{c} skos:member {m}: missing from has_member"


def test_member_list_keeps_order(skos_logic):
    """§9.3: skos:memberList items appear in has_member in list order; collection is ordered."""
    for c, head in skos_logic.graph.subject_objects(SKOS.memberList):
        if not isinstance(c, URIRef):
            continue
        coll = _inst(skos_logic, c, Collection)
        assert coll is not None, f"{c} has skos:memberList but is not Collection in cache"
        expected = [str(i) for i in RDFLibCollection(skos_logic.graph, head) if not isinstance(i, RDFLiteral)]
        actual = [i.get_has_identifier() for i in coll.get_has_member()]
        # skos:member triples may add items after the list: only the list prefix is ordered
        assert [x for x in actual if x in expected] == expected, f"{c}: memberList order lost"
        assert coll.get_is_ordered() is True, f"{c}: memberList but is_ordered is False"
