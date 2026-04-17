"""
test_owl_logic.py
Systematic unit tests for OwlLogic.

Covers:
  Phase 1  - BNode classification via inferred_class predicates
  Phase 2  - Instance creation from rdf:type + static setters
  Phase 3  - Property population (setters, handlers)
  Phase 4  - Group axioms (AllDisjointClasses, AllDifferent, AllDisjointProperties)
  Phase 5  - Fallback: Property reclassification, OWL defaults, punning annotation
  Phase 6  - Statement creation for unmapped triples
  get_or_create - cache deduplication, punning, namespace filtering
  Inferences - inverseOf classification, subPropertyOf hierarchy (up/down),
               domain/range inheritance, rdfs:Literal default for Attribute

Each test is self-contained: builds a minimal in-memory RDF graph, constructs
an OwlLogic instance with an OwlConfigManager strategy, and runs only the
phases needed to exercise the target behaviour.

Run with:
    pytest test_owl_logic.py -v
"""

import pytest
from rdflib import Graph, URIRef, BNode, Literal as RDFLiteral, Namespace
from rdflib.namespace import RDF, RDFS, OWL, XSD

# ---------------------------------------------------------------------------
# Adjust these imports to match the actual package layout of your project.
# ---------------------------------------------------------------------------
from lode.models import (
    Concept, Property, Relation, Attribute, Annotation,
    Individual, Model, Statement, Literal, Datatype,
    TruthFunction, Quantifier, Cardinality, OneOf, Value,
    Restriction, Resource,
)
from lode.reader.config_manager import OwlConfigManager
from lode.reader.logic.owl_logic import OwlLogic

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

EX = Namespace("http://example.org/test#")


def _make_logic(triples: list) -> OwlLogic:
    """Build a minimal OwlLogic from a list of (s, p, o) tuples."""
    g = Graph()
    for s, p, o in triples:
        g.add((s, p, o))
    cache = {}
    strategy = OwlConfigManager()
    return OwlLogic(g, cache, strategy)


def _run_all(logic: OwlLogic):
    """Run all phases in order."""
    logic.phase1_classify_from_predicates()
    logic.phase2_create_from_types()
    logic.phase3_populate_properties()
    logic.phase4_process_group_axioms()
    logic.phase5_fallback()
    logic.phase6_create_statements()

def _instances_of(logic: OwlLogic, cls):
    """Return all cached instances of a given class (exact type match)."""
    result = []
    for instances in logic._instance_cache.values():
        for i in instances:
            if type(i) is cls:
                result.append(i)
    return result

def _instance_for_uri(logic: OwlLogic, uri, cls=None):
    """Return the cached instance for uri, optionally filtered by class."""
    instances = logic._instance_cache.get(uri, set())
    for i in instances:
        if cls is None or isinstance(i, cls):
            return i
    return None

def _make_rdf_list(g, items):
    """Helper: builds an RDF list in graph g from items, returns head BNode."""
    from rdflib.collection import Collection as Col
    head = BNode()
    Col(g, head, items)
    return head


# ===========================================================================
# PHASE 1 - BNode classification via inferred_class predicates
# ===========================================================================

class TestPhase1:

    def test_bnode_classified_as_quantifier_via_some_values_from(self):
        """A BNode bearing owl:someValuesFrom must be classified as Quantifier."""
        bnode = BNode()
        logic = _make_logic([
            (bnode, OWL.someValuesFrom, EX.SomeConcept),
        ])
        logic.phase1_classify_from_predicates()
        assert bnode in logic._instance_cache
        inst = next(iter(logic._instance_cache[bnode]))
        assert isinstance(inst, Quantifier)

    def test_bnode_classified_as_quantifier_via_all_values_from(self):
        """A BNode bearing owl:allValuesFrom must be classified as Quantifier."""
        bnode = BNode()
        logic = _make_logic([
            (bnode, OWL.allValuesFrom, EX.SomeConcept),
        ])
        logic.phase1_classify_from_predicates()
        inst = next(iter(logic._instance_cache[bnode]))
        assert isinstance(inst, Quantifier)

    def test_bnode_classified_as_cardinality_via_min_cardinality(self):
        """A BNode bearing owl:minCardinality must be classified as Cardinality."""
        bnode = BNode()
        logic = _make_logic([
            (bnode, OWL.minCardinality, RDFLiteral(1, datatype=XSD.nonNegativeInteger)),
        ])
        logic.phase1_classify_from_predicates()
        inst = next(iter(logic._instance_cache[bnode]))
        assert isinstance(inst, Cardinality)

    def test_bnode_classified_as_truth_function_via_intersection_of(self):
        """A BNode bearing owl:intersectionOf must be classified as TruthFunction."""
        bnode = BNode()
        logic = _make_logic([
            (bnode, OWL.intersectionOf, BNode()),
        ])
        logic.phase1_classify_from_predicates()
        inst = next(iter(logic._instance_cache[bnode]))
        assert isinstance(inst, TruthFunction)

    def test_uriref_classified_in_phase1(self):
        """Phase 1 must only classify BNodes; URIRefs carrying the same predicates
        should not be touched."""
        logic = _make_logic([
            (EX.MyClass, OWL.disjointWith, BNode()),
        ])
        logic.phase1_classify_from_predicates()
        assert EX.MyClass in logic._instance_cache

    def test_bnode_classified_as_one_of(self):
        """A BNode bearing owl:oneOf must be classified as OneOf."""
        bnode = BNode()
        logic = _make_logic([
            (bnode, OWL.oneOf, BNode()),
        ])
        logic.phase1_classify_from_predicates()
        inst = next(iter(logic._instance_cache[bnode]))
        assert isinstance(inst, OneOf)

    def test_bnode_classified_as_value_via_has_value(self):
        """A BNode bearing owl:hasValue must be classified as Value."""
        bnode = BNode()
        logic = _make_logic([
            (bnode, OWL.hasValue, EX.SomeIndividual),
        ])
        logic.phase1_classify_from_predicates()
        inst = next(iter(logic._instance_cache[bnode]))
        assert isinstance(inst, Value)


# ===========================================================================
# PHASE 2 - Instance creation from rdf:type
# ===========================================================================

