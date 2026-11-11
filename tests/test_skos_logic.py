"""
test_skos_logic.py
Reference: https://www.w3.org/TR/skos-reference/

Unit tests for SkosLogic.

Covers:
  Phase 1  - skipped (SKOS classifies only through rdf:type)
  Phase 2  - Instance creation from rdf:type (Concept, ConceptScheme, Collection)
  Phase 3  - Property population (labels, notes, semantic and mapping relations,
             scheme links, collections)
  Phase 4/5 - No-op phases
  Phase 6  - Statement creation for unmapped triples
  Namespace filter

Each test builds a minimal in-memory RDF graph, constructs a SkosLogic with a
SkosConfigManager and runs only the phases needed.

Run with:
    uv run pytest tests/test_skos_logic.py -v
"""

from rdflib import Graph, BNode, Literal as RDFLiteral, Namespace
from rdflib.namespace import RDF, SKOS, XSD
from rdflib.collection import Collection as RDFLibCollection

from lode.models import Concept, Collection, Model, Statement
from lode.reader.config_manager import SkosConfigManager
from lode.reader.logic.skos_logic import SkosLogic

EX = Namespace("http://example.org/skos#")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_logic(triples: list, graph: Graph = None) -> SkosLogic:
    """Build a SkosLogic from (s, p, o) tuples, or from a ready-made graph."""
    g = graph if graph is not None else Graph()
    for s, p, o in triples:
        g.add((s, p, o))
    return SkosLogic(g, {}, SkosConfigManager())


def _run_all(logic: SkosLogic):
    """Run all phases in order."""
    logic.phase1_classify_from_predicates()
    logic.phase2_create_from_types()
    logic.phase3_populate_properties()
    logic.phase4_process_group_axioms()
    logic.phase5_fallback()
    logic.phase6_create_statements()


def _instance_for_uri(logic: SkosLogic, uri, cls=None):
    """Return the cached instance for uri, optionally filtered by class."""
    for i in logic._instance_cache.get(uri, set()):
        if cls is None or isinstance(i, cls):
            return i
    return None


def _instances_of(logic: SkosLogic, cls):
    """Return all cached instances of exactly the given class."""
    return [i for insts in logic._instance_cache.values()
            for i in insts if type(i) is cls]


def _values(literals) -> set:
    """Return the lexical values of a list of model Literals."""
    return {l.get_has_value() for l in literals}


def _concept_graph(*uris) -> list:
    """Return the rdf:type skos:Concept triples for the given URIs."""
    return [(u, RDF.type, SKOS.Concept) for u in uris]


# ===========================================================================
# PHASE 1
# ===========================================================================

class TestPhase1:

    def test_phase1_is_noop(self):
        """Phase 1 must not create anything: SKOS uses only rdf:type."""
        logic = _make_logic([(EX.A, SKOS.broader, EX.B)])
        logic.phase1_classify_from_predicates()
        assert logic._instance_cache == {}


# ===========================================================================
# PHASE 2 - Instance creation from rdf:type
# ===========================================================================

class TestPhase2:

    def test_skos_concept_creates_concept(self):
        """skos:Concept must produce a Concept."""
        logic = _make_logic(_concept_graph(EX.A))
        logic.phase2_create_from_types()
        assert _instance_for_uri(logic, EX.A, Concept) is not None

    def test_skos_concept_scheme_creates_model(self):
        """skos:ConceptScheme must produce a Model."""
        logic = _make_logic([(EX.S, RDF.type, SKOS.ConceptScheme)])
        logic.phase2_create_from_types()
        assert _instance_for_uri(logic, EX.S, Model) is not None

    def test_skos_collection_creates_unordered_collection(self):
        """skos:Collection must produce a Collection with is_ordered=False."""
        logic = _make_logic([(EX.C, RDF.type, SKOS.Collection)])
        logic.phase2_create_from_types()
        coll = _instance_for_uri(logic, EX.C, Collection)
        assert coll is not None
        assert coll.get_is_ordered() is False

    def test_skos_ordered_collection_is_ordered(self):
        """skos:OrderedCollection must produce a Collection with is_ordered=True."""
        logic = _make_logic([(EX.C, RDF.type, SKOS.OrderedCollection)])
        logic.phase2_create_from_types()
        coll = _instance_for_uri(logic, EX.C, Collection)
        assert coll is not None
        assert coll.get_is_ordered() is True

    def test_unknown_type_creates_nothing(self):
        """A subject typed with an unmapped class must not be instantiated in phase 2."""
        logic = _make_logic([(EX.X, RDF.type, EX.Unknown)])
        logic.phase2_create_from_types()
        assert EX.X not in logic._instance_cache

    def test_no_duplicate_on_repeated_call(self):
        """Calling phase 2 twice must not add a second instance."""
        logic = _make_logic(_concept_graph(EX.A))
        logic.phase2_create_from_types()
        logic.phase2_create_from_types()
        assert len(logic._instance_cache[EX.A]) == 1