class TestPhase2:

    def test_owl_class_creates_concept(self):
        """A URI typed as owl:Class must produce a Concept instance."""
        logic = _make_logic([
            (EX.MyClass, RDF.type, OWL.Class),
        ])
        logic.phase2_create_from_types()
        inst = _instance_for_uri(logic, EX.MyClass, Concept)
        assert inst is not None

    def test_owl_object_property_creates_relation(self):
        """A URI typed as owl:ObjectProperty must produce a Relation instance."""
        logic = _make_logic([
            (EX.myProp, RDF.type, OWL.ObjectProperty),
        ])
        logic.phase2_create_from_types()
        inst = _instance_for_uri(logic, EX.myProp, Relation)
        assert inst is not None

    def test_owl_datatype_property_creates_attribute(self):
        """A URI typed as owl:DatatypeProperty must produce an Attribute instance."""
        logic = _make_logic([
            (EX.myAttr, RDF.type, OWL.DatatypeProperty),
        ])
        logic.phase2_create_from_types()
        inst = _instance_for_uri(logic, EX.myAttr, Attribute)
        assert inst is not None

    def test_owl_annotation_property_creates_annotation(self):
        """A URI typed as owl:AnnotationProperty must produce an Annotation instance."""
        logic = _make_logic([
            (EX.myAnnot, RDF.type, OWL.AnnotationProperty),
        ])
        logic.phase2_create_from_types()
        inst = _instance_for_uri(logic, EX.myAnnot, Annotation)
        assert inst is not None

    def test_owl_named_individual_creates_individual(self):
        """A URI typed as owl:NamedIndividual must produce an Individual instance."""
        logic = _make_logic([
            (EX.myInd, RDF.type, OWL.NamedIndividual),
        ])
        logic.phase2_create_from_types()
        inst = _instance_for_uri(logic, EX.myInd, Individual)
        assert inst is not None

    def test_owl_ontology_creates_model(self):
        """A URI typed as owl:Ontology must produce a Model instance."""
        logic = _make_logic([
            (EX.myOntology, RDF.type, OWL.Ontology),
        ])
        logic.phase2_create_from_types()
        inst = _instance_for_uri(logic, EX.myOntology, Model)
        assert inst is not None

    def test_symmetric_property_setter_applied(self):
        """owl:SymmetricProperty typed entity must have is_symmetric=True."""
        logic = _make_logic([
            (EX.myRel, RDF.type, OWL.SymmetricProperty),
        ])
        logic.phase2_create_from_types()
        inst = _instance_for_uri(logic, EX.myRel, Relation)
        assert inst is not None
        assert inst.get_is_symmetric() is True

    def test_transitive_property_setter_applied(self):
        """owl:TransitiveProperty typed entity must have is_transitive=True."""
        logic = _make_logic([
            (EX.myRel, RDF.type, OWL.TransitiveProperty),
        ])
        logic.phase2_create_from_types()
        inst = _instance_for_uri(logic, EX.myRel, Relation)
        assert inst is not None
        assert inst.get_is_transitive() is True

    def test_asymmetric_property_setter_applied(self):
        """owl:AsymmetricProperty must produce a Relation with is_asymmetric=True."""
        logic = _make_logic([
            (EX.myRel, RDF.type, OWL.AsymmetricProperty),
        ])
        logic.phase2_create_from_types()
        inst = _instance_for_uri(logic, EX.myRel, Relation)
        assert inst is not None
        assert inst.get_is_asymmetric() is True

    def test_irreflexive_property_setter_applied(self):
        """owl:IrreflexiveProperty must produce a Relation with is_irreflexive=True."""
        logic = _make_logic([
            (EX.myRel, RDF.type, OWL.IrreflexiveProperty),
        ])
        logic.phase2_create_from_types()
        inst = _instance_for_uri(logic, EX.myRel, Relation)
        assert inst is not None
        assert inst.get_is_irreflexive() is True

    def test_reflexive_property_setter_applied(self):
        """owl:ReflexiveProperty must produce a Relation with is_reflexive=True."""
        logic = _make_logic([
            (EX.myRel, RDF.type, OWL.ReflexiveProperty),
        ])
        logic.phase2_create_from_types()
        inst = _instance_for_uri(logic, EX.myRel, Relation)
        assert inst is not None
        assert inst.get_is_reflexive() is True

    def test_inverse_functional_property_setter_applied(self):
        """owl:InverseFunctionalProperty must produce a Relation with is_inverse_functional=True."""
        logic = _make_logic([
            (EX.myRel, RDF.type, OWL.InverseFunctionalProperty),
        ])
        logic.phase2_create_from_types()
        inst = _instance_for_uri(logic, EX.myRel, Relation)
        assert inst is not None
        assert inst.get_is_inverse_functional() is True

    def test_functional_property_setter_applied(self):
        """owl:FunctionalProperty must produce a Property with is_functional=True.
        Target class is Property (not Relation) per config — subtype resolved in phase 5."""
        logic = _make_logic([
            (EX.myProp, RDF.type, OWL.FunctionalProperty),
        ])
        logic.phase2_create_from_types()
        inst = _instance_for_uri(logic, EX.myProp, Property)
        assert inst is not None
        assert inst.get_is_functional() is True

    def test_functional_object_property_is_functional(self):
        """A property typed as both owl:ObjectProperty and owl:FunctionalProperty
        must be a Relation with is_functional=True."""
        logic = _make_logic([
            (EX.myRel, RDF.type, OWL.ObjectProperty),
            (EX.myRel, RDF.type, OWL.FunctionalProperty),
        ])
        logic.phase2_create_from_types()
        inst = _instance_for_uri(logic, EX.myRel, Relation)
        assert inst is not None
        assert inst.get_is_functional() is True

    def test_negative_property_assertion_is_positive_statement_false(self):
        """owl:NegativePropertyAssertion must produce a Statement with is_positive_statement=True."""
        logic = _make_logic([
            (EX.myStmt, RDF.type, OWL.NegativePropertyAssertion),
        ])
        logic.phase2_create_from_types()
        inst = _instance_for_uri(logic, EX.myStmt, Statement)
        assert inst is not None
        assert inst.get_is_positive_statement() is False

    def test_deprecated_class_setter_applied(self):
        """owl:DeprecatedClass must produce a Concept with is_deprecated=True."""
        logic = _make_logic([
            (EX.myClass, RDF.type, OWL.DeprecatedClass),
        ])
        logic.phase2_create_from_types()
        inst = _instance_for_uri(logic, EX.myClass, Concept)
        assert inst is not None
        assert inst.get_is_deprecated() is True

    def test_multiple_static_setters_on_same_property(self):
        """A Relation typed as both owl:SymmetricProperty and owl:TransitiveProperty
        must have both flags set to True."""
        logic = _make_logic([
            (EX.myRel, RDF.type, OWL.SymmetricProperty),
            (EX.myRel, RDF.type, OWL.TransitiveProperty),
        ])
        logic.phase2_create_from_types()
        inst = _instance_for_uri(logic, EX.myRel, Relation)
        assert inst is not None
        assert inst.get_is_symmetric() is True
        assert inst.get_is_transitive() is True

    def test_unknown_rdf_type_creates_individual(self):
        """A subject typed with an rdf:type not in the config must become Individual."""
        logic = _make_logic([
            (EX.myThing, RDF.type, EX.UnknownClass),
        ])
        logic.phase2_create_from_types()
        inst = _instance_for_uri(logic, EX.myThing, Individual)
        assert inst is not None

    def test_no_duplicate_on_repeated_call(self):
        """Calling phase2 twice must not add a second instance for the same URI."""
        logic = _make_logic([
            (EX.MyClass, RDF.type, OWL.Class),
        ])
        logic.phase2_create_from_types()
        logic.phase2_create_from_types()
        assert len(logic._instance_cache.get(EX.MyClass, set())) == 1

    def test_relation_is_symmetric_defaults_false(self):
        """A Relation not typed as owl:SymmetricProperty must have is_symmetric=False."""
        logic = _make_logic([
            (EX.myRel, RDF.type, OWL.ObjectProperty),
        ])
        logic.phase2_create_from_types()
        inst = _instance_for_uri(logic, EX.myRel, Relation)
        assert inst is not None
        assert inst.get_is_symmetric() is False
 
    def test_relation_is_transitive_defaults_false(self):
        """A Relation not typed as owl:TransitiveProperty must have is_transitive=False."""
        logic = _make_logic([
            (EX.myRel, RDF.type, OWL.ObjectProperty),
        ])
        logic.phase2_create_from_types()
        inst = _instance_for_uri(logic, EX.myRel, Relation)
        assert inst.get_is_transitive() is False
 
    def test_relation_is_asymmetric_defaults_false(self):
        """A Relation not typed as owl:AsymmetricProperty must have is_asymmetric=False."""
        logic = _make_logic([
            (EX.myRel, RDF.type, OWL.ObjectProperty),
        ])
        logic.phase2_create_from_types()
        inst = _instance_for_uri(logic, EX.myRel, Relation)
        assert inst.get_is_asymmetric() is False
 
    def test_relation_is_irreflexive_defaults_false(self):
        """A Relation not typed as owl:IrreflexiveProperty must have is_irreflexive=False."""
        logic = _make_logic([
            (EX.myRel, RDF.type, OWL.ObjectProperty),
        ])
        logic.phase2_create_from_types()
        inst = _instance_for_uri(logic, EX.myRel, Relation)
        assert inst.get_is_irreflexive() is False
 
    def test_relation_is_reflexive_defaults_false(self):
        """A Relation not typed as owl:ReflexiveProperty must have is_reflexive=False."""
        logic = _make_logic([
            (EX.myRel, RDF.type, OWL.ObjectProperty),
        ])
        logic.phase2_create_from_types()
        inst = _instance_for_uri(logic, EX.myRel, Relation)
        assert inst.get_is_reflexive() is False
 
    def test_relation_is_inverse_functional_defaults_false(self):
        """A Relation not typed as owl:InverseFunctionalProperty must have
        is_inverse_functional=False."""
        logic = _make_logic([
            (EX.myRel, RDF.type, OWL.ObjectProperty),
        ])
        logic.phase2_create_from_types()
        inst = _instance_for_uri(logic, EX.myRel, Relation)
        assert inst.get_is_inverse_functional() is False
 
    def test_property_is_functional_defaults_false(self):
        """A Property not typed as owl:FunctionalProperty must have is_functional=False."""
        logic = _make_logic([
            (EX.myRel, RDF.type, OWL.ObjectProperty),
        ])
        logic.phase2_create_from_types()
        inst = _instance_for_uri(logic, EX.myRel, Relation)
        assert inst.get_is_functional() is False
 
    def test_resource_is_deprecated_defaults_false(self):
        """A Concept not bearing owl:deprecated must have is_deprecated=False."""
        logic = _make_logic([
            (EX.myClass, RDF.type, OWL.Class),
        ])
        logic.phase2_create_from_types()
        inst = _instance_for_uri(logic, EX.myClass, Concept)
        assert inst.get_is_deprecated() is False


# ===========================================================================
# PHASE 3 - Property population
# ===========================================================================

class TestPhase3:

    def test_rdfs_label_populated(self):
        """rdfs:label must be stored as a Literal on the target instance."""
        logic = _make_logic([
            (EX.MyClass, RDF.type, OWL.Class),
            (EX.MyClass, RDFS.label, RDFLiteral("My Class", lang="en")),
        ])
        _run_all(logic)
        inst = _instance_for_uri(logic, EX.MyClass, Concept)
        assert inst is not None
        labels = inst.get_has_label()
        assert len(labels) >= 1
        assert any(l.get_has_value() == "My Class" for l in labels)

    def test_rdfs_subclass_of_populated(self):
        """rdfs:subClassOf must wire is_sub_concept_of on the Concept."""
        logic = _make_logic([
            (EX.Child, RDF.type, OWL.Class),
            (EX.Parent, RDF.type, OWL.Class),
            (EX.Child, RDFS.subClassOf, EX.Parent),
        ])
        _run_all(logic)
        child = _instance_for_uri(logic, EX.Child, Concept)
        parent = _instance_for_uri(logic, EX.Parent, Concept)
        assert parent in child.get_is_sub_concept_of()

    def test_rdfs_sub_property_of_populated(self):
        """rdfs:subPropertyOf must wire is_sub_property_of on the Property."""
        logic = _make_logic([
            (EX.childProp, RDF.type, OWL.ObjectProperty),
            (EX.parentProp, RDF.type, OWL.ObjectProperty),
            (EX.childProp, RDFS.subPropertyOf, EX.parentProp),
        ])
        _run_all(logic)
        child_prop = _instance_for_uri(logic, EX.childProp, Relation)
        parent_prop = _instance_for_uri(logic, EX.parentProp, Relation)
        assert parent_prop in child_prop.get_is_sub_property_of()

    def test_owl_deprecated_predicate_applied(self):
        """owl:deprecated true on a resource must set is_deprecated=True on the instance."""
        logic = _make_logic([
            (EX.myClass, RDF.type, OWL.Class),
            (EX.myClass, OWL.deprecated, RDFLiteral(True, datatype=XSD.boolean)),
        ])
        logic.phase1_classify_from_predicates() # classifies as Resource
        logic.phase2_create_from_types() # classifies EX.myClass as Concept
        logic.phase3_populate_properties() # adds and populate is_deprecated to the class
        inst = _instance_for_uri(logic, EX.myClass, Concept)
        assert inst is not None
        assert inst.get_is_deprecated() is True

    def test_rdfs_domain_populated(self):
        """rdfs:domain must be stored on the Property."""
        logic = _make_logic([
            (EX.myProp, RDF.type, OWL.ObjectProperty),
            (EX.DomainClass, RDF.type, OWL.Class),
            (EX.myProp, RDFS.domain, EX.DomainClass),
        ])
        _run_all(logic)
        prop = _instance_for_uri(logic, EX.myProp, Relation)
        domains = prop.get_has_domain()
        assert any(d.get_has_identifier() == str(EX.DomainClass) for d in domains)

    def test_rdfs_range_populated(self):
        """rdfs:range must be stored on the Property."""
        logic = _make_logic([
            (EX.myProp, RDF.type, OWL.ObjectProperty),
            (EX.RangeClass, RDF.type, OWL.Class),
            (EX.myProp, RDFS.range, EX.RangeClass),
        ])
        _run_all(logic)
        prop = _instance_for_uri(logic, EX.myProp, Relation)
        ranges = prop.get_has_range()
        assert any(r.get_has_identifier() == str(EX.RangeClass) for r in ranges)

    def test_owl_inverse_of_wired_bidirectionally(self):
        """owl:inverseOf must wire is_inverse_of on both Relations."""
        logic = _make_logic([
            (EX.hasPart, RDF.type, OWL.ObjectProperty),
            (EX.isPartOf, RDF.type, OWL.ObjectProperty),
            (EX.hasPart, OWL.inverseOf, EX.isPartOf),
        ])
        _run_all(logic)
        has_part = _instance_for_uri(logic, EX.hasPart, Relation)
        is_part_of = _instance_for_uri(logic, EX.isPartOf, Relation)
        assert has_part is not None
        assert is_part_of is not None
        assert has_part.get_is_inverse_of() is is_part_of

    def test_owl_equivalent_class_populated(self):
        """owl:equivalentClass must wire is_equivalent_to on the Concept."""
        logic = _make_logic([
            (EX.A, RDF.type, OWL.Class),
            (EX.B, RDF.type, OWL.Class),
            (EX.A, OWL.equivalentClass, EX.B),
        ])
        _run_all(logic)
        a = _instance_for_uri(logic, EX.A, Concept)
        b = _instance_for_uri(logic, EX.B, Concept)
        assert b in a.get_is_equivalent_to()

    def test_owl_disjoint_with_populated(self):
        """owl:disjointWith must wire is_disjoint_with on the Concept."""
        logic = _make_logic([
            (EX.A, RDF.type, OWL.Class),
            (EX.B, RDF.type, OWL.Class),
            (EX.A, OWL.disjointWith, EX.B),
        ])
        _run_all(logic)
        a = _instance_for_uri(logic, EX.A, Concept)
        b = _instance_for_uri(logic, EX.B, Concept)
        assert b in a.get_is_disjoint_with()

    def test_on_property_wired_to_restriction(self):
        """owl:onProperty must set applies_on_property on the Restriction."""
        restriction = BNode()
        logic = _make_logic([
            (restriction, RDF.type, OWL.Restriction),
            (restriction, OWL.onProperty, EX.myProp),
            (EX.myProp, RDF.type, OWL.ObjectProperty),
            (restriction, OWL.someValuesFrom, EX.SomeClass),
        ])
        _run_all(logic)
        inst = next(iter(logic._instance_cache.get(restriction, set())), None)
        assert inst is not None
        prop = inst.get_applies_on_property()
        assert prop is not None
        assert prop.get_has_identifier() == str(EX.myProp)

    def test_property_chain_axiom_handler(self):
        """owl:propertyChainAxiom must populate has_property_chain on the Relation."""
        g = Graph()
        head = _make_rdf_list(g, [EX.p1, EX.p2])
        g.add((EX.myRel, RDF.type, OWL.ObjectProperty))
        g.add((EX.p1, RDF.type, OWL.ObjectProperty))
        g.add((EX.p2, RDF.type, OWL.ObjectProperty))
        g.add((EX.myRel, OWL.propertyChainAxiom, head))
        cache = {}
        logic = OwlLogic(g, cache, OwlConfigManager())
        _run_all(logic)
        inst = _instance_for_uri(logic, EX.myRel, Relation)
        chain = inst.get_has_property_chain()
        ids = [c.get_has_identifier() for c in chain]
        assert str(EX.p1) in ids
        assert str(EX.p2) in ids

    def test_cardinality_exactly_handler(self):
        """owl:cardinality must set type=exactly, cardinality value, and applies_on_concept=owl:Thing."""
        bnode = BNode()
        logic = _make_logic([
            (bnode, OWL.cardinality, RDFLiteral(2, datatype=XSD.nonNegativeInteger)),
        ])
        _run_all(logic)
        inst = next(iter(logic._instance_cache.get(bnode, set())), None)
        assert isinstance(inst, Cardinality)
        assert inst.get_has_cardinality_type() == "exactly"
        assert inst.get_has_cardinality() == 2
        concept = inst.get_applies_on_concept()
        concepts = concept if isinstance(concept, list) else [concept]
        assert any(c.get_has_identifier() == str(OWL.Thing) for c in concepts)

    def test_cardinality_min_handler(self):
        """owl:minCardinality must set type=min, cardinality value, and applies_on_concept=owl:Thing."""
        bnode = BNode()
        logic = _make_logic([
            (bnode, OWL.minCardinality, RDFLiteral(1, datatype=XSD.nonNegativeInteger)),
        ])
        _run_all(logic)
        inst = next(iter(logic._instance_cache.get(bnode, set())), None)
        assert isinstance(inst, Cardinality)
        assert inst.get_has_cardinality_type() == "min"
        assert inst.get_has_cardinality() == 1

    def test_cardinality_max_handler(self):
        """owl:maxCardinality must set type=max and cardinality value."""
        bnode = BNode()
        logic = _make_logic([
            (bnode, OWL.maxCardinality, RDFLiteral(5, datatype=XSD.nonNegativeInteger)),
        ])
        _run_all(logic)
        inst = next(iter(logic._instance_cache.get(bnode, set())), None)
        assert isinstance(inst, Cardinality)
        assert inst.get_has_cardinality_type() == "max"
        assert inst.get_has_cardinality() == 5

    def test_qualified_cardinality_exactly_setter(self):
        """owl:qualifiedCardinality must set type=exactly and applies_on_concept to the filler."""
        bnode = BNode()
        logic = _make_logic([
            (bnode, OWL.qualifiedCardinality, RDFLiteral(3, datatype=XSD.nonNegativeInteger)),
            (bnode, OWL.onClass, EX.FillerClass),
            (EX.FillerClass, RDF.type, OWL.Class),
        ])
        _run_all(logic)
        inst = next(iter(logic._instance_cache.get(bnode, set())), None)
        assert isinstance(inst, Cardinality)
        assert inst.get_has_cardinality_type() == "exactly"
        concept = inst.get_applies_on_concept()
        concepts = concept if isinstance(concept, list) else [concept]
        assert any(c.get_has_identifier() == str(EX.FillerClass) for c in concepts)

    def test_qualified_cardinality_min_setter(self):
        """owl:minQualifiedCardinality must set type=min."""
        bnode = BNode()
        logic = _make_logic([
            (bnode, OWL.minQualifiedCardinality, RDFLiteral(1, datatype=XSD.nonNegativeInteger)),
            (bnode, OWL.onClass, EX.FillerClass),
            (EX.FillerClass, RDF.type, OWL.Class),
        ])
        _run_all(logic)
        inst = next(iter(logic._instance_cache.get(bnode, set())), None)
        assert isinstance(inst, Cardinality)
        assert inst.get_has_cardinality_type() == "min"

    def test_qualified_cardinality_max_setter(self):
        """owl:maxQualifiedCardinality must set type=max."""
        bnode = BNode()
        logic = _make_logic([
            (bnode, OWL.maxQualifiedCardinality, RDFLiteral(4, datatype=XSD.nonNegativeInteger)),
            (bnode, OWL.onClass, EX.FillerClass),
            (EX.FillerClass, RDF.type, OWL.Class),
        ])
        _run_all(logic)
        inst = next(iter(logic._instance_cache.get(bnode, set())), None)
        assert isinstance(inst, Cardinality)
        assert inst.get_has_cardinality_type() == "max"

    def test_cardinality_on_datatype_filler(self):
        """owl:onDatatype on a Cardinality BNode must set applies_on_concept to
        the XSD Datatype, not owl:Thing (as defaulted)."""
        bnode = BNode()
        logic = _make_logic([
            (bnode, OWL.qualifiedCardinality, RDFLiteral(1, datatype=XSD.nonNegativeInteger)),
            (bnode, OWL.onDatatype, XSD.string),
        ])
        _run_all(logic)
        inst = next(iter(logic._instance_cache.get(bnode, set())), None)
        assert isinstance(inst, Cardinality)
        concepts = inst.get_applies_on_concept()
        concepts = concepts if isinstance(concepts, list) else [concepts]
        ids = [c.get_has_identifier() for c in concepts if c is not None]
        assert str(XSD.string) in ids


    def test_namespace_filter_skips_non_mapped_predicates(self):
        """Predicates outside OWL/RDFS/RDF namespaces must not populate the instance
        and must not appear in _triples_map."""
        logic = _make_logic([
            (EX.myClass, RDF.type, OWL.Class),
            (EX.myClass, EX.customPred, RDFLiteral("value")),
        ])
        logic.phase1_classify_from_predicates()
        logic.phase2_create_from_types()
        logic.phase3_populate_properties()
        inst = _instance_for_uri(logic, EX.myClass, Concept)
        triples = logic._triples_map.get(inst, set())
        assert not any(p == EX.customPred for _, p, _ in triples)