# ===========================================================================
# PHASE 3 - Lexical labels (§5), notation and notes (§7)
# ===========================================================================

class TestLabelsAndNotes:

    def test_same_text_different_language_keeps_each_language(self):
        """Labels with the same text but different language tags must stay distinct:
        the shared Literal cache must not merge them."""
        logic = _make_logic(_concept_graph(EX.A, EX.B) + [
            (EX.A, SKOS.prefLabel, RDFLiteral("Communication", lang="en")),
            (EX.B, SKOS.prefLabel, RDFLiteral("Communication", lang="fr")),
            (EX.B, SKOS.altLabel, RDFLiteral("Communication")),
        ])
        _run_all(logic)
        a = _instance_for_uri(logic, EX.A, Concept)
        b = _instance_for_uri(logic, EX.B, Concept)
        assert a.get_has_preferred_label()[0].get_has_language() == "en"
        assert b.get_has_preferred_label()[0].get_has_language() == "fr"
        assert b.get_has_alternative_label()[0].get_has_language() is None

    
    def test_pref_label_with_language(self):
        """skos:prefLabel must be stored as a Literal keeping its language tag."""
        logic = _make_logic(_concept_graph(EX.A) + [
            (EX.A, SKOS.prefLabel, RDFLiteral("tree", lang="en")),
        ])
        _run_all(logic)
        labels = _instance_for_uri(logic, EX.A, Concept).get_has_preferred_label()
        assert _values(labels) == {"tree"}
        assert labels[0].get_has_language() == "en"

    def test_alt_and_hidden_label(self):
        """skos:altLabel and skos:hiddenLabel must go to their own lists."""
        logic = _make_logic(_concept_graph(EX.A) + [
            (EX.A, SKOS.altLabel, RDFLiteral("plant", lang="en")),
            (EX.A, SKOS.hiddenLabel, RDFLiteral("tre", lang="en")),
        ])
        _run_all(logic)
        a = _instance_for_uri(logic, EX.A, Concept)
        assert _values(a.get_has_alternative_label()) == {"plant"}
        assert _values(a.get_has_hidden_label()) == {"tre"}
        assert a.get_has_preferred_label() == []

    def test_notation_keeps_datatype(self):
        """skos:notation must be stored with its datatype."""
        logic = _make_logic(_concept_graph(EX.A) + [
            (EX.A, SKOS.notation, RDFLiteral("T1", datatype=XSD.string)),
        ])
        _run_all(logic)
        notation = _instance_for_uri(logic, EX.A, Concept).get_has_notation()
        assert _values(notation) == {"T1"}
        assert notation[0].get_has_type().get_has_identifier() == str(XSD.string)

    def test_documentation_properties(self):
        """Every SKOS documentation property must fill its own getter."""
        cases = {
            SKOS.note: "get_has_note",
            SKOS.definition: "get_has_definition",
            SKOS.scopeNote: "get_has_scope_note",
            SKOS.example: "get_has_example",
            SKOS.historyNote: "get_has_history_note",
            SKOS.editorialNote: "get_has_editorial_note",
            SKOS.changeNote: "get_has_change_note",
        }
        logic = _make_logic(_concept_graph(EX.A) + [
            (EX.A, pred, RDFLiteral(getter, lang="en")) for pred, getter in cases.items()
        ])
        _run_all(logic)
        a = _instance_for_uri(logic, EX.A, Concept)
        for getter in cases.values():
            assert _values(getattr(a, getter)()) == {getter}, getter

    def test_labels_apply_to_concept_scheme(self):
        """Documentation properties target Resource, so a ConceptScheme gets them too."""
        logic = _make_logic([
            (EX.S, RDF.type, SKOS.ConceptScheme),
            (EX.S, SKOS.definition, RDFLiteral("a scheme", lang="en")),
        ])
        _run_all(logic)
        scheme = _instance_for_uri(logic, EX.S, Model)
        assert _values(scheme.get_has_definition()) == {"a scheme"}