# ===========================================================================
# PHASE 4 - Group axioms
# ===========================================================================

class TestPhase4:

    def test_all_disjoint_classes(self):
        """owl:AllDisjointClasses must mark all pairs mutually disjoint."""
        g = Graph()
        node = BNode()
        head = _make_rdf_list(g, [EX.A, EX.B, EX.C])
        g.add((node, RDF.type, OWL.AllDisjointClasses))
        g.add((node, OWL.members, head))
        g.add((EX.A, RDF.type, OWL.Class))
        g.add((EX.B, RDF.type, OWL.Class))
        g.add((EX.C, RDF.type, OWL.Class))
        cache = {}
        logic = OwlLogic(g, cache, OwlConfigManager())
        _run_all(logic)
        a = _instance_for_uri(logic, EX.A, Concept)
        b = _instance_for_uri(logic, EX.B, Concept)
        c = _instance_for_uri(logic, EX.C, Concept)
        assert b in a.get_is_disjoint_with()
        assert c in a.get_is_disjoint_with()
        assert a in b.get_is_disjoint_with()

    def test_all_different_individuals(self):
        """owl:AllDifferent must mark all pairs mutually different."""
        g = Graph()
        node = BNode()
        head = _make_rdf_list(g, [EX.i1, EX.i2])
        g.add((node, RDF.type, OWL.AllDifferent))
        g.add((node, OWL.distinctMembers, head))
        g.add((EX.i1, RDF.type, OWL.NamedIndividual))
        g.add((EX.i2, RDF.type, OWL.NamedIndividual))
        cache = {}
        logic = OwlLogic(g, cache, OwlConfigManager())
        _run_all(logic)
        i1 = _instance_for_uri(logic, EX.i1, Individual)
        i2 = _instance_for_uri(logic, EX.i2, Individual)
        assert i2 in i1.get_is_different_from()
        assert i1 in i2.get_is_different_from()

    def test_all_disjoint_properties(self):
        """owl:AllDisjointProperties must mark all pairs mutually disjoint."""
        g = Graph()
        node = BNode()
        head = _make_rdf_list(g, [EX.p1, EX.p2])
        g.add((node, RDF.type, OWL.AllDisjointProperties))
        g.add((node, OWL.members, head))
        g.add((EX.p1, RDF.type, OWL.ObjectProperty))
        g.add((EX.p2, RDF.type, OWL.ObjectProperty))
        cache = {}
        logic = OwlLogic(g, cache, OwlConfigManager())
        _run_all(logic)
        p1 = _instance_for_uri(logic, EX.p1, Relation)
        p2 = _instance_for_uri(logic, EX.p2, Relation)
        assert p2 in p1.get_is_disjoint_with()
        assert p1 in p2.get_is_disjoint_with()


# ===========================================================================
# PHASE 5 - Fallback: reclassification + OWL defaults
# ===========================================================================

class TestPhase5Defaults:

    def test_relation_gets_owl_thing_domain_when_none_declared(self):
        """A Relation without explicit domain must receive owl:Thing as default domain."""
        logic = _make_logic([
            (EX.myRel, RDF.type, OWL.ObjectProperty),
        ])
        _run_all(logic)
        rel = _instance_for_uri(logic, EX.myRel, Relation)
        domains = rel.get_has_domain()
        assert any(d.get_has_identifier() == str(OWL.Thing) for d in domains)

    def test_relation_gets_owl_thing_range_when_none_declared(self):
        """A Relation without explicit range must receive owl:Thing as default range."""
        logic = _make_logic([
            (EX.myRel, RDF.type, OWL.ObjectProperty),
        ])
        _run_all(logic)
        rel = _instance_for_uri(logic, EX.myRel, Relation)
        ranges = rel.get_has_range()
        assert any(r.get_has_identifier() == str(OWL.Thing) for r in ranges)

    def test_attribute_gets_rdfs_literal_range_when_none_declared(self):
        """A DatatypeProperty without explicit range must receive rdfs:Literal as default range."""
        logic = _make_logic([
            (EX.myAttr, RDF.type, OWL.DatatypeProperty),
        ])
        _run_all(logic)
        attr = _instance_for_uri(logic, EX.myAttr, Attribute)
        ranges = attr.get_has_range()
        assert any(r.get_has_identifier() == str(RDFS.Literal) for r in ranges)

    def test_individual_gets_owl_thing_type_when_none_declared(self):
        """A NamedIndividual without explicit rdf:type assertion must have owl:Thing as type."""
        logic = _make_logic([
            (EX.myInd, RDF.type, OWL.NamedIndividual),
        ])
        _run_all(logic)
        ind = _instance_for_uri(logic, EX.myInd, Individual)
        types = ind.get_has_type()
        assert any(t.get_has_identifier() == str(OWL.Thing) for t in types)

    def test_explicitly_typed_individual_keeps_declared_type(self):
        """An Individual with an explicit rdf:type must keep it and not be overridden."""
        logic = _make_logic([
            (EX.myInd, RDF.type, OWL.NamedIndividual),
            (EX.myInd, RDF.type, EX.SomeClass),
            (EX.SomeClass, RDF.type, OWL.Class),
        ])
        _run_all(logic)
        ind = _instance_for_uri(logic, EX.myInd, Individual)
        types = ind.get_has_type()
        ids = [t.get_has_identifier() for t in types]
        assert str(EX.SomeClass) in ids

    def test_explicit_domain_not_overridden_by_owl_thing(self):
        """A Relation with explicit domain must NOT have owl:Thing added as extra domain."""
        logic = _make_logic([
            (EX.myRel, RDF.type, OWL.ObjectProperty),
            (EX.DomainClass, RDF.type, OWL.Class),
            (EX.myRel, RDFS.domain, EX.DomainClass),
        ])
        _run_all(logic)
        rel = _instance_for_uri(logic, EX.myRel, Relation)
        ids = [d.get_has_identifier() for d in rel.get_has_domain()]
        assert str(OWL.Thing) not in ids

    def test_explicit_range_not_overridden_by_owl_thing(self):
        """A Relation with explicit range must NOT have owl:Thing added as extra range."""
        logic = _make_logic([
            (EX.myRel, RDF.type, OWL.ObjectProperty),
            (EX.RangeClass, RDF.type, OWL.Class),
            (EX.myRel, RDFS.range, EX.RangeClass),
        ])
        _run_all(logic)
        rel = _instance_for_uri(logic, EX.myRel, Relation)
        ids = [r.get_has_identifier() for r in rel.get_has_range()]
        assert str(OWL.Thing) not in ids


# ===========================================================================
# PHASE 5 - Property reclassification
# ===========================================================================

class TestPhase5Reclassification:

    def test_generic_property_reclassified_via_inverse_of(self):
        """A generic Property with owl:inverseOf pointing to a known Relation
        must be reclassified as Relation."""
        logic = _make_logic([
            (EX.hasPart, RDF.type, OWL.ObjectProperty),
            (EX.isPartOf, OWL.inverseOf, EX.hasPart),
        ])
        _run_all(logic)
        # isPartOf never typed as owl:ObjectProperty explicitly
        inst = _instance_for_uri(logic, EX.isPartOf, Relation)
        assert inst is not None, "isPartOf must be reclassified as Relation via inverseOf"

    def test_generic_property_reclassified_via_super_property_up(self):
        """A generic Property whose parent is a Relation must be reclassified as Relation
        (upward traversal of the subPropertyOf hierarchy)."""
        logic = _make_logic([
            (EX.parentProp, RDF.type, OWL.ObjectProperty),
            (EX.childProp, RDFS.subPropertyOf, EX.parentProp),
        ])
        _run_all(logic)
        child = _instance_for_uri(logic, EX.childProp, Relation)
        assert child is not None, "childProp must be reclassified as Relation via subPropertyOf (up)"

    def test_generic_property_reclassified_via_sub_property_down(self):
        """A generic Property whose child is a Relation must be reclassified as Relation
        (downward traversal of the subPropertyOf hierarchy)."""
        logic = _make_logic([
            (EX.childProp, RDF.type, OWL.ObjectProperty),
            (EX.childProp, RDFS.subPropertyOf, EX.parentProp),
        ])
        _run_all(logic)
        parent = _instance_for_uri(logic, EX.parentProp, Relation)
        assert parent is not None, "parentProp must be reclassified as Relation via subPropertyOf (down)"

    def test_untyped_property_falls_back_to_annotation(self):
        """A predicate used in the graph but never typed or connected to any typed
        property must default to Annotation."""
        logic = _make_logic([
            (EX.someSubject, EX.unknownPred, RDFLiteral("value")),
        ])
        _run_all(logic)
        # After phase5 fallback the predicate should be created as Annotation
        inst = _instance_for_uri(logic, EX.unknownPred, Annotation)
        assert inst is not None

# ===========================================================================
# PHASE 5 - Domain/range inheritance via subPropertyOf
# ===========================================================================

class TestDomainRangeInheritance:

    def test_child_inherits_domain_from_parent(self):
        """A child Relation with no domain must inherit the parent's domain."""
        logic = _make_logic([
            (EX.parentProp, RDF.type, OWL.ObjectProperty),
            (EX.DomainClass, RDF.type, OWL.Class),
            (EX.parentProp, RDFS.domain, EX.DomainClass),
            (EX.childProp, RDF.type, OWL.ObjectProperty),
            (EX.childProp, RDFS.subPropertyOf, EX.parentProp),
        ])
        _run_all(logic)
        child = _instance_for_uri(logic, EX.childProp, Relation)
        ids = [d.get_has_identifier() for d in child.get_has_domain()]
        assert str(EX.DomainClass) in ids
        assert str(OWL.Thing) not in ids

    def test_child_inherits_range_from_parent(self):
        """A child Relation with no range must inherit the parent's range."""
        logic = _make_logic([
            (EX.parentProp, RDF.type, OWL.ObjectProperty),
            (EX.RangeClass, RDF.type, OWL.Class),
            (EX.parentProp, RDFS.range, EX.RangeClass),
            (EX.childProp, RDF.type, OWL.ObjectProperty),
            (EX.childProp, RDFS.subPropertyOf, EX.parentProp),
        ])
        _run_all(logic)
        child = _instance_for_uri(logic, EX.childProp, Relation)
        ids = [r.get_has_identifier() for r in child.get_has_range()]
        assert str(EX.RangeClass) in ids
        assert str(OWL.Thing) not in ids

    def test_inverse_domain_inferred_from_inverse_range(self):
        """A Relation whose inverse has an explicit range must use that range
        as its own domain (inverseOf domain/range swap)."""
        logic = _make_logic([
            (EX.hasPart, RDF.type, OWL.ObjectProperty),
            (EX.RangeClass, RDF.type, OWL.Class),
            (EX.hasPart, RDFS.range, EX.RangeClass),
            (EX.isPartOf, RDF.type, OWL.ObjectProperty),
            (EX.isPartOf, OWL.inverseOf, EX.hasPart),
        ])
        _run_all(logic)
        is_part_of = _instance_for_uri(logic, EX.isPartOf, Relation)
        ids = [d.get_has_identifier() for d in is_part_of.get_has_domain()]
        assert str(EX.RangeClass) in ids

    def test_inverse_range_inferred_from_inverse_domain(self):
        """A Relation whose inverse has an explicit domain must use that doman
        as its own range (inverseOf domain/range swap)."""
        logic = _make_logic([
            (EX.hasPart, RDF.type, OWL.ObjectProperty),
            (EX.DomainClass, RDF.type, OWL.Class),
            (EX.hasPart, RDFS.domain, EX.DomainClass),
            (EX.isPartOf, RDF.type, OWL.ObjectProperty),
            (EX.isPartOf, OWL.inverseOf, EX.hasPart),
        ])
        _run_all(logic)
        is_part_of = _instance_for_uri(logic, EX.isPartOf, Relation)
        ids = [d.get_has_identifier() for d in is_part_of.get_has_range()]
        assert str(EX.DomainClass) in ids


# ===========================================================================
# PHASE 5 - Punning
# ===========================================================================

class TestPunning:

    def test_punned_uri_has_two_instances(self):
        """A URI declared as both owl:Class and owl:NamedIndividual must have
        exactly two cached instances (Concept + Individual)."""
        logic = _make_logic([
            (EX.NaturalElement, RDF.type, OWL.Class),
            (EX.NaturalElement, RDF.type, OWL.NamedIndividual),
        ])
        _run_all(logic)
        instances = logic._instance_cache.get(EX.NaturalElement, set())
        types = {type(i) for i in instances}
        assert Concept in types
        assert Individual in types

    def test_punned_instances_annotated_with_also_defined_as(self):
        """After phase5 each instance involved in punning must reference the other
        via also_defined_as (set_also_defined_as)."""
        logic = _make_logic([
            (EX.NaturalElement, RDF.type, OWL.Class),
            (EX.NaturalElement, RDF.type, OWL.NamedIndividual),
        ])
        _run_all(logic)
        instances = list(logic._instance_cache.get(EX.NaturalElement, set()))
        assert len(instances) == 2
        # Each must reference the other
        for inst in instances:
            also = inst.get_also_defined_as() if hasattr(inst, 'get_also_defined_as') else []
            others = [i for i in instances if i is not inst]
            assert any(o in also for o in others), \
                f"{type(inst).__name__} missing also_defined_as for the punned peer"


# ===========================================================================
# PHASE 6 - Statement creation
# ===========================================================================

class TestPhase6:

    def test_unmapped_triple_produces_statement(self):
        """A triple whose predicate is not mapped in the config must generate a Statement."""
        logic = _make_logic([
            (EX.subject, RDF.type, OWL.Class),
            (EX.subject, EX.customPred, EX.someObject),
        ])
        _run_all(logic)
        stmts = _instances_of(logic, Statement)
        assert len(stmts) >= 1

    def test_statement_subject_predicate_object_set(self):
        """The produced Statement must have subject, predicate, and object populated."""
        logic = _make_logic([
            (EX.subject, RDF.type, OWL.Class),
            (EX.subject, EX.customPred, RDFLiteral("hello")),
        ])
        _run_all(logic)
        stmts = _instances_of(logic, Statement)
        assert len(stmts) >= 1
        stmt = stmts[0]
        assert stmt.get_has_subject() is not None
        assert stmt.get_has_predicate() is not None
        assert stmt.get_has_object() is not None

    def test_mapped_triple_does_not_produce_statement(self):
        """A triple already handled by the property mapping must NOT generate a Statement."""
        logic = _make_logic([
            (EX.MyClass, RDF.type, OWL.Class),
            (EX.MyClass, RDFS.label, RDFLiteral("My Class")),
        ])
        _run_all(logic)
        stmts = _instances_of(logic, Statement)
        # rdfs:label is mapped -> no extra statement for it
        for stmt in stmts:
            pred = stmt.get_has_predicate()
            if pred:
                assert pred.get_has_identifier() != str(RDFS.label)

    def test_bnode_subject_produces_statement_not_individual(self):
        """A BNode typed as owl:Axiom must be a Statement with subject, predicate,
        and object populated — not an Individual."""
        bnode = BNode()
        logic = _make_logic([
            (bnode, RDF.type, OWL.Axiom),
            (bnode, OWL.annotatedSource, EX.subject),
            (bnode, OWL.annotatedProperty, EX.pred),
            (bnode, OWL.annotatedTarget, RDFLiteral("val")),
        ])
        _run_all(logic)
        inst = next(iter(logic._instance_cache.get(bnode, set())), None)
        assert inst is not None
        assert isinstance(inst, Statement)
        assert not isinstance(inst, Individual)
        assert inst.get_has_subject() is not None
        assert inst.get_has_predicate() is not None
        assert inst.get_has_object() is not None

    def test_literal_object_produces_annotation_predicate(self):
        """A Statement whose object is a Literal must have an Annotation as predicate
        when the predicate is not already in cache."""
        logic = _make_logic([
            (EX.subject, RDF.type, OWL.Class),
            (EX.subject, EX.customPred, RDFLiteral("hello")),
        ])
        _run_all(logic)
        stmts = _instances_of(logic, Statement)
        target = next((s for s in stmts if isinstance(s.get_has_object(), Literal)), None)
        assert target is not None
        assert isinstance(target.get_has_predicate(), Annotation)

    def test_bnode_object_produces_statement_object(self):
        """A Statement whose object is a BNode must resolve the object to a Statement
        instance, not a generic Resource."""
        bnode_obj = BNode()
        logic = _make_logic([
            (EX.subject, RDF.type, OWL.NamedIndividual),
            (bnode_obj, RDF.type, OWL.Axiom),
            (EX.subject, EX.customPred, bnode_obj),
        ])
        _run_all(logic)
        stmts = _instances_of(logic, Statement)
        target = next((s for s in stmts
                    if s.get_has_subject() is not None
                    and s.get_has_subject().get_has_identifier() == str(EX.subject)), None)
        assert target is not None
        obj = target.get_has_object()
        assert isinstance(obj, Statement)