# ===========================================================================
# PHASE 3 - Semantic relations (§8)
# ===========================================================================

class TestSemanticRelations:

    def test_broader_wires_both_sides(self):
        """skos:broader must fill is_sub_concept_of and the inverse is_super_concept_of."""
        logic = _make_logic(_concept_graph(EX.Child, EX.Parent) + [
            (EX.Child, SKOS.broader, EX.Parent),
        ])
        _run_all(logic)
        child = _instance_for_uri(logic, EX.Child, Concept)
        parent = _instance_for_uri(logic, EX.Parent, Concept)
        assert child.get_is_sub_concept_of() == [parent]
        assert parent.get_is_super_concept_of() == [child]

    def test_narrower_wires_both_sides(self):
        """skos:narrower must fill is_super_concept_of and the inverse is_sub_concept_of."""
        logic = _make_logic(_concept_graph(EX.Child, EX.Parent) + [
            (EX.Parent, SKOS.narrower, EX.Child),
        ])
        _run_all(logic)
        child = _instance_for_uri(logic, EX.Child, Concept)
        parent = _instance_for_uri(logic, EX.Parent, Concept)
        assert parent.get_is_super_concept_of() == [child]
        assert child.get_is_sub_concept_of() == [parent]

    def test_broader_and_narrower_declared_together_no_duplicates(self):
        """Declaring both directions of the same link must list each side once."""
        logic = _make_logic(_concept_graph(EX.Child, EX.Parent) + [
            (EX.Child, SKOS.broader, EX.Parent),
            (EX.Parent, SKOS.narrower, EX.Child),
        ])
        _run_all(logic)
        child = _instance_for_uri(logic, EX.Child, Concept)
        parent = _instance_for_uri(logic, EX.Parent, Concept)
        assert child.get_is_sub_concept_of() == [parent]
        assert parent.get_is_super_concept_of() == [child]

    def test_multiple_broader(self):
        """A concept with two broader concepts must be wired into both."""
        logic = _make_logic(_concept_graph(EX.C, EX.P1, EX.P2) + [
            (EX.C, SKOS.broader, EX.P1),
            (EX.C, SKOS.broader, EX.P2),
        ])
        _run_all(logic)
        c = _instance_for_uri(logic, EX.C, Concept)
        p1 = _instance_for_uri(logic, EX.P1, Concept)
        p2 = _instance_for_uri(logic, EX.P2, Concept)
        assert set(c.get_is_sub_concept_of()) == {p1, p2}
        assert p1.get_is_super_concept_of() == [c]
        assert p2.get_is_super_concept_of() == [c]

    def test_related_is_symmetric(self):
        """skos:related stated one way must appear on both concepts (§8.6.2)."""
        logic = _make_logic(_concept_graph(EX.A, EX.B) + [(EX.A, SKOS.related, EX.B)])
        _run_all(logic)
        a = _instance_for_uri(logic, EX.A, Concept)
        b = _instance_for_uri(logic, EX.B, Concept)
        assert a.get_is_related_to() == [b]
        assert b.get_is_related_to() == [a]

    def test_related_declared_both_ways_no_duplicates(self):
        """skos:related stated in both directions must be listed once per side."""
        logic = _make_logic(_concept_graph(EX.A, EX.B) + [
            (EX.A, SKOS.related, EX.B),
            (EX.B, SKOS.related, EX.A),
        ])
        _run_all(logic)
        a = _instance_for_uri(logic, EX.A, Concept)
        b = _instance_for_uri(logic, EX.B, Concept)
        assert a.get_is_related_to() == [b]
        assert b.get_is_related_to() == [a]