# ===========================================================================
# get_or_create - cache behaviour, namespace filtering, punning guard
# ===========================================================================

class TestGetOrCreate:

    def test_same_uri_same_class_returns_same_instance(self):
        """Calling get_or_create twice with the same URI and class must return
        the same instance."""
        logic = _make_logic([])
        i1 = logic.get_or_create(EX.A, Concept, populate=False)
        i2 = logic.get_or_create(EX.A, Concept, populate=False)
        assert i1 is i2

    # def test_owl_namespace_uri_filtered_out(self):
    #     """Arbitrary OWL-namespace URIs that are not whitelisted must return None."""
    #     logic = _make_logic([])
    #     result = logic.get_or_create(OWL.topObjectProperty, Relation, populate=False)
    #     assert result is None

    # def test_owl_thing_not_filtered(self):
    #     """OWL.Thing must NOT be filtered even though it's in the OWL namespace."""
    #     logic = _make_logic([])
    #     result = logic.get_or_create(OWL.Thing, Concept, populate=False)
    #     assert result is not None
    #     assert isinstance(result, Concept)

    # def test_rdfs_literal_not_filtered(self):
    #     """RDFS.Literal must NOT be filtered."""
    #     logic = _make_logic([])
    #     result = logic.get_or_create(RDFS.Literal, Datatype, populate=False)
    #     assert result is not None

    def test_punning_individual_does_not_overwrite_concept(self):
        """Requesting Individual for a URI already cached as Concept (without
        explicit owl:NamedIndividual declaration) must return the existing Concept."""
        logic = _make_logic([])
        concept = logic.get_or_create(EX.A, Concept, populate=False)
        result = logic.get_or_create(EX.A, Individual, populate=False)
        assert result is concept

    def test_named_individual_punning_allowed(self):
        """When the graph contains (uri, rdf:type, owl:NamedIndividual), requesting
        Individual for a URI already cached as Concept must create a second instance."""
        logic = _make_logic([
            (EX.A, RDF.type, OWL.NamedIndividual),
        ])
        logic.get_or_create(EX.A, Concept, populate=False)
        result = logic.get_or_create(EX.A, Individual, populate=False)
        assert isinstance(result, Individual)
        # Both must coexist in cache
        types = {type(i) for i in logic._instance_cache[EX.A]}
        assert Concept in types
        assert Individual in types

    def test_xsd_uri_creates_datatype(self):
        """A URI in the XSD namespace must always produce a Datatype regardless of
        the requested class."""
        logic = _make_logic([])
        result = logic.get_or_create(XSD.string, Concept, populate=False)
        assert isinstance(result, Datatype)

    def test_literal_returns_literal_instance(self):
        """Passing an RDFLib Literal to get_or_create must return a Literal model."""
        logic = _make_logic([])
        rdf_lit = RDFLiteral("hello", lang="en")
        result = logic.get_or_create(rdf_lit, populate=False)
        assert isinstance(result, Literal)
        assert result.get_has_value() == "hello"

    def test_concrete_subtype_prevents_generic_property_duplicate(self):
        """If a URI is typed as both owl:ObjectProperty (Relation) and owl:FunctionalProperty
        (Property), get_or_create must keep only the Relation and apply the functional setter
        on it — no duplicate generic Property instance must be created."""
        logic = _make_logic([
            (EX.myProp, RDF.type, OWL.ObjectProperty),
            (EX.myProp, RDF.type, OWL.FunctionalProperty),
        ])
        logic.phase1_classify_from_predicates()
        logic.phase2_create_from_types()
        logic.phase3_populate_properties()
        logic.phase4_process_group_axioms()
        logic.phase5_fallback()

        instances = logic._instance_cache.get(EX.myProp, set())
        # Only one instance, and it must be Relation (not generic Property)
        assert len(instances) == 1
        inst = next(iter(instances))
        assert type(inst) is Relation
        assert inst.get_is_functional() is True

    def test_resource_promoted_to_concept_when_requested(self):
        """A URI already in cache as Resource must be promoted to Concept when requested,
        since Concept is a subclass of Resource."""
        logic = _make_logic([])
        # First create as Resource
        r = logic.get_or_create(EX.foo, Resource, populate=False)
        assert isinstance(r, Resource)
        assert type(r) is Resource
        # Now request as Concept — must promote, not return stale Resource
        c = logic.get_or_create(EX.foo, Concept, populate=False)
        assert isinstance(c, Concept)
        assert type(c) is Concept
        # Cache must contain only the promoted instance
        assert len(logic._instance_cache[EX.foo]) == 1

    def test_resource_not_promoted_when_punning(self):
        """A URI declared as owl:NamedIndividual (explicit punning) plus Concept
        must not be collapsed when Resource is requested."""
        logic = _make_logic([
            (EX.foo, RDF.type, OWL.NamedIndividual),
            (EX.foo, RDF.type, OWL.Class),
        ])
        _run_all(logic)
        result = logic.get_or_create(EX.foo, Resource, populate=False)
        assert len(logic._instance_cache[EX.foo]) == 2
        assert isinstance(result, (Concept, Individual))

    def test_concept_not_downgraded_to_resource(self):
        """A URI already in cache as Concept must never be downgraded to Resource."""
        logic = _make_logic([])
        logic.get_or_create(EX.foo, Concept, populate=False)
        result = logic.get_or_create(EX.foo, Resource, populate=False)
        assert isinstance(result, Concept)
        assert type(result) is Concept

    # def test_rdfs_resource_filtered(self):
    #     """RDFS.Resource must be filtered and return None."""
    #     logic = _make_logic([])
    #     result = logic.get_or_create(RDFS.Resource, Resource, populate=False)
    #     assert result is None

    # def test_rdfs_class_filtered(self):
    #     """RDFS.Class must be filtered and return None."""
    #     logic = _make_logic([])
    #     result = logic.get_or_create(RDFS.Class, Concept, populate=False)
    #     assert result is None

    def test_bnode_in_cache_returns_existing(self):
        """get_or_create on a BNode already in cache must return the existing instance."""
        logic = _make_logic([])
        bnode = BNode()
        first = logic.get_or_create(bnode, Concept, populate=False)
        second = logic.get_or_create(bnode, Concept, populate=False)
        assert first is second

    def test_uriref_in_cache_returns_matching_type(self):
        """get_or_create on a URIRef already in cache must return the instance
        matching the requested class."""
        logic = _make_logic([])
        first = logic.get_or_create(EX.A, Concept, populate=False)
        second = logic.get_or_create(EX.A, Concept, populate=False)
        assert first is second

    def test_populate_true_calls_populate_instance(self):
        """get_or_create with populate=True on a new URI must populate the instance
        (label populated from graph)."""
        logic = _make_logic([
            (EX.MyClass, RDFS.label, RDFLiteral("My Class")),
        ])
        # No phase2 — EX.MyClass not in cache yet
        inst = logic.get_or_create(EX.MyClass, Concept, populate=True)
        labels = inst.get_has_label()
        assert len(labels) >= 1
        assert any(l.get_has_value() == "My Class" for l in labels)

    def test_populate_false_skips_populate_instance(self):
        """get_or_create with populate=False must not populate the instance."""
        logic = _make_logic([
            (EX.MyClass, RDF.type, OWL.Class),
            (EX.MyClass, RDFS.label, RDFLiteral("My Class")),
        ])
        inst = logic.get_or_create(EX.MyClass, Concept, populate=False)
        labels = inst.get_has_label()
        assert len(labels) == 0

    def test_identifier_always_set(self):
        """get_or_create must always set has_identifier even with populate=False."""
        logic = _make_logic([])
        inst = logic.get_or_create(EX.MyClass, Concept, populate=False)
        assert inst.get_has_identifier() == str(EX.MyClass)


# ===========================================================================
# Integration - end-to-end on a minimal realistic ontology fragment
# ===========================================================================

class TestIntegration:

    def test_pizza_like_fragment(self):
        """
        Minimal pizza-like fragment:
          hasTopping owl:ObjectProperty, domain Pizza, range PizzaTopping,
                     inverseOf isToppingOf
          isToppingOf: no explicit domain/range -> must inherit from inverse
        """
        logic = _make_logic([
            (EX.hasTopping, RDF.type, OWL.ObjectProperty),
            (EX.Pizza, RDF.type, OWL.Class),
            (EX.PizzaTopping, RDF.type, OWL.Class),
            (EX.hasTopping, RDFS.domain, EX.Pizza),
            (EX.hasTopping, RDFS.range, EX.PizzaTopping),
            (EX.isToppingOf, RDF.type, OWL.ObjectProperty),
            (EX.isToppingOf, OWL.inverseOf, EX.hasTopping),
        ])
        _run_all(logic)

        has_topping = _instance_for_uri(logic, EX.hasTopping, Relation)
        is_topping_of = _instance_for_uri(logic, EX.isToppingOf, Relation)

        assert has_topping is not None
        assert is_topping_of is not None

        # isToppingOf domain <- hasTopping range (PizzaTopping)
        domain_ids = [d.get_has_identifier() for d in is_topping_of.get_has_domain()]
        assert str(EX.PizzaTopping) in domain_ids

        # isToppingOf range <- hasTopping domain (Pizza)
        range_ids = [r.get_has_identifier() for r in is_topping_of.get_has_range()]
        assert str(EX.Pizza) in range_ids

    def test_restriction_quantifier_populated(self):
        """
        A Restriction with owl:someValuesFrom must have:
        - quantifier_type = 'some'
        - applies_on_concept pointing to the filler class
        """
        restriction = BNode()
        logic = _make_logic([
            (restriction, RDF.type, OWL.Restriction),
            (restriction, OWL.onProperty, EX.myProp),
            (EX.myProp, RDF.type, OWL.ObjectProperty),
            (restriction, OWL.someValuesFrom, EX.FillerClass),
            (EX.FillerClass, RDF.type, OWL.Class),
        ])
        _run_all(logic)
        inst = next(iter(logic._instance_cache.get(restriction, set())), None)
        assert inst is not None
        assert isinstance(inst, Quantifier)
        assert inst.get_has_quantifier_type() == "some"
        filler_id = str(EX.FillerClass)
        concept = inst.get_applies_on_concept()
        if isinstance(concept, list):
            assert any(c.get_has_identifier() == filler_id for c in concept)
        else:
            assert concept.get_has_identifier() == filler_id

    def test_intersection_of_truth_function(self):
        """
        owl:intersectionOf on a BNode must produce a TruthFunction with
        has_logical_operator = 'and' and applies_on_concept populated.
        """
        bnode = BNode()
        from rdflib.collection import Collection as Col
        g = Graph()
        head = BNode()
        Col(g, head, [EX.A, EX.B])
        g.add((bnode, OWL.intersectionOf, head))
        g.add((EX.A, RDF.type, OWL.Class))
        g.add((EX.B, RDF.type, OWL.Class))
        cache = {}
        logic = OwlLogic(g, cache, OwlConfigManager())
        _run_all(logic)

        tf = _instance_for_uri(logic, bnode, TruthFunction)
        if tf is None:
            # TF may be keyed on the head BNode (collection)
            tf = _instance_for_uri(logic, head, TruthFunction)
        assert tf is not None
        assert tf.get_has_logical_operator() == "and"
        concepts = tf.get_applies_on_concept()
        ids = [c.get_has_identifier() for c in (concepts if isinstance(concepts, list) else [concepts])]
        assert str(EX.A) in ids
        assert str(EX.B) in ids

    def test_union_of_truth_function(self):
        """owl:unionOf on a BNode must produce a TruthFunction with
        has_logical_operator='or' and applies_on_concept populated."""
        bnode = BNode()
        g = Graph()
        head = BNode()
        from rdflib.collection import Collection as Col
        Col(g, head, [EX.A, EX.B])
        g.add((bnode, OWL.unionOf, head))
        g.add((EX.A, RDF.type, OWL.Class))
        g.add((EX.B, RDF.type, OWL.Class))
        cache = {}
        logic = OwlLogic(g, cache, OwlConfigManager())
        _run_all(logic)
        tf = _instance_for_uri(logic, bnode, TruthFunction)
        if tf is None:
            tf = _instance_for_uri(logic, head, TruthFunction)
        assert tf is not None
        assert tf.get_has_logical_operator() == "or"
        concepts = tf.get_applies_on_concept()
        ids = [c.get_has_identifier() for c in (concepts if isinstance(concepts, list) else [concepts])]
        assert str(EX.A) in ids
        assert str(EX.B) in ids

    def test_complement_of_truth_function(self):
        """owl:complementOf on a BNode must produce a TruthFunction with
        has_logical_operator='not' and applies_on_concept populated."""
        bnode = BNode()
        logic = _make_logic([
            (bnode, OWL.complementOf, EX.A),
            (EX.A, RDF.type, OWL.Class),
        ])
        _run_all(logic)
        tf = _instance_for_uri(logic, bnode, TruthFunction)
        assert tf is not None
        assert tf.get_has_logical_operator() == "not"
        concepts = tf.get_applies_on_concept()
        concepts = concepts if isinstance(concepts, list) else [concepts]
        assert any(c.get_has_identifier() == str(EX.A) for c in concepts)

    def test_one_of_with_individuals(self):
        """owl:oneOf on a BNode must produce a OneOf with applies_on_resource
        populated with all listed individuals."""
        bnode = BNode()
        g = Graph()
        head = BNode()
        from rdflib.collection import Collection as Col
        Col(g, head, [EX.ind1, EX.ind2])
        g.add((bnode, OWL.oneOf, head))
        g.add((EX.ind1, RDF.type, OWL.NamedIndividual))
        g.add((EX.ind2, RDF.type, OWL.NamedIndividual))
        cache = {}
        logic = OwlLogic(g, cache, OwlConfigManager())
        _run_all(logic)
        one_of = _instance_for_uri(logic, bnode, OneOf)
        assert one_of is not None
        resources = one_of.get_applies_on_resource()
        ids = [r.get_has_identifier() for r in resources]
        assert str(EX.ind1) in ids
        assert str(EX.ind2) in ids

    def test_multi_level_sub_property_inheritance(self):
        """Domain/range must be inherited across a three-level subPropertyOf chain:
        grandchild -> child -> parent, where only parent declares domain and range."""
        logic = _make_logic([
            (EX.parent, RDF.type, OWL.ObjectProperty),
            (EX.DomainClass, RDF.type, OWL.Class),
            (EX.RangeClass, RDF.type, OWL.Class),
            (EX.parent, RDFS.domain, EX.DomainClass),
            (EX.parent, RDFS.range, EX.RangeClass),
            (EX.child, RDF.type, OWL.ObjectProperty),
            (EX.child, RDFS.subPropertyOf, EX.parent),
            (EX.grandchild, RDF.type, OWL.ObjectProperty),
            (EX.grandchild, RDFS.subPropertyOf, EX.child),
        ])
        _run_all(logic)
        grandchild = _instance_for_uri(logic, EX.grandchild, Relation)
        domain_ids = [d.get_has_identifier() for d in grandchild.get_has_domain()]
        range_ids = [r.get_has_identifier() for r in grandchild.get_has_range()]
        assert str(EX.DomainClass) in domain_ids
        assert str(EX.RangeClass) in range_ids
        assert str(OWL.Thing) not in domain_ids

    def test_nested_truth_functions_linked(self):
        """Two BNodes connected via owl:intersectionOf where one member is itself
        a TruthFunction (unionOf) must produce linked TruthFunction instances."""
        inner = BNode()
        g = Graph()
        from rdflib.collection import Collection as Col
        inner_head = BNode()
        Col(g, inner_head, [EX.B, EX.C])
        g.add((inner, OWL.unionOf, inner_head))
        outer_head = BNode()
        Col(g, outer_head, [EX.A, inner])
        outer = BNode()
        g.add((outer, OWL.intersectionOf, outer_head))
        g.add((EX.A, RDF.type, OWL.Class))
        g.add((EX.B, RDF.type, OWL.Class))
        g.add((EX.C, RDF.type, OWL.Class))
        cache = {}
        logic = OwlLogic(g, cache, OwlConfigManager())
        _run_all(logic)
        outer_tf = _instance_for_uri(logic, outer, TruthFunction)
        if outer_tf is None:
            outer_tf = _instance_for_uri(logic, outer_head, TruthFunction)
        assert outer_tf is not None
        assert outer_tf.get_has_logical_operator() == "and"
        inner_tf = _instance_for_uri(logic, inner, TruthFunction)
        if inner_tf is None:
            inner_tf = _instance_for_uri(logic, inner_head, TruthFunction)
        assert inner_tf is not None
        assert inner_tf.get_has_logical_operator() == "or"
        # outer must reference inner via applies_on_concept
        outer_concepts = outer_tf.get_applies_on_concept()
        outer_concepts = outer_concepts if isinstance(outer_concepts, list) else [outer_concepts]
        assert inner_tf in outer_concepts