# ===========================================================================
# PHASE 3 - Mapping relations (§10)
# ===========================================================================

class TestMappingRelations:

    def test_broad_match_wires_narrow_match_back(self):
        """skos:broadMatch must set the inverse has_narrow_match."""
        logic = _make_logic(_concept_graph(EX.A, EX.B) + [(EX.A, SKOS.broadMatch, EX.B)])
        _run_all(logic)
        a = _instance_for_uri(logic, EX.A, Concept)
        b = _instance_for_uri(logic, EX.B, Concept)
        assert a.get_has_broad_match() == [b]
        assert b.get_has_narrow_match() == [a]

    def test_narrow_match_wires_broad_match_back(self):
        """skos:narrowMatch must set the inverse has_broad_match."""
        logic = _make_logic(_concept_graph(EX.A, EX.B) + [(EX.A, SKOS.narrowMatch, EX.B)])
        _run_all(logic)
        a = _instance_for_uri(logic, EX.A, Concept)
        b = _instance_for_uri(logic, EX.B, Concept)
        assert a.get_has_narrow_match() == [b]
        assert b.get_has_broad_match() == [a]

    def test_exact_match_is_symmetric(self):
        """skos:exactMatch must appear on both concepts."""
        logic = _make_logic(_concept_graph(EX.A, EX.B) + [(EX.A, SKOS.exactMatch, EX.B)])
        _run_all(logic)
        a = _instance_for_uri(logic, EX.A, Concept)
        b = _instance_for_uri(logic, EX.B, Concept)
        assert a.get_has_exact_match() == [b]
        assert b.get_has_exact_match() == [a]

    def test_close_match_is_symmetric(self):
        """skos:closeMatch must appear on both concepts."""
        logic = _make_logic(_concept_graph(EX.A, EX.B) + [(EX.A, SKOS.closeMatch, EX.B)])
        _run_all(logic)
        a = _instance_for_uri(logic, EX.A, Concept)
        b = _instance_for_uri(logic, EX.B, Concept)
        assert a.get_has_close_match() == [b]
        assert b.get_has_close_match() == [a]

    def test_related_match_is_symmetric(self):
        """skos:relatedMatch must appear on both concepts."""
        logic = _make_logic(_concept_graph(EX.A, EX.B) + [(EX.A, SKOS.relatedMatch, EX.B)])
        _run_all(logic)
        a = _instance_for_uri(logic, EX.A, Concept)
        b = _instance_for_uri(logic, EX.B, Concept)
        assert a.get_has_related_match() == [b]
        assert b.get_has_related_match() == [a]

    def test_match_declared_both_ways_no_duplicates(self):
        """A symmetric match stated in both directions must be listed once per side."""
        logic = _make_logic(_concept_graph(EX.A, EX.B) + [
            (EX.A, SKOS.exactMatch, EX.B),
            (EX.B, SKOS.exactMatch, EX.A),
        ])
        _run_all(logic)
        a = _instance_for_uri(logic, EX.A, Concept)
        b = _instance_for_uri(logic, EX.B, Concept)
        assert a.get_has_exact_match() == [b]
        assert b.get_has_exact_match() == [a]


# ===========================================================================
# PHASE 3 - Concept schemes (§4)
# ===========================================================================