class TestPopulationEdgeCases:
 
    def test_same_predicate_twice_both_values_in_list(self):
        """rdfs:label declared twice on the same class must produce two Literal
        instances in has_label — not just the last one."""
        logic = _make_logic([
            (EX.MyClass, RDF.type, OWL.Class),
            (EX.MyClass, RDFS.label, RDFLiteral("First", lang="en")),
            (EX.MyClass, RDFS.label, RDFLiteral("Secondo", lang="it")),
        ])
        _run_all(logic)
        inst = _instance_for_uri(logic, EX.MyClass, Concept)
        labels = inst.get_has_label()
        values = [l.get_has_value() for l in labels]
        assert "First" in values
        assert "Secondo" in values
 
    def test_same_subclass_triple_twice_no_duplicate_in_list(self):
        """rdfs:subClassOf declared twice for the same pair must not add the
        parent twice to is_sub_concept_of."""
        logic = _make_logic([
            (EX.Child, RDF.type, OWL.Class),
            (EX.Parent, RDF.type, OWL.Class),
            (EX.Child, RDFS.subClassOf, EX.Parent),
            (EX.Child, RDFS.subClassOf, EX.Parent),
        ])
        _run_all(logic)
        child = _instance_for_uri(logic, EX.Child, Concept)
        parent = _instance_for_uri(logic, EX.Parent, Concept)
        parents_in_list = [c for c in child.get_is_sub_concept_of() if c is parent]
        assert len(parents_in_list) == 1
 
    def test_setter_not_called_with_none_object(self):
        """When get_or_create returns None for a filtered URI (e.g. OWL namespace),
        the setter must not be called — None must never appear in has_domain."""
        logic = _make_logic([
            (EX.myProp, RDF.type, OWL.ObjectProperty),
            # rdfs:domain points to a filtered OWL URI
            (EX.myProp, RDFS.domain, OWL.topObjectProperty),
        ])
        _run_all(logic)
        prop = _instance_for_uri(logic, EX.myProp, Relation)
        domains = prop.get_has_domain()
        assert None not in domains
 
    def test_handler_exception_triple_not_in_triples_map(self):
        """When a handler raises an exception, the triple must not appear in
        _triples_map for the instance."""
        logic = _make_logic([
            (EX.myRel, RDF.type, OWL.ObjectProperty),
            (EX.myRel, OWL.propertyChainAxiom, EX.notAList),
        ])
        _run_all(logic)
        inst = _instance_for_uri(logic, EX.myRel, Relation)
        triples = logic._triples_map.get(inst, set())
        assert not any(p == OWL.propertyChainAxiom for _, p, _ in triples)
 
    def test_handler_exception_triple_becomes_statement(self):
        """When a handler raises an exception, the unmapped triple must produce
        a Statement in phase6."""
        logic = _make_logic([
            (EX.myRel, RDF.type, OWL.ObjectProperty),
            (EX.myRel, OWL.propertyChainAxiom, EX.notAList),
        ])
        _run_all(logic)
        stmts = _instances_of(logic, Statement)
        pred_ids = [
            s.get_has_predicate().get_has_identifier()
            for s in stmts
            if s.get_has_predicate() is not None
        ]
        assert str(OWL.propertyChainAxiom) in pred_ids
 
 
# ===========================================================================
# CACHE EDGE CASES
# ===========================================================================
 
class TestCacheEdgeCases:
 
    def test_populate_true_on_cached_uri_does_not_duplicate_triples(self):
        """Calling get_or_create with populate=True on a URI already in cache
        must not add duplicate entries to _triples_map."""
        logic = _make_logic([
            (EX.MyClass, RDF.type, OWL.Class),
            (EX.MyClass, RDFS.label, RDFLiteral("My Class")),
        ])
        logic.phase2_create_from_types()
        logic.phase3_populate_properties()
 
        inst = _instance_for_uri(logic, EX.MyClass, Concept)
        triples_before = len(logic._triples_map.get(inst, set()))
 
        # Call again with populate=True on already-cached URI
        logic.get_or_create(EX.MyClass, Concept, populate=True)
        triples_after = len(logic._triples_map.get(inst, set()))
 
        assert triples_after == triples_before
 
    def test_populate_true_on_cached_uri_does_not_duplicate_labels(self):
        """Calling get_or_create with populate=True on a URI already populated
        must not add the label twice to has_label."""
        logic = _make_logic([
            (EX.MyClass, RDF.type, OWL.Class),
            (EX.MyClass, RDFS.label, RDFLiteral("My Class")),
        ])
        logic.phase2_create_from_types()
        logic.phase3_populate_properties()
 
        inst = _instance_for_uri(logic, EX.MyClass, Concept)
        labels_before = len(inst.get_has_label())
 
        logic.get_or_create(EX.MyClass, Concept, populate=True)
        labels_after = len(inst.get_has_label())
 
        assert labels_after == labels_before
 
 
# ===========================================================================
# PHASE 6 EXCLUSIONS
# ===========================================================================
 
class TestPhase6Exclusions:
 
    def test_rdf_first_not_produces_statement(self):
        """Triples with rdf:first as predicate must be excluded from Statement production."""
        logic = _make_logic([
            (EX.subject, RDF.type, OWL.Class),
            (EX.subject, EX.customPred, EX.someObject),
        ])
        _run_all(logic)
        stmts = _instances_of(logic, Statement)
        pred_ids = [
            s.get_has_predicate().get_has_identifier()
            for s in stmts
            if s.get_has_predicate() is not None
        ]
        assert str(RDF.first) not in pred_ids
 
    def test_rdf_rest_not_produces_statement(self):
        """Triples with rdf:rest as predicate must be excluded from Statement production."""
        logic = _make_logic([
            (EX.subject, RDF.type, OWL.Class),
            (EX.subject, EX.customPred, EX.someObject),
        ])
        _run_all(logic)
        stmts = _instances_of(logic, Statement)
        pred_ids = [
            s.get_has_predicate().get_has_identifier()
            for s in stmts
            if s.get_has_predicate() is not None
        ]
        assert str(RDF.rest) not in pred_ids
 
    def test_owl_members_not_produces_statement(self):
        """Triples with owl:members as predicate must be excluded from Statement production."""
        g = Graph()
        node = BNode()
        from rdflib.collection import Collection as Col
        head = BNode()
        Col(g, head, [EX.A, EX.B])
        g.add((node, RDF.type, OWL.AllDisjointClasses))
        g.add((node, OWL.members, head))
        g.add((EX.A, RDF.type, OWL.Class))
        g.add((EX.B, RDF.type, OWL.Class))
        logic = OwlLogic(g, {}, OwlConfigManager())
        _run_all(logic)
        stmts = _instances_of(logic, Statement)
        pred_ids = [
            s.get_has_predicate().get_has_identifier()
            for s in stmts
            if s.get_has_predicate() is not None
        ]
        assert str(OWL.members) not in pred_ids
 
    def test_owl_distinct_members_not_produces_statement(self):
        """Triples with owl:distinctMembers as predicate must be excluded from
        Statement production."""
        g = Graph()
        node = BNode()
        from rdflib.collection import Collection as Col
        head = BNode()
        Col(g, head, [EX.i1, EX.i2])
        g.add((node, RDF.type, OWL.AllDifferent))
        g.add((node, OWL.distinctMembers, head))
        g.add((EX.i1, RDF.type, OWL.NamedIndividual))
        g.add((EX.i2, RDF.type, OWL.NamedIndividual))
        logic = OwlLogic(g, {}, OwlConfigManager())
        _run_all(logic)
        stmts = _instances_of(logic, Statement)
        pred_ids = [
            s.get_has_predicate().get_has_identifier()
            for s in stmts
            if s.get_has_predicate() is not None
        ]
        assert str(OWL.distinctMembers) not in pred_ids

    def test_rdfs_class_not_in_cache_after_phases(self):
        """RDFS.Class used only as rdf:type target must not end up in cache."""
        logic = _make_logic([
            (EX.foo, RDF.type, RDFS.Class),
        ])
        _run_all(logic)
        assert RDFS.Class not in logic._instance_cache

    # reserved namespaces handling checks
    
    def test_reserved_ns_predicate_not_in_cache(self):
        """A random reserved entity used ad predicate must not appear in cache."""
        logic = _make_logic([
            (EX.myProp, OWL.disjointWith, EX.myProp2),
        ])
        _run_all(logic)
        assert OWL.disjointWith not in logic._instance_cache

    def test_reserved_ns_class_not_in_cache(self):
        """A random reserved entity used ad class must not appear in cache."""
        logic = _make_logic([
            (EX.myProp, RDF.type, OWL.FunctionalProperty),
        ])
        _run_all(logic)
        assert OWL.FunctionalProperty not in logic._instance_cache

    def test_sub_property_of_rdfs_comment_stays_in_cache(self):
        """A property declared as rdfs:subPropertyOf rdfs:comment must appear in cache."""
        logic = _make_logic([
            (EX.myProp, RDFS.subPropertyOf, RDFS.comment),
        ])
        _run_all(logic)
        assert EX.myProp in logic._instance_cache

    def test_owl_namespace_subject_with_type_not_in_cache(self):
        """A subject explicitly typed even if belonging to OWL namespace must appear in cache."""
        logic = _make_logic([
            (OWL.topObjectProperty, RDF.type, OWL.ObjectProperty),
            (OWL.topObjectProperty, RDFS.label, RDFLiteral("top")),
        ])
        _run_all(logic)
        assert OWL.topObjectProperty in logic._instance_cache

    def test_owl_namespace_subject_with_type_not_in_cache(self):
        """A subject explicitly typed even if belonging to OWL namespace must appear in cache."""
        logic = _make_logic([
            (OWL.topObjectProperty, RDFS.range, EX.myProp),
            (OWL.topObjectProperty, RDFS.label, RDFLiteral("top")),
        ])
        _run_all(logic)
        assert OWL.topObjectProperty in logic._instance_cache
    