class TestConceptSchemes:

    def test_in_scheme(self):
        """skos:inScheme must fill is_included_in with the scheme Model."""
        logic = _make_logic(_concept_graph(EX.A) + [
            (EX.S, RDF.type, SKOS.ConceptScheme),
            (EX.A, SKOS.inScheme, EX.S),
        ])
        _run_all(logic)
        a = _instance_for_uri(logic, EX.A, Concept)
        scheme = _instance_for_uri(logic, EX.S, Model)
        assert a.get_is_included_in() == [scheme]

    def test_has_top_concept_wires_both_sides(self):
        """skos:hasTopConcept must fill has_top_concept and the inverse is_top_concept_of."""
        logic = _make_logic(_concept_graph(EX.A) + [
            (EX.S, RDF.type, SKOS.ConceptScheme),
            (EX.S, SKOS.hasTopConcept, EX.A),
        ])
        _run_all(logic)
        a = _instance_for_uri(logic, EX.A, Concept)
        scheme = _instance_for_uri(logic, EX.S, Model)
        assert scheme.get_has_top_concept() == [a]
        assert a.is_top_concept_of == [scheme]

    def test_top_concept_of_wires_both_sides(self):
        """skos:topConceptOf must fill is_top_concept_of and the inverse has_top_concept."""
        logic = _make_logic(_concept_graph(EX.A) + [
            (EX.S, RDF.type, SKOS.ConceptScheme),
            (EX.A, SKOS.topConceptOf, EX.S),
        ])
        _run_all(logic)
        a = _instance_for_uri(logic, EX.A, Concept)
        scheme = _instance_for_uri(logic, EX.S, Model)
        assert a.is_top_concept_of == [scheme]
        assert scheme.get_has_top_concept() == [a]

    def test_top_concept_declared_both_ways_no_duplicates(self):
        """hasTopConcept plus topConceptOf for the same pair must be listed once per side."""
        logic = _make_logic(_concept_graph(EX.A) + [
            (EX.S, RDF.type, SKOS.ConceptScheme),
            (EX.S, SKOS.hasTopConcept, EX.A),
            (EX.A, SKOS.topConceptOf, EX.S),
        ])
        _run_all(logic)
        a = _instance_for_uri(logic, EX.A, Concept)
        scheme = _instance_for_uri(logic, EX.S, Model)
        assert scheme.get_has_top_concept() == [a]
        assert a.is_top_concept_of == [scheme]


# ===========================================================================
# PHASE 3 - Collections (§9)
# ===========================================================================

class TestCollections:

    def test_member_concept(self):
        """skos:member must add the concept to has_member."""
        logic = _make_logic(_concept_graph(EX.A) + [
            (EX.C, RDF.type, SKOS.Collection),
            (EX.C, SKOS.member, EX.A),
        ])
        _run_all(logic)
        coll = _instance_for_uri(logic, EX.C, Collection)
        assert coll.get_has_member() == [_instance_for_uri(logic, EX.A, Concept)]

    def test_member_nested_collection(self):
        """skos:member may point to another Collection."""
        logic = _make_logic([
            (EX.C, RDF.type, SKOS.Collection),
            (EX.Inner, RDF.type, SKOS.Collection),
            (EX.C, SKOS.member, EX.Inner),
        ])
        _run_all(logic)
        coll = _instance_for_uri(logic, EX.C, Collection)
        assert coll.get_has_member() == [_instance_for_uri(logic, EX.Inner, Collection)]

    def test_member_list_keeps_order_and_sets_ordered(self):
        """skos:memberList must expand the list in order and flag the collection ordered."""
        g = Graph()
        head = BNode()
        RDFLibCollection(g, head, [EX.B, EX.A, EX.C])
        logic = _make_logic(
            _concept_graph(EX.A, EX.B, EX.C) + [
                (EX.C1, RDF.type, SKOS.OrderedCollection),
                (EX.C1, SKOS.memberList, head),
            ],
            graph=g,
        )
        _run_all(logic)
        coll = _instance_for_uri(logic, EX.C1, Collection)
        ids = [m.get_has_identifier() for m in coll.get_has_member()]
        assert ids == [str(EX.B), str(EX.A), str(EX.C)]
        assert coll.get_is_ordered() is True

    def test_member_list_and_member_no_duplicates(self):
        """An item given by both memberList and member must appear once."""
        g = Graph()
        head = BNode()
        RDFLibCollection(g, head, [EX.A])
        logic = _make_logic(
            _concept_graph(EX.A) + [
                (EX.C1, RDF.type, SKOS.OrderedCollection),
                (EX.C1, SKOS.memberList, head),
                (EX.C1, SKOS.member, EX.A),
            ],
            graph=g,
        )
        _run_all(logic)
        coll = _instance_for_uri(logic, EX.C1, Collection)
        assert len(coll.get_has_member()) == 1

    def test_member_list_skips_literals(self):
        """Literal items in a memberList must be ignored."""
        g = Graph()
        head = BNode()
        RDFLibCollection(g, head, [EX.A, RDFLiteral("not a resource")])
        logic = _make_logic(
            _concept_graph(EX.A) + [
                (EX.C1, RDF.type, SKOS.OrderedCollection),
                (EX.C1, SKOS.memberList, head),
            ],
            graph=g,
        )
        _run_all(logic)
        coll = _instance_for_uri(logic, EX.C1, Collection)
        assert len(coll.get_has_member()) == 1

    def test_member_list_not_a_list_adds_no_members(self):
        """A memberList whose object is not an RDF list must add no members."""
        logic = _make_logic([
            (EX.C1, RDF.type, SKOS.OrderedCollection),
            (EX.C1, SKOS.memberList, EX.NotAList),
        ])
        _run_all(logic)
        assert _instance_for_uri(logic, EX.C1, Collection).get_has_member() == []


# ===========================================================================
# PHASE 4 / 5 - No-op phases
# ===========================================================================

class TestNoopPhases:

    def test_phase4_and_phase5_do_not_change_cache(self):
        """Phases 4 and 5 must leave the cache untouched."""
        logic = _make_logic(_concept_graph(EX.A, EX.B) + [(EX.A, SKOS.broader, EX.B)])
        logic.phase2_create_from_types()
        logic.phase3_populate_properties()
        before = {k: set(v) for k, v in logic._instance_cache.items()}
        logic.phase4_process_group_axioms()
        logic.phase5_fallback()
        assert logic._instance_cache == before


# ===========================================================================
# PHASE 6 - Statement creation
# ===========================================================================

class TestPhase6:

    def test_unmapped_triple_produces_statement(self):
        """A triple whose predicate is not mapped must become a Statement."""
        logic = _make_logic(_concept_graph(EX.A) + [(EX.A, EX.customPred, EX.B)])
        _run_all(logic)
        assert len(_instances_of(logic, Statement)) >= 1

    def test_mapped_triple_produces_no_statement(self):
        """A triple consumed by the mapping must not be reified."""
        logic = _make_logic(_concept_graph(EX.A) + [
            (EX.A, SKOS.prefLabel, RDFLiteral("a", lang="en")),
        ])
        _run_all(logic)
        for stmt in _instances_of(logic, Statement):
            pred = stmt.get_has_predicate()
            assert pred is None or pred.get_has_identifier() != str(SKOS.prefLabel)


# ===========================================================================
# Namespace filter
# ===========================================================================

class TestNamespaceFilter:

    def test_allowed_namespaces_are_rdf_rdfs_skos(self):
        """The SKOS logic must accept only RDF, RDFS and SKOS, ignoring owl."""
        logic = _make_logic([])
        allowed = logic._get_allowed_namespaces()
        assert str(SKOS) in allowed
        assert "http://www.w3.org/2002/07/owl#" not in allowed

    def test_non_mapped_predicate_does_not_populate_instance(self):
        """A predicate outside the mapping must not be tracked as populated."""
        logic = _make_logic(_concept_graph(EX.A) + [
            (EX.A, EX.customPred, RDFLiteral("v")),
        ])
        logic.phase2_create_from_types()
        logic.phase3_populate_properties()
        inst = _instance_for_uri(logic, EX.A, Concept)
        triples = logic._triples_map.get(inst, set())
        assert not any(p == EX.customPred for _, p, _ in triples)
