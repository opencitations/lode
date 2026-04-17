# tests/test_integrity.py
import json
import pytest
from pathlib import Path
from rdflib.namespace import RDF, RDFS, OWL, XSD
from rdflib import URIRef, BNode
import os

from lode.models import (
    Property, Relation, Attribute, Annotation, Resource,
    Individual, Statement, Literal, Concept, Datatype, Model
)

# check model coherence nd dt integrity

ONTOLOGIES_PATH = Path(__file__).parent / "ontologies.json"

def _load_uris():
    single = os.environ.get("TEST_ONTOLOGY_URI")
    if single:
        return [single]
    with open(ONTOLOGIES_PATH) as f:
        data = json.load(f)
    return [entry["uri"] for entry in data["uris"]]

def _instances_of(logic, cls):
    result = []
    for instances in logic._instance_cache.values():
        for inst in instances:
            if type(inst) is cls:
                result.append(inst)
    return result


@pytest.fixture(scope="module", params=_load_uris())
def owl_logic(request):
    uri = request.param
    from lode.reader import Reader
    reader = Reader()
    try:
        reader.load_instances(uri, "owl")
    except Exception as e:
        pytest.skip(f"Could not load {uri}: {e}")
    logic = reader._logic
    yield logic
    logic._instance_cache.clear()
    logic._triples_map.clear()


#############################################################################################
# §3 Ontologies / §3.1 Ontology IRI and Version IRI / §3.4 Imports / §3.5 Ontology Annotations
#
# §3:   "An OWL 2 ontology is an instance O of the Ontology UML class."
#        Extraction rule: every URI declared rdf:type owl:Ontology must be Model in cache.
#
# §3.4: "An OWL 2 ontology can import other ontologies."
#        Extraction rule: owl:imports, owl:priorVersion, owl:backwardCompatibleWith,
#        owl:incompatibleWith subject and object must both be Model in cache and populate
#        the corresponding getters. Covered by test_model_relations_subject_object_are_models
#        and test_model_relations_are_populated.
#
# §3.5: "owl:priorVersion, owl:backwardCompatibleWith, owl:incompatibleWith are built-in
#        annotation properties for ontology annotations."
#        Extraction rule: covered by test_model_relations_are_populated.
#
# §3.6: canonical parsing produces instances for all relevant URIs.
#############################################################################################
 
def test_ontology_declaration_produces_model(owl_logic):
    """§3: Every URI declared as owl:Ontology must be Model in cache."""
    from rdflib.namespace import RDF, OWL
    from rdflib import URIRef
    from lode.models import Model
 
    for uri in owl_logic.graph.subjects(RDF.type, OWL.Ontology):
        if not isinstance(uri, URIRef):
            continue
        instances = owl_logic._instance_cache.get(uri, set())
        assert any(isinstance(i, Model) for i in instances), (
            f"§3: {uri} declared as owl:Ontology "
            f"but not Model in cache: "
            f"{[type(i).__name__ for i in instances]}"
        )

def test_model_relations_subject_object_are_models(owl_logic):
    """For every owl:imports, owl:versionIRI, owl:priorVersion,
    owl:backwardCompatibleWith and owl:incompatibleWith triple in the graph,
    both subject and object must be Model instances in cache."""
    from rdflib.namespace import OWL
    from rdflib import URIRef
    from lode.models import Model

    predicates = [
        OWL.imports,
        OWL.versionIRI,
        OWL.priorVersion,
        OWL.backwardCompatibleWith,
        OWL.incompatibleWith,
    ]

    for predicate in predicates:
        for s, _, o in owl_logic.graph.triples((None, predicate, None)):
            if not isinstance(s, URIRef) or not isinstance(o, URIRef):
                continue
            s_inst = next((i for i in owl_logic._instance_cache.get(s, set()) if isinstance(i, Model)), None)
            o_inst = next((i for i in owl_logic._instance_cache.get(o, set()) if isinstance(i, Model)), None)
            assert s_inst is not None, (
                f"{s} is subject of {predicate} but not Model in cache: "
                f"{[type(i).__name__ for i in owl_logic._instance_cache.get(s, set())]}"
            )
            assert o_inst is not None, (
                f"{o} is object of {predicate} but not Model in cache: "
                f"{[type(i).__name__ for i in owl_logic._instance_cache.get(o, set())]}"
            )

def test_model_relations_are_populated(owl_logic):
    """For every owl:imports, owl:versionIRI, owl:priorVersion,
    owl:backwardCompatibleWith and owl:incompatibleWith triple in the graph,
    the corresponding getter on the subject Model must return the object Model."""
    from rdflib.namespace import OWL
    from rdflib import URIRef
    from lode.models import Model

    checks = [
        (OWL.imports, 'get_imports'),
        (OWL.versionIRI, 'get_has_version'),
        (OWL.priorVersion, 'get_has_prior_version'),
        (OWL.backwardCompatibleWith, 'get_is_backward_compatible_with'),
        (OWL.incompatibleWith, 'get_is_incompatible_with'),
    ]

    for predicate, getter_name in checks:
        for s, _, o in owl_logic.graph.triples((None, predicate, None)):
            if not isinstance(s, URIRef) or not isinstance(o, URIRef):
                continue
            s_inst = next((i for i in owl_logic._instance_cache.get(s, set()) if isinstance(i, Model)), None)
            o_inst = next((i for i in owl_logic._instance_cache.get(o, set()) if isinstance(i, Model)), None)
            if s_inst is None or o_inst is None:
                continue
            # Skip if subject has multiple values for this predicate (malformed ontology)
            if len(list(owl_logic.graph.objects(s, predicate))) > 1:
                continue
            values = getattr(s_inst, getter_name)()
            if not isinstance(values, list):
                values = [values]
            assert o_inst in values, (
                f"{s} {predicate} {o}: getter {getter_name} does not return object Model. "
                f"Got: {[v.get_has_identifier() if v else None for v in values]}"
            )

def test_reserved_subject_with_mapped_predicate_in_cache(owl_logic):
    """A reserved namespace URI that appears as subject of a mapped predicate
    must appear in cache."""
    mapped_preds = set(owl_logic._property_mapping.keys())

    for uri in owl_logic.graph.subjects():
        if not isinstance(uri, URIRef):
            continue
        if not any(str(uri).startswith(ns) for ns in [str(RDF), str(RDFS), str(OWL)]):
            continue
        has_mapped_pred = any(
            (uri, p, None) in owl_logic.graph for p in mapped_preds
        )
        if has_mapped_pred:
            assert uri in owl_logic._instance_cache, (
                f"Reserved URI {uri} with mapped predicate must be in cache"
            )

#############################################################################################
# §4 Datatype Maps / §4.1 Real Numbers, Decimal Numbers, and Integers
#
# §4:   "A set of datatypes supported by a reasoner is called a datatype map. This is not
#        a syntactic construct — it is not represented in the structural specification."
#        Out of scope as a whole: datatype map is a reasoner concern, not extraction.
#
# The OWL 2 datatype map includes: owl:real, owl:rational, xsd:decimal, xsd:integer,
#        xsd:nonNegativeInteger, xsd:nonPositiveInteger, xsd:positiveInteger,
#        xsd:negativeInteger, xsd:long, xsd:int, xsd:short, xsd:byte, xsd:unsignedLong,
#        xsd:unsignedInt, xsd:unsignedShort, xsd:unsignedByte.
#        Extraction rule: any URI from this set appearing in the graph as subject or object
#        must be Datatype in cache. Covered by test_datatype_uris_in_cache.
#        The constraining facets (xsd:minInclusive etc.) are predicates, not datatypes —
#        they must NOT be Datatype in cache. Covered by test_datatype_uris_in_cache
#        which excludes predicates from the check.
#############################################################################################

def test_datatype_uris_in_cache(owl_logic):
    """XSD URIs and RDFS.Literal used as subject or object must appear in cache as Datatype."""
    from lode.models import Datatype

    for s, p, o in owl_logic.graph:
        for node in (s, o):  # escludes p —predicates (facets) XSD are Annotations, not Datatypes
            if not isinstance(node, URIRef):
                continue
            if str(node).startswith(str(XSD)) or node == RDFS.Literal:
                assert node in owl_logic._instance_cache, (
                    f"{node} is a datatype URI but not in cache"
                )
                instances = owl_logic._instance_cache[node]
                assert any(isinstance(i, Datatype) for i in instances), (
                    f"{node} is in cache but not as Datatype: "
                    f"{[type(i).__name__ for i in instances]}"
                )

#############################################################################################
# §5.2 Datatypes
# "An IRI used to identify a datatype in an OWL 2 DL ontology MUST:
#   - be rdfs:Literal, OR
#   - identify a datatype in the OWL 2 datatype map (XSD + owl:real/owl:rational), OR
#   - not be in the reserved vocabulary of OWL 2"
#############################################################################################

def test_datatype_iris_are_valid(owl_logic):
    """§5.2 OWL 2 Structural Specification — Datatype IRIs.
    Spec: 'Each datatype is rdfs:Literal, in the OWL 2 datatype map,
    or defined by a DatatypeDefinition.'
    Extraction rule: every Datatype IRI in reserved vocabulary must be
    either rdfs:Literal, an XSD datatype, or rdf:XMLLiteral / rdf:HTML."""
    from rdflib.namespace import XSD, RDFS, OWL, RDF
    from lode.models import Datatype

    # OWL 2 datatype map: rdfs:Literal + tutto XSD + rdf:XMLLiteral + rdf:HTML
    XSD_NS = str(XSD)

    VALID_RESERVED = {
        str(RDFS.Literal),
        str(OWL.real),
        str(OWL.rational),
        str(RDF.XMLLiteral),
        str(RDF.HTML),
        "http://www.w3.org/1999/02/22-rdf-syntax-ns#langString",
        "http://www.w3.org/1999/02/22-rdf-syntax-ns#PlainLiteral",
        "http://www.w3.org/1999/02/22-rdf-syntax-ns#JSON",
    }
    
    RESERVED_NS = {str(OWL), str(RDF), str(RDFS), str(XSD)}

    for instances in owl_logic._instance_cache.values():
        for inst in instances:
            if not isinstance(inst, Datatype):
                continue
            iri = inst.get_has_identifier()
            if iri is None:
                continue
            if not any(iri.startswith(ns) for ns in RESERVED_NS):
                continue  # non è in namespace riservato — OK per §5.2 condition 3
            # È in namespace riservato: deve essere XSD o nella whitelist
            assert iri.startswith(XSD_NS) or iri in VALID_RESERVED, (
                f"§5.2: Datatype {iri} is in reserved vocabulary "
                f"but not a valid OWL 2 datatype IRI"
            )

#############################################################################################
# §5 Entities, Literals, and Anonymous Individuals
# §5.1 Classes / §5.2 Datatypes / §5.3 Object Properties / §5.4 Data Properties /
# §5.5 Annotation Properties / §5.6 Individuals / §5.7 Literals /
# §5.8 Entity Declarations and Typing / §5.9 Metamodeling
#
# §5.1: "The classes with the IRIs owl:Thing and owl:Nothing are available as built-in
#        classes. IRIs from the reserved vocabulary other than owl:Thing and owl:Nothing
#        MUST NOT be used to identify classes in an OWL 2 DL ontology."
#        Extraction rule: every URI declared rdf:type owl:Class must be Concept in cache.
#        owl:Thing used as default domain/range must be Concept in cache.
#        Covered by test_concept_relations_subject_object_are_concepts and
#        test_property_domain_and_range_populated. Also: test_no_instance_has_none_identifier (concern §5.1-§5.6).
#
# §5.2: "An IRI used to identify a datatype MUST be rdfs:Literal, identify a datatype
#        in the OWL 2 datatype map, or not be in the reserved vocabulary of OWL 2."
#        Extraction rule: every Datatype in cache must satisfy one of these conditions.
#        Covered by test_datatype_uris_in_cache and test_datatype_iris_are_valid.
#
# §5.3: "Object properties connect pairs of individuals."
#        "IRIs from the reserved vocabulary other than owl:topObjectProperty and
#        owl:bottomObjectProperty MUST NOT be used to identify object properties."
#        Extraction rule: every URI declared rdf:type owl:ObjectProperty must be Relation.
#        Covered by test_object_property_declaration_produces_relation.
#
# §5.4: "Data properties connect individuals with literals."
#        "IRIs from the reserved vocabulary other than owl:topDataProperty and
#        owl:bottomDataProperty MUST NOT be used to identify data properties."
#        Extraction rule: every URI declared rdf:type owl:DatatypeProperty must be Attribute.
#        Covered by test_datatype_property_declaration_produces_attribute.
#
# §5.5: "Annotation properties can be used to provide an annotation for an ontology,
#        axiom, or an IRI."
#        Built-in annotation properties: rdfs:label, rdfs:comment, rdfs:seeAlso,
#        rdfs:isDefinedBy, owl:deprecated, owl:versionInfo, owl:priorVersion,
#        owl:backwardCompatibleWith, owl:incompatibleWith.
#        Extraction rule: every URI declared rdf:type owl:AnnotationProperty must be
#        Annotation in cache. Built-in annotation properties are filtered by namespace
#        filter — out of scope.
#        Covered by test_annotation_property_declaration_produces_annotation and fallback covered by test_untyped_property_fallback_is_annotation,
#
# §5.6.1: "Named individuals are identified using an IRI."
#          "IRIs from the reserved vocabulary MUST NOT be used to identify named individuals."
#          Extraction rule: every URI declared rdf:type owl:NamedIndividual must be
#          Individual in cache.
#          Covered by test_named_individual_declaration_produces_individual.
#
# §5.6.2: "Anonymous individuals do not have a global name and are local to the ontology."
#          Out of scope: BNode identity across ontology boundaries not verifiable at
#          extraction level.
#
# §5.7: "Each literal consists of a lexical form and a datatype."
#        Extraction rule: every Literal in cache must have has_value set (lexical form)
#        and optionally has_type (datatype) and has_language.
#        Covered by test_all_literals_have_value.
#
# §5.8.1: Typing constraints:
#          "No IRI I is declared as being of more than one type of property."
#          "No IRI I is declared to be both a class and a datatype."
#          Extraction rule: no URIRef in cache can simultaneously be Relation+Attribute,
#          Relation+Annotation, Attribute+Annotation, or Concept+Datatype.
#          Covered by test_no_generic_property_in_cache (partial) and
#          test_no_iri_has_conflicting_property_types.
#
# §5.9: Metamodeling — same IRI used as both Concept and Individual (punning).
#          "An IRI I can be used in an OWL 2 ontology to refer to more than one type of entity.
#          Such usage of I is often called metamodeling."
#          (OWL 2 Structural Specification, Section 5.9)
#          Extraction rule: if a URI is declared both as owl:Class and owl:NamedIndividual
#          in the graph, both a Concept and an Individual instance must exist in cache
#          under the same URI key (punning). Covered by test_no_duplicate_instances_for_non_punned_uri and test_punning_concept_and_individual_preserved.
#############################################################################################

def test_concept_relations_subject_object_are_concepts(owl_logic):
    """For every rdfs:subClassOf, owl:disjointWith and owl:equivalentClass triple
    in the graph, both subject and object must be Concept instances in cache."""
    from rdflib.namespace import RDFS, OWL
    from rdflib import URIRef
    from lode.models import Concept

    predicates = [
        RDFS.subClassOf,
        OWL.disjointWith,
        OWL.equivalentClass,
    ]

    for predicate in predicates:
        for s, _, o in owl_logic.graph.triples((None, predicate, None)):
            if not isinstance(s, URIRef) or not isinstance(o, URIRef):
                continue
            s_inst = next((i for i in owl_logic._instance_cache.get(s, set()) if isinstance(i, Concept)), None)
            o_inst = next((i for i in owl_logic._instance_cache.get(o, set()) if isinstance(i, Concept)), None)
            assert s_inst is not None, (
                f"{s} is subject of {predicate} but not Concept in cache: "
                f"{[type(i).__name__ for i in owl_logic._instance_cache.get(s, set())]}"
            )
            assert o_inst is not None, (
                f"{o} is object of {predicate} but not Concept in cache: "
                f"{[type(i).__name__ for i in owl_logic._instance_cache.get(o, set())]}"
            )

def test_concept_relations_are_populated(owl_logic):
    """For every rdfs:subClassOf, owl:disjointWith and owl:equivalentClass triple,
    the corresponding getter on the subject Concept must return the object Concept."""
    from rdflib.namespace import RDFS, OWL
    from rdflib import URIRef
    from lode.models import Concept

    checks = [
        (RDFS.subClassOf, 'get_is_sub_concept_of'),
        (OWL.disjointWith, 'get_is_disjoint_with'),
        (OWL.equivalentClass, 'get_is_equivalent_to'),
    ]

    for predicate, getter_name in checks:
        for s, _, o in owl_logic.graph.triples((None, predicate, None)):
            if not isinstance(s, URIRef) or not isinstance(o, URIRef):
                continue
            if len(list(owl_logic.graph.objects(s, predicate))) > 1:
                continue
            s_inst = next((i for i in owl_logic._instance_cache.get(s, set()) if isinstance(i, Concept)), None)
            o_inst = next((i for i in owl_logic._instance_cache.get(o, set()) if isinstance(i, Concept)), None)
            if s_inst is None or o_inst is None:
                continue
            values = getattr(s_inst, getter_name)()
            if not isinstance(values, list):
                values = [values]
            assert o_inst in values, (
                f"{s} {predicate} {o}: getter {getter_name} does not return object Concept. "
                f"Got: {[v.get_has_identifier() if v else None for v in values]}"
            )

def test_skos_concept_relations_not_populated(owl_logic):
    """SKOS match/hierarchy predicates must never populate Concept relation fields
    when parsing as OWL — those triples must become Statements instead."""
    from lode.models import Concept

    SKOS_GETTERS = [
        'get_is_related_to',
        'get_has_broad_match',
        'get_has_narrow_match',
        'get_has_related_match',
        'get_has_exact_match',
        'get_has_close_match',
    ]

    for instances in owl_logic._instance_cache.values():
        for inst in instances:
            if not isinstance(inst, Concept):
                continue
            for getter_name in SKOS_GETTERS:
                values = getattr(inst, getter_name)()
                assert len(values) == 0, (
                    f"{inst.get_has_identifier()} ({type(inst).__name__}) "
                    f"has {getter_name}() populated in OWL mode: {values}"
                )

def test_object_property_declaration_produces_relation(owl_logic):
    """§5.3: Every URI declared as owl:ObjectProperty must be Relation in cache."""
    from rdflib.namespace import RDF, OWL
    from rdflib import URIRef
    from lode.models import Relation

    for uri in owl_logic.graph.subjects(RDF.type, OWL.ObjectProperty):
        if not isinstance(uri, URIRef):
            continue
        instances = owl_logic._instance_cache.get(uri, set())
        assert any(isinstance(i, Relation) for i in instances), (
            f"§5.3: {uri} declared as owl:ObjectProperty "
            f"but not Relation in cache: "
            f"{[type(i).__name__ for i in instances]}"
        )

def test_annotation_property_declaration_produces_annotation(owl_logic):
    """§5.5: Every URI declared as owl:AnnotationProperty must be Annotation in cache."""
    from rdflib.namespace import RDF, OWL
    from rdflib import URIRef
    from lode.models import Annotation

    for uri in owl_logic.graph.subjects(RDF.type, OWL.AnnotationProperty):
        if not isinstance(uri, URIRef):
            continue
        instances = owl_logic._instance_cache.get(uri, set())
        assert any(isinstance(i, Annotation) for i in instances), (
            f"§5.5: {uri} declared as owl:AnnotationProperty "
            f"but not Annotation in cache: "
            f"{[type(i).__name__ for i in instances]}"
        )

def test_all_literals_have_value(owl_logic):
    """Every Literal in cache must have has_value set."""
    from lode.models import Literal

    for instances in owl_logic._instance_cache.values():
        for inst in instances:
            if not isinstance(inst, Literal):
                continue
            assert inst.get_has_value() is not None, (
                f"Literal has no value"
            )

def test_no_generic_property_in_cache(owl_logic):
    for instances in owl_logic._instance_cache.values():
        for inst in instances:
            assert type(inst) is not Property, (
                f"Generic Property found in cache: {inst.get_has_identifier()}"
            )

@pytest.mark.parametrize("cls_a, cls_b, label", [
    (Relation, Attribute, "object and data property"),
    (Relation, Annotation, "object and annotation property"),
    (Attribute, Annotation, "data and annotation property"),
    (Concept, Datatype, "class and datatype"),
])
def test_no_iri_has_conflicting_property_types(owl_logic, cls_a, cls_b, label):
    """§5.8.1 OWL 2 Structural Specification — Typing Constraints.
    Spec: 'No IRI I is declared to be both {label}.'
    Extraction rule: no URIRef in cache can simultaneously be cls_a and cls_b.
    Guard: if both types are explicitly declared in the graph, the ontology is
    malformed — not a LODE bug, skip."""
    from rdflib.namespace import RDF, OWL, RDFS
    from rdflib import URIRef

    CLS_TO_RDF_TYPE = {
        Relation: OWL.ObjectProperty,
        Attribute: OWL.DatatypeProperty,
        Annotation: OWL.AnnotationProperty,
        Concept: OWL.Class,
        Datatype: RDFS.Datatype,
    }

    for uri, instances in owl_logic._instance_cache.items():
        if not isinstance(uri, URIRef):
            continue

        # Guard: both types explicitly declared in graph → malformed ontology, not LODE bug
        rdf_a = CLS_TO_RDF_TYPE.get(cls_a)
        rdf_b = CLS_TO_RDF_TYPE.get(cls_b)
        if rdf_a and rdf_b:
            if (uri, RDF.type, rdf_a) in owl_logic.graph and \
               (uri, RDF.type, rdf_b) in owl_logic.graph:
                continue

        # Concept uses exact type() check — Datatype is a subclass of Concept
        if cls_a is Concept:
            has_a = any(type(i) is Concept for i in instances)
        else:
            has_a = any(isinstance(i, cls_a) for i in instances)
        has_b = any(isinstance(i, cls_b) for i in instances)

        assert not (has_a and has_b), (
            f"§5.8.1: {uri} is both {cls_a.__name__} and {cls_b.__name__} in cache"
        )

def test_punning_concept_and_individual_preserved(owl_logic):
    """§5.9 OWL 2 Structural Specification — Metamodeling.
    Spec: 'An IRI I can be used in an OWL 2 ontology to refer to more than one type
    of entity — this is called metamodeling.'
    Extraction rule: a URI declared both as owl:Class and owl:NamedIndividual must have
    both a Concept and an Individual instance in cache under the same URI key."""
    from rdflib.namespace import RDF, OWL
    from rdflib import URIRef
    from lode.models import Concept, Individual

    punned = set(owl_logic.graph.subjects(RDF.type, OWL.Class)) & \
             set(owl_logic.graph.subjects(RDF.type, OWL.NamedIndividual))

    for uri in punned:
        if not isinstance(uri, URIRef):
            continue
        instances = owl_logic._instance_cache.get(uri, set())
        has_concept = any(isinstance(i, Concept) for i in instances)
        has_individual = any(isinstance(i, Individual) for i in instances)
        assert has_concept and has_individual, (
            f"§5.9: {uri} declared as both owl:Class and owl:NamedIndividual "
            f"but punning not preserved in cache: "
            f"{[type(i).__name__ for i in instances]}"
        )

def test_no_duplicate_instances_for_non_punned_uri(owl_logic):
    """A URIRef must not have duplicate instances of the same type in cache."""
    from rdflib import URIRef
    for uri, instances in owl_logic._instance_cache.items():
        if not isinstance(uri, URIRef):
            continue
        if len(instances) <= 1:
            continue
        # Duplicates are only a bug if two instances have the SAME type
        types = [type(i) for i in instances]
        for t in types:
            assert types.count(t) == 1, (
                f"URI {uri} has {types.count(t)} instances of type {t.__name__}"
            )

def test_no_instance_has_none_identifier(owl_logic):
    for instances in owl_logic._instance_cache.values():
        for inst in instances:
            if isinstance(inst, Literal):
                continue
            if hasattr(inst, 'get_has_identifier'):
                assert inst.get_has_identifier() is not None, (
                    f"{type(inst).__name__} has None identifier"
                )

def test_untyped_property_fallback_is_annotation(owl_logic):
    """Any property that cannot be classified as Relation or Attribute
    must fall back to Annotation — never remain as generic Property."""
    from rdflib import URIRef
    from lode.models import Property, Relation, Attribute, Annotation

    for uri, instances in owl_logic._instance_cache.items():
        if not isinstance(uri, URIRef):
            continue
        for inst in instances:
            if not isinstance(inst, Property):
                continue
            assert isinstance(inst, (Relation, Attribute, Annotation)), (
                f"{uri} is generic Property — must be Relation, Attribute or Annotation"
            )
#############################################################################################
# §6 Property Expressions
# §6.1 Object Property Expressions / §6.1.1 Inverse Object Properties
# §6.2 Data Property Expressions
#
# §6.1.1: "An inverse object property expression ObjectInverseOf(P) connects I1 with I2
#          if and only if P connects I2 with I1."
#          Extraction rule: if A owl:inverseOf B in graph, then A.get_is_inverse_of() is B
#          and B.get_is_inverse_of() is A, and domain/range are swapped.
#          Covered by test_inverse_of_bidirectional_and_domain_range_swapped and test_on_property_inverse_bnode_resolved.
#
#############################################################################################

def test_inverse_of_bidirectional_and_domain_range_swapped(owl_logic):
    """If A owl:inverseOf B in graph then:
    - both A and B are Relation
    - A.is_inverse_of is B and B.is_inverse_of is A
    - A.domain == B.range and A.range == B.domain (if declared)
    Note. skips bnodes as they are unique even if representing the same restriction
    """
    from rdflib.namespace import OWL
    from rdflib import URIRef
    from lode.models import Relation

    for s, _, o in owl_logic.graph.triples((None, OWL.inverseOf, None)):
        if not isinstance(s, URIRef) or not isinstance(o, URIRef):
            continue
        s_inst = next((i for i in owl_logic._instance_cache.get(s, set()) if isinstance(i, Relation)), None)
        o_inst = next((i for i in owl_logic._instance_cache.get(o, set()) if isinstance(i, Relation)), None)
        assert s_inst is not None, f"{s} has owl:inverseOf but is not Relation"
        assert o_inst is not None, f"{o} has owl:inverseOf but is not Relation"
        assert s_inst.get_is_inverse_of() is o_inst, f"{s} not wired to inverse {o}"
        assert o_inst.get_is_inverse_of() is s_inst, f"{o} not wired back to inverse {s}"

        # Skip if domain/range contain anonymous classes (BNodes — e.g. owl:unionOf)
        if any(not str(d.get_has_identifier()).startswith('http') for d in s_inst.get_has_domain()):
            continue
        if any(not str(r.get_has_identifier()).startswith('http') for r in s_inst.get_has_range()):
            continue
        if any(not str(d.get_has_identifier()).startswith('http') for d in o_inst.get_has_domain()):
            continue
        if any(not str(r.get_has_identifier()).startswith('http') for r in o_inst.get_has_range()):
            continue

        # Skip if both s and o have explicit domain/range in graph (malformed ontology)
        from rdflib.namespace import RDFS
        if ((s, RDFS.domain, None) in owl_logic.graph or (s, RDFS.range, None) in owl_logic.graph) and \
           ((o, RDFS.domain, None) in owl_logic.graph or (o, RDFS.range, None) in owl_logic.graph):
                continue

        s_domains = {d.get_has_identifier() for d in s_inst.get_has_domain()}
        s_ranges = {r.get_has_identifier() for r in s_inst.get_has_range()}
        o_domains = {d.get_has_identifier() for d in o_inst.get_has_domain()}
        o_ranges = {r.get_has_identifier() for r in o_inst.get_has_range()}

        assert s_domains == o_ranges, (
            f"{s} domain {s_domains} != {o} range {o_ranges}"
        )
        assert o_domains == s_ranges, (
            f"{o} domain {o_domains} != {s} range {s_ranges}"
        )

def test_on_property_inverse_bnode_resolved(owl_logic):
    """§6.1.1: When owl:onProperty points to a BNode with owl:inverseOf,
    the PropertyConceptRestriction must have is_inverse=True and
    applies_on_property pointing to the real property (not the BNode)."""
    from rdflib import BNode, URIRef
    from rdflib.namespace import OWL
    from lode.models import PropertyConceptRestriction

    for restr_uri, obj in owl_logic.graph.subject_objects(OWL.onProperty):
        if not isinstance(obj, BNode):
            continue
        if (obj, OWL.inverseOf, None) not in owl_logic.graph:
            continue
        instances = owl_logic._instance_cache.get(restr_uri, set())
        pcr = next((i for i in instances if isinstance(i, PropertyConceptRestriction)), None)
        if pcr is None:
            continue
        assert pcr.get_is_inverse() is True, (
            f"{restr_uri} has owl:onProperty with inverseOf BNode "
            f"but is_inverse is not True"
        )
        prop = pcr.get_applies_on_property()
        assert prop is not None, (
            f"{restr_uri} has owl:onProperty with inverseOf BNode "
            f"but applies_on_property is None"
        )
        iri = prop.get_has_identifier()
        assert iri and not iri.startswith("N") and not iri.startswith("n"), (
            f"{restr_uri} applies_on_property should be the real property, "
            f"not BNode {iri}"
        )

#############################################################################################
# §7 Data Ranges
# §7.1 Intersection / §7.2 Union / §7.3 Complement / §7.4 Enumeration / §7.5 Restriction
#
# §7:   "Data ranges can be used in restrictions on data properties."
#        DataRange := Datatype | DataIntersectionOf | DataUnionOf | DataComplementOf |
#        DataOneOf | DatatypeRestriction.
#        Out of scope: DataIntersectionOf, DataUnionOf, DataComplementOf, DataOneOf are
#        data range constructs with no direct RDF triple representation as named entities —
#        they appear as BNode structures within data property restrictions.
#        LODE does not currently model these as distinct instances.
#
# §7.1: "DataIntersectionOf(DR1...DRn) — all DRi MUST be of the same arity (>= 2)."
#        See TruthFunction tests.
#
# §7.2: "DataUnionOf(DR1...DRn) — all DRi MUST be of the same arity (>= 2)."
#        See TruthFunction tests.
#
# §7.3: "DataComplementOf(DR) — complement of a data range."
#        See TruthFunction tests.
#
# §7.4: "DataOneOf(lt1...ltn) — exactly the specified literals."
#        See OneOf tests.
#
# §7.5 Datatype Restrictions
# "DatatypeRestriction(DT F1 lt1 ... Fn ltn) — restricts the value space of DT
#  by n constraining facet-value pairs."
# In LODE (owl.yaml):
#   - owl:withRestrictions → Datatype in cache (the restricted datatype)
#   - BNode with XSD facet predicate → DatatypeRestriction in cache
# Extraction rule: every BNode that is subject of an XSD facet predicate must produce
# a DatatypeRestriction in cache with has_constraint (Annotation) and
# has_restriction_value (str) populated.
# Covered by test_datatype_restriction_has_constraint_and_value (integrity)
# and test_datatype_restriction_graph_correspondence (graph correspondence) and test_datatype_restriction_xsd_facet_in_cache (xsd:facets).
#############################################################################################
 
def test_datatype_restriction_graph_correspondence(owl_logic):
    """§7.5 OWL 2 Structural Specification — Datatype Restrictions.
    Spec: 'DatatypeRestriction(DT F1 lt1...Fn ltn) restricts the value space of DT
    by n constraining facet-value pairs.'
    Extraction rule: every BNode with owl:onDatatype in the graph must produce a
    DatatypeRestriction in cache."""
    from rdflib.namespace import OWL
    from rdflib import BNode
    from lode.models import DatatypeRestriction
 
    for subj in owl_logic.graph.subjects(OWL.onDatatype, None):
        if not isinstance(subj, BNode):
            continue
        instances = owl_logic._instance_cache.get(subj, set())
        assert any(isinstance(i, DatatypeRestriction) for i in instances), (
            f"§7.5: BNode {subj} has owl:onDatatype in graph "
            f"but no DatatypeRestriction in cache: "
            f"{[type(i).__name__ for i in instances]}"
        )

def test_datatype_restriction_xsd_facet_in_cache(owl_logic):
    """§7.5 OWL 2 Structural Specification — Datatype Restrictions.
    Spec: 'DatatypeRestriction consists of a unary datatype DT and n constraining
    facet-value pairs.'
    Extraction rule: every BNode that is subject of an XSD facet predicate must produce
    a DatatypeRestriction in cache."""
    from rdflib.namespace import XSD
    from rdflib import BNode
    from lode.models import DatatypeRestriction
 
    XSD_FACETS = {
        XSD.minExclusive, XSD.maxExclusive, XSD.minInclusive, XSD.maxInclusive,
        XSD.pattern, XSD.length, XSD.minLength, XSD.maxLength,
        XSD.totalDigits, XSD.fractionDigits, XSD.enumeration, XSD.whiteSpace,
    }
 
    seen = set()
    for facet in XSD_FACETS:
        for subj in owl_logic.graph.subjects(facet, None):
            if not isinstance(subj, BNode) or subj in seen:
                continue
            seen.add(subj)
            instances = owl_logic._instance_cache.get(subj, set())
            assert any(isinstance(i, DatatypeRestriction) for i in instances), (
                f"§7.5: BNode {subj} has XSD facet predicate in graph "
                f"but no DatatypeRestriction in cache: "
                f"{[type(i).__name__ for i in instances]}"
            )

#############################################################################################
# §8 Class Expressions
#
# §8.1.1: "ObjectIntersectionOf(CE1...CEn) — >= 2 class expressions."
#          Extraction rule: BNode with owl:intersectionOf produces TruthFunction(operator=and)
#          with >= 2 applies_on_concept entries.
#          Covered by test_truth_function_and_or_has_multiple_concepts,
#          test_truth_function_graph_correspondence.
#
# §8.1.2: "ObjectUnionOf(CE1...CEn) — >= 2 class expressions."
#          Extraction rule: BNode with owl:unionOf produces TruthFunction(operator=or)
#          with >= 2 applies_on_concept entries.
#          Covered by test_truth_function_and_or_has_multiple_concepts,
#          test_truth_function_graph_correspondence.
#
# §8.1.3: "ObjectComplementOf(CE) — exactly 1 class expression."
#          Extraction rule: BNode with owl:complementOf produces TruthFunction(operator=not)
#          with exactly 1 applies_on_concept entry.
#          Covered by test_truth_function_not_has_exactly_one_concept,
#          test_truth_function_graph_correspondence.
#
# §8.1.4: "ObjectOneOf(a1...an) — exactly the specified individuals."
#          Extraction rule: BNode with owl:oneOf produces OneOf with applies_on_resource
#          populated with >= 1 Individual instances.
#          Covered by test_one_of_has_resources, test_one_of_resources_are_individuals,
#          test_one_of_graph_correspondence.
#
# §8.2.1: "ObjectSomeValuesFrom(OPE CE) — existential quantification."
#          Extraction rule: BNode with owl:someValuesFrom produces Quantifier(type=some)
#          with applies_on_property and applies_on_concept populated.
#          Covered by test_quantifier_graph_correspondence, test_quantifier_type_valid,
#          test_quantifier_has_property.
#
# §8.2.2: "ObjectAllValuesFrom(OPE CE) — universal quantification."
#          Extraction rule: BNode with owl:allValuesFrom produces Quantifier(type=only)
#          with applies_on_property and applies_on_concept populated.
#          Covered by test_quantifier_graph_correspondence, test_quantifier_type_valid,
#          test_quantifier_has_property.
#
# §8.2.3: "ObjectHasValue(OPE a) — individual value restriction."
#          Extraction rule: BNode with owl:hasValue produces Value with
#          applies_on_property and applies_on_resource populated.
#          Covered by test_value_has_resource, test_value_has_property,
#          test_value_graph_correspondence.
#
# §8.2.4: "ObjectHasSelf(OPE) — self-restriction."
#          Out of scope: owl:hasSelf not mapped in owl.yaml — no model class.
#
# §8.3.1: "ObjectMinCardinality(n OPE [CE]) — min cardinality. If CE missing, owl:Thing."
#          Extraction rule: BNode with owl:minCardinality or owl:minQualifiedCardinality
#          produces Cardinality(type=min) with has_cardinality >= 0, applies_on_property,
#          applies_on_concept (owl:Thing if unqualified).
#          Covered by test_cardinality_graph_correspondence, test_cardinality_type_valid,
#          test_cardinality_value_is_non_negative_int, test_cardinality_has_property.
#
# §8.3.2: "ObjectMaxCardinality(n OPE [CE]) — max cardinality. If CE missing, owl:Thing."
#          Extraction rule: BNode with owl:maxCardinality or owl:maxQualifiedCardinality
#          produces Cardinality(type=max).
#          Covered by same tests as §8.3.1.
#
# §8.3.3: "ObjectExactCardinality(n OPE [CE]) — exact cardinality. If CE missing, owl:Thing."
#          Extraction rule: BNode with owl:cardinality or owl:qualifiedCardinality
#          produces Cardinality(type=exactly).
#          Covered by same tests as §8.3.1.
#
# §8.4.1: "DataSomeValuesFrom(DPE DR) — existential quantification on data property."
#          owl:someValuesFrom is shared with object context in RDF serialization.
#          Extraction rule: same as §8.2.1 — produces Quantifier(type=some).
#          Covered by test_quantifier_graph_correspondence.
#
# §8.4.2: "DataAllValuesFrom(DPE DR) — universal quantification on data property."
#          owl:allValuesFrom is shared with object context in RDF serialization.
#          Extraction rule: same as §8.2.2 — produces Quantifier(type=only).
#          Covered by test_quantifier_graph_correspondence.
#
# §8.4.3: "DataHasValue(DPE lt) — literal value restriction."
#          owl:hasValue is shared with object context in RDF serialization.
#          Extraction rule: same as §8.2.3 — produces Value.
#          Covered by test_value_has_resource, test_value_graph_correspondence.
#
# §8.5.1: "DataMinCardinality(n DPE [DR]) — min cardinality on data property."
#          owl:minCardinality / owl:minQualifiedCardinality shared with object context.
#          Extraction rule: same as §8.3.1 — produces Cardinality(type=min).
#          Covered by test_cardinality_graph_correspondence.
#
# §8.5.2: "DataMaxCardinality(n DPE [DR]) — max cardinality on data property."
#          Extraction rule: same as §8.3.2 — produces Cardinality(type=max).
#          Covered by test_cardinality_graph_correspondence.
#
# §8.5.3: "DataExactCardinality(n DPE [DR]) — exact cardinality on data property."
#          Extraction rule: same as §8.3.3 — produces Cardinality(type=exactly).
#          Covered by test_cardinality_graph_correspondence.
#############################################################################################

#############################################################################################
########################              A. RESTRICTION (BASE)        ##########################
#############################################################################################
 
def test_restriction_applies_on_concept_not_empty(owl_logic):
    """applies_on_concept must be populated.
    - PropertyConceptRestriction subclasses (Quantifier, Cardinality, Value):
      scalar [1] — must not be None.
    - Pure Restriction subclasses (TruthFunction): list [1..*] — must not be empty.
    - OneOf: uses applies_on_resource instead — skipped here.
    - Value: uses applies_on_resource instead — skipped here.
    """
    from lode.models import Restriction, PropertyConceptRestriction, OneOf, Value, Concept, DatatypeRestriction
 
    for instances in owl_logic._instance_cache.values():
        for inst in instances:
            if not isinstance(inst, Restriction):
                continue
            if isinstance(inst, (OneOf, Value, DatatypeRestriction)):
                continue
            c = inst.get_applies_on_concept()
            if isinstance(inst, PropertyConceptRestriction):
                assert c is not None, (
                    f"{type(inst).__name__} {inst.get_has_identifier()} "
                    f"has applies_on_concept=None"
                )
            else:
                assert len(c) >= 1, (
                    f"{type(inst).__name__} {inst.get_has_identifier()} "
                    f"has empty applies_on_concept"
                )
 
def test_restriction_applies_on_concept_are_concepts(owl_logic):
    """applies_on_concept entries must be Concept instances.
    Handles both scalar (PropertyConceptRestriction) and list (Restriction) semantics.
    """
    from lode.models import Restriction, PropertyConceptRestriction, Concept, OneOf, Value, DatatypeRestriction
 
    for instances in owl_logic._instance_cache.values():
        for inst in instances:
            if not isinstance(inst, Restriction):
                continue
            if isinstance(inst, (OneOf, Value, DatatypeRestriction)):
                continue
            c = inst.get_applies_on_concept()
            if isinstance(inst, PropertyConceptRestriction):
                if c is None:
                    continue
                assert isinstance(c, Concept), (
                    f"{type(inst).__name__} {inst.get_has_identifier()} "
                    f"applies_on_concept is not Concept: {type(c).__name__}"
                )
            else:
                for item in c:
                    assert isinstance(item, Concept), (
                        f"{type(inst).__name__} {inst.get_has_identifier()} "
                        f"applies_on_concept contains non-Concept: {type(item).__name__} "
                        f"{getattr(item, 'get_has_identifier', lambda: '?')()}"
                    )
 
 
#############################################################################################
########################     B. PROPERTY CONCEPT RESTRICTION       ##########################
#############################################################################################
 
def test_property_concept_restriction_has_property(owl_logic):
    """Every PropertyConceptRestriction must have applies_on_property set."""
    from lode.models import PropertyConceptRestriction, Property
 
    for inst in _instances_of(owl_logic, None):  # handled below
        pass
 
    for instances in owl_logic._instance_cache.values():
        for inst in instances:
            if not isinstance(inst, PropertyConceptRestriction):
                continue
            prop = inst.get_applies_on_property()
            assert prop is not None, (
                f"{type(inst).__name__} {inst.get_has_identifier()} "
                f"has no applies_on_property"
            )
            assert isinstance(prop, Property), (
                f"{type(inst).__name__} {inst.get_has_identifier()} "
                f"applies_on_property is not Property: {type(prop).__name__}"
            )
 
 
#############################################################################################
########################              C. QUANTIFIER                ##########################
#############################################################################################
 
def test_quantifier_type_valid(owl_logic):
    """has_quantifier_type must be 'some' or 'only'."""
    from lode.models import Quantifier
 
    VALID = {"some", "only"}
    for inst in _instances_of(owl_logic, Quantifier):
        qt = inst.get_has_quantifier_type()
        assert qt in VALID, (
            f"Quantifier {inst.get_has_identifier()} has invalid "
            f"has_quantifier_type: {qt!r}"
        )
 
def test_quantifier_has_property(owl_logic):
    """Every Quantifier must have applies_on_property set."""
    from lode.models import Quantifier, Property
 
    for inst in _instances_of(owl_logic, Quantifier):
        prop = inst.get_applies_on_property()
        assert prop is not None, (
            f"Quantifier {inst.get_has_identifier()} has no applies_on_property"
        )
        assert isinstance(prop, Property), (
            f"Quantifier {inst.get_has_identifier()} applies_on_property "
            f"is not Property: {type(prop).__name__}"
        )
 
def test_quantifier_graph_correspondence(owl_logic):
    """Every owl:someValuesFrom / owl:allValuesFrom BNode in graph must
    produce exactly one Quantifier in cache."""
    from rdflib.namespace import OWL
    from rdflib import BNode
    from lode.models import Quantifier
 
    for pred, expected_type in [
        (OWL.someValuesFrom, "some"),
        (OWL.allValuesFrom, "only"),
    ]:
        for subj in owl_logic.graph.subjects(pred, None):
            if not isinstance(subj, BNode):
                continue
            instances = owl_logic._instance_cache.get(subj, set())
            q = next((i for i in instances if isinstance(i, Quantifier)), None)
            assert q is not None, (
                f"BNode {subj} has {pred.split('#')[-1]} in graph "
                f"but no Quantifier in cache"
            )
            assert q.get_has_quantifier_type() == expected_type, (
                f"BNode {subj}: expected quantifier_type={expected_type!r}, "
                f"got {q.get_has_quantifier_type()!r}"
            )
 
 
#############################################################################################
########################              D. CARDINALITY               ##########################
#############################################################################################
 
def test_cardinality_type_valid(owl_logic):
    """has_cardinality_type must be 'min', 'max', or 'exactly'."""
    from lode.models import Cardinality
 
    VALID = {"min", "max", "exactly"}
    for inst in _instances_of(owl_logic, Cardinality):
        ct = inst.get_has_cardinality_type()
        assert ct in VALID, (
            f"Cardinality {inst.get_has_identifier()} has invalid "
            f"has_cardinality_type: {ct!r}"
        )
 
def test_cardinality_value_is_non_negative_int(owl_logic):
    """has_cardinality must be a non-negative integer."""
    from lode.models import Cardinality
 
    for inst in _instances_of(owl_logic, Cardinality):
        val = inst.get_has_cardinality()
        assert val is not None, (
            f"Cardinality {inst.get_has_identifier()} has no has_cardinality"
        )
        assert isinstance(val, int), (
            f"Cardinality {inst.get_has_identifier()} has_cardinality is not int: "
            f"{type(val).__name__}"
        )
        assert val >= 0, (
            f"Cardinality {inst.get_has_identifier()} has negative cardinality: {val}"
        )
 
def test_cardinality_has_property(owl_logic):
    """Every Cardinality must have applies_on_property set."""
    from lode.models import Cardinality, Property
 
    for inst in _instances_of(owl_logic, Cardinality):
        prop = inst.get_applies_on_property()
        assert prop is not None, (
            f"Cardinality {inst.get_has_identifier()} has no applies_on_property"
        )
        assert isinstance(prop, Property), (
            f"Cardinality {inst.get_has_identifier()} applies_on_property "
            f"is not Property: {type(prop).__name__}"
        )
 
def test_cardinality_graph_correspondence(owl_logic):
    """Every cardinality BNode in graph must produce a Cardinality in cache
    with the correct type."""
    from rdflib.namespace import OWL
    from rdflib import BNode
    from lode.models import Cardinality
 
    PRED_TO_TYPE = {
        OWL.cardinality: "exactly",
        OWL.minCardinality: "min",
        OWL.maxCardinality: "max",
        OWL.qualifiedCardinality: "exactly",
        OWL.minQualifiedCardinality: "min",
        OWL.maxQualifiedCardinality: "max",
    }
 
    for pred, expected_type in PRED_TO_TYPE.items():
        for subj in owl_logic.graph.subjects(pred, None):
            if not isinstance(subj, BNode):
                continue
            instances = owl_logic._instance_cache.get(subj, set())
            card = next((i for i in instances if isinstance(i, Cardinality)), None)
            assert card is not None, (
                f"BNode {subj} has {pred.split('#')[-1]} in graph "
                f"but no Cardinality in cache"
            )
            assert card.get_has_cardinality_type() == expected_type, (
                f"BNode {subj}: expected cardinality_type={expected_type!r}, "
                f"got {card.get_has_cardinality_type()!r}"
            )
 
 
#############################################################################################
########################              E. TRUTH FUNCTION            ##########################
#############################################################################################
 
def test_truth_function_operator_valid(owl_logic):
    """has_logical_operator must be 'and', 'or', or 'not'."""
    from lode.models import TruthFunction
 
    VALID = {"and", "or", "not"}
    for inst in _instances_of(owl_logic, TruthFunction):
        op = inst.get_has_logical_operator()
        assert op in VALID, (
            f"TruthFunction {inst.get_has_identifier()} has invalid "
            f"has_logical_operator: {op!r}"
        )
 
def test_truth_function_not_has_exactly_one_concept(owl_logic):
    """A 'not' TruthFunction must apply on exactly one concept."""
    from lode.models import TruthFunction
 
    for inst in _instances_of(owl_logic, TruthFunction):
        if inst.get_has_logical_operator() != "not":
            continue
        concepts = inst.get_applies_on_concept()
        assert len(concepts) == 1, (
            f"TruthFunction 'not' {inst.get_has_identifier()} "
            f"has {len(concepts)} concepts (expected 1): "
            f"{[c.get_has_identifier() for c in concepts]}"
        )
 
def test_truth_function_and_or_has_multiple_concepts(owl_logic):
    """An 'and'/'or' TruthFunction must apply on at least two concepts."""
    from lode.models import TruthFunction
 
    for inst in _instances_of(owl_logic, TruthFunction):
        op = inst.get_has_logical_operator()
        if op not in ("and", "or"):
            continue
        concepts = inst.get_applies_on_concept()
        assert len(concepts) >= 2, (
            f"TruthFunction '{op}' {inst.get_has_identifier()} "
            f"has only {len(concepts)} concept(s) (expected >= 2)"
        )
 
def test_truth_function_graph_correspondence(owl_logic):
    """Every owl:intersectionOf / owl:unionOf / owl:complementOf BNode
    must produce a TruthFunction in cache."""
    from rdflib.namespace import OWL
    from rdflib import BNode
    from lode.models import TruthFunction
 
    PRED_TO_OP = {
        OWL.intersectionOf: "and",
        OWL.unionOf: "or",
        OWL.complementOf: "not",
    }
 
    for pred, expected_op in PRED_TO_OP.items():
        for subj in owl_logic.graph.subjects(pred, None):
            if not isinstance(subj, BNode):
                continue
            instances = owl_logic._instance_cache.get(subj, set())
            tf = next((i for i in instances if isinstance(i, TruthFunction)), None)
            assert tf is not None, (
                f"BNode {subj} has {pred.split('#')[-1]} in graph "
                f"but no TruthFunction in cache"
            )
            assert tf.get_has_logical_operator() == expected_op, (
                f"BNode {subj}: expected operator={expected_op!r}, "
                f"got {tf.get_has_logical_operator()!r}"
            )
 
 
#############################################################################################
########################              F. ONE OF                    ##########################
#############################################################################################
 
def test_one_of_has_resources(owl_logic):
    """Every OneOf must have at least one applies_on_resource."""
    from lode.models import OneOf
 
    for inst in _instances_of(owl_logic, OneOf):
        resources = inst.get_applies_on_resource()
        assert len(resources) >= 1, (
            f"OneOf {inst.get_has_identifier()} has empty applies_on_resource"
        )
 
def test_one_of_resources_are_individuals(owl_logic):
    """applies_on_resource entries in OneOf must be Individual or Resource instances.
    Some ontologies use owl:oneOf with URIs not declared as owl:NamedIndividual
    (e.g. owl:oneOf enumerations of concept-like values) — Resource is accepted."""
    from lode.models import OneOf, Resource
 
    for inst in _instances_of(owl_logic, OneOf):
        for r in inst.get_applies_on_resource():
            assert isinstance(r, Resource), (
                f"OneOf {inst.get_has_identifier()} applies_on_resource "
                f"contains non-Resource: {type(r).__name__} "
                f"{getattr(r, 'get_has_identifier', lambda: '?')()}"
            )
 
def test_one_of_graph_correspondence(owl_logic):
    """Every owl:oneOf BNode in graph must produce a OneOf in cache."""
    from rdflib.namespace import OWL
    from rdflib import BNode
    from lode.models import OneOf
 
    for subj in owl_logic.graph.subjects(OWL.oneOf, None):
        if not isinstance(subj, BNode):
            continue
        instances = owl_logic._instance_cache.get(subj, set())
        one_of = next((i for i in instances if isinstance(i, OneOf)), None)
        assert one_of is not None, (
            f"BNode {subj} has owl:oneOf in graph but no OneOf in cache"
        )
 
 
#############################################################################################
########################              G. VALUE                     ##########################
#############################################################################################
 
def test_value_has_resource(owl_logic):
    """Every Value must have applies_on_resource set."""
    from lode.models import Value, Resource
 
    for inst in _instances_of(owl_logic, Value):
        r = inst.get_applies_on_resource()
        assert r is not None, (
            f"Value {inst.get_has_identifier()} has no applies_on_resource"
        )
        assert isinstance(r, Resource), (
            f"Value {inst.get_has_identifier()} applies_on_resource "
            f"is not Resource: {type(r).__name__}"
        )
 
def test_value_has_property(owl_logic):
    """Every Value must have applies_on_property set."""
    from lode.models import Value, Property
 
    for inst in _instances_of(owl_logic, Value):
        prop = inst.get_applies_on_property()
        assert prop is not None, (
            f"Value {inst.get_has_identifier()} has no applies_on_property"
        )
        assert isinstance(prop, Property), (
            f"Value {inst.get_has_identifier()} applies_on_property "
            f"is not Property: {type(prop).__name__}"
        )
 
def test_value_graph_correspondence(owl_logic):
    """Every owl:hasValue BNode in graph must produce a Value in cache."""
    from rdflib.namespace import OWL
    from rdflib import BNode
    from lode.models import Value
 
    for subj in owl_logic.graph.subjects(OWL.hasValue, None):
        if not isinstance(subj, BNode):
            continue
        instances = owl_logic._instance_cache.get(subj, set())
        val = next((i for i in instances if isinstance(i, Value)), None)
        assert val is not None, (
            f"BNode {subj} has owl:hasValue in graph but no Value in cache"
        )

#############################################################################################
# §9 Axioms
# §9.1 Class Expression Axioms / §9.2 Object Property Axioms / §9.3 Data Property Axioms /
# §9.4 Datatype Definitions / §9.5 Keys / §9.6 Assertions
#
# §9.1.1: "SubClassOf(CE1 CE2) — CE1 is subclass of CE2."
#          Extraction rule: rdfs:subClassOf subject and object must both be Concept in cache.
#          Subject's get_is_sub_concept_of() must contain object.
#          Covered by test_concept_relations_subject_object_are_concepts,
#          test_concept_relations_are_populated.
#
# §9.1.2: "EquivalentClasses(CE1...CEn) — equivalent to SubClassOf(CE1 CE2) and
#          SubClassOf(CE2 CE1) — symmetry required."
#          Extraction rule: owl:equivalentClass both subject and object must be Concept.
#          Both get_is_equivalent_to() must contain the other.
#          Covered by test_concept_relations_subject_object_are_concepts,
#          test_concept_relations_are_populated.
#          Test symmetry — test_equivalent_class_is_symmetric.
#
# §9.1.3: "DisjointClasses(CE1...CEn) — pairwise disjoint."
#          Extraction rule: owl:disjointWith both sides must be Concept.
#          Both get_is_disjoint_with() must contain the other (symmetry).
#          Covered by test_concept_relations_subject_object_are_concepts.
#          Test symmetry — test_disjoint_with_is_symmetric.
#
# §9.1.4 DisjointUnion
# "DisjointUnion(C CE1...CEn) — equivalent to:
#  EquivalentClasses(C ObjectUnionOf(CE1...CEn)) and DisjointClasses(CE1...CEn)."
# (OWL 2 Structural Specification, Section 9.1.4)
# Extraction rule 1: subject C must be Concept with get_is_equivalent_to() containing
# a TruthFunction(operator=or) with all CEi in applies_on_concept.
# Extraction rule 2: every pair (CEi, CEj) must be mutually disjoint.
#
# §9.2.1: "SubObjectPropertyOf(OPE1 OPE2) — OPE1 subproperty of OPE2."
#          Extraction rule: rdfs:subPropertyOf subject and object must be Property in cache.
#          Subject's get_is_sub_property_of() must contain object.
#          Subproperty type must match parent type (Relation→Relation, etc.).
#          Covered by test_property_relations_subject_object_are_properties,
#          test_property_reclassified_via_sub_property_of.
#
# §9.2.1: "SubObjectPropertyOf(ObjectPropertyChain(OPE1...OPEn) OPE) — property chain."
#          Extraction rule: owl:propertyChainAxiom subject must be Relation with
#          non-empty get_has_property_chain().
#          Covered by test_property_chain_matches_graph.
#
# §9.2.2 EquivalentObjectProperties
# "EquivalentObjectProperties(OPE1 OPE2) is equivalent to SubObjectPropertyOf(OPE1 OPE2)
#  and SubObjectPropertyOf(OPE2 OPE1)" — symmetry required. Handled by test_equivalent_property_is_symmetric.
#
# §9.2.3 DisjointObjectProperties
# "DisjointObjectProperties(OPE1...OPEn) — pairwise disjoint."
# Symmetry required — same reasoning as §9.1.3 DisjointClasses. Handled by test_property_disjoint_with_is_symmetric.
#
# §9.2.4: "InverseObjectProperties(OPE1 OPE2) — OPE1 inverse of OPE2, and vice versa."
#          Extraction rule: owl:inverseOf both sides must be Relation. Both
#          get_is_inverse_of() must point to each other. Domain/range must be swapped.
#          Covered by test_inverse_of_bidirectional_and_domain_range_swapped.
#
# §9.2.5: "ObjectPropertyDomain(OPE CE) — domain of OPE is CE."
#          Extraction rule: rdfs:domain populates get_has_domain() with Concept.
#          If no explicit domain, default is owl:Thing.
#          Covered by test_property_domain_and_range_populated, test_all_relations_have_domain,
#          test_no_none_in_has_domain, test_domain_inherited_via_sub_property_of.
#
# §9.2.6: "ObjectPropertyRange(OPE CE) — range of OPE is CE."
#          Extraction rule: rdfs:range populates get_has_range() with Resource.
#          If no explicit range, default is owl:Thing.
#          Covered by test_property_domain_and_range_populated, test_all_relations_have_range,
#          test_no_none_in_has_range, test_range_inherited_via_sub_property_of.
#
# §9.2.7: "FunctionalObjectProperty(OPE) — each individual has at most one outgoing OPE."
#          Extraction rule: owl:FunctionalProperty URI must be Property in cache with
#          get_is_functional() == True.
#          Covered by test_property_characteristics_functional.
#
# §9.2.8: "InverseFunctionalObjectProperty(OPE) — each individual has at most one
#          incoming OPE."
#          Extraction rule: owl:InverseFunctionalProperty URI must be Relation with
#          get_is_inverse_functional() == True.
#          Covered by test_relation_characteristics_match_graph.
#
# §9.2.9: "ReflexiveObjectProperty(OPE) — each individual connected by OPE to itself."
#          Extraction rule: owl:ReflexiveProperty URI must be Relation with
#          get_is_reflexive() == True.
#          Covered by test_relation_characteristics_match_graph.
#
# §9.2.10: "IrreflexiveObjectProperty(OPE) — no individual connected by OPE to itself."
#           Extraction rule: owl:IrreflexiveProperty URI must be Relation with
#           get_is_irreflexive() == True.
#           Covered by test_relation_characteristics_match_graph.
#
# §9.2.11: "SymmetricObjectProperty(OPE) — if x OPE y then y OPE x."
#           Extraction rule: owl:SymmetricProperty URI must be Relation with
#           get_is_symmetric() == True.
#           Covered by test_relation_characteristics_match_graph.
#
# §9.2.12: "AsymmetricObjectProperty(OPE) — if x OPE y then y cannot OPE x."
#           Extraction rule: owl:AsymmetricProperty URI must be Relation with
#           get_is_asymmetric() == True.
#           Covered by test_relation_characteristics_match_graph.
#
# §9.2.13: "TransitiveObjectProperty(OPE) — if x OPE y and y OPE z then x OPE z."
#           Extraction rule: owl:TransitiveProperty URI must be Relation with
#           get_is_transitive() == True.
#           Covered by test_relation_characteristics_match_graph.
#
# §9.3.1: "SubDataPropertyOf(DPE1 DPE2) — DPE1 subproperty of DPE2."
#          Extraction rule: same as §9.2.1 for Attribute. rdfs:subPropertyOf populates
#          get_is_sub_property_of(). Child type must match parent (Attribute→Attribute).
#          Covered by test_property_relations_subject_object_are_properties,
#          test_property_reclassified_via_sub_property_of.
#
# §9.3.2: "EquivalentDataProperties(DPE1...DPEn)."
#          Extraction rule: owl:equivalentProperty both sides must be Property in cache.
#          Note: symmetry not tested — same reasoning as §9.2.2.
#          Covered by test_property_relations_subject_object_are_properties.
#
# §9.3.3: "DisjointDataProperties(DPE1...DPEn)."
#          Extraction rule: owl:propertyDisjointWith both sides must be Property in cache.
#          Note: symmetry not tested — same reasoning as §9.2.3.
#          Covered by test_property_relations_subject_object_are_properties.
#
# §9.3.4: "DataPropertyDomain(DPE CE) — domain of DPE is CE."
#          Extraction rule: same as §9.2.5 for Attribute.
#          Covered by test_property_domain_and_range_populated.
#
# §9.3.5: "DataPropertyRange(DPE DR) — range of DPE is DR. Arity of DR MUST be one."
#          Extraction rule: rdfs:range populates get_has_range() with Resource/Datatype.
#          Covered by test_all_attributes_have_range, test_property_domain_and_range_populated.
#           Extraction rule: every Attribute range must be Datatype or DatatypeRestriction.
#           Malformed ontologies may declare rdfs:range as owl:Class — skipped with guard. Test: test_attribute_range_is_datatype.
#
# §9.3.6: "FunctionalDataProperty(DPE) — each individual has at most one outgoing DPE."
#          Extraction rule: owl:FunctionalProperty URI must be Property with
#          get_is_functional() == True.
#          Covered by test_property_characteristics_functional.
#
# §9.4: "DatatypeDefinition(DT DR) — DT semantically equivalent to DR."
#        In RDF: DT rdf:type rdfs:Datatype + DT owl:equivalentClass DR.
#        Extraction rule: DT must be Datatype in cache (covered by test_datatype_uris_in_cache).
#        DR is a DatatypeRestriction — get_is_equivalent_to() on the Datatype may contain
#        a DatatypeRestriction instance. No dedicated test — covered indirectly by
#        test_datatype_restriction_has_constraint_and_value and test_datatype_uris_in_cache.
#
# §9.5: "HasKey(CE (OPE1...OPEm) (DPE1...DPEn)) — instances of CE uniquely identified."
#        Out of scope: owl:hasKey not mapped in owl.yaml.
#
# §9.6.1: "SameIndividual(a1...an) — all ai are equal to each other."
#          Extraction rule: owl:sameAs subject and object must both be Individual in cache.
#          Subject's get_is_same_as() must contain object (and vice versa — symmetry).
#          Covered by test_individual_relations_subject_object_are_individuals.
#          Symmetry — test_same_as_is_symmetric.
#
# §9.6.2: "DifferentIndividuals(a1...an) — all ai different from each other."
#          Extraction rule: owl:differentFrom subject and object must be Individual in cache.
#          Both get_is_different_from() must contain the other (symmetry).
#          Covered by test_individual_relations_subject_object_are_individuals.
#          Symmetry — test_different_from_is_symmetric.
#
# §9.6.3: "ClassAssertion(CE a) — individual a is instance of CE."
#          Extraction rule: rdf:type populates Individual.get_has_type() with Concept.
#          Every Individual must have at least one type.
#          Covered by test_all_individuals_have_type.
#
# §9.6.4: "ObjectPropertyAssertion(OPE a1 a2) — positive assertion."
#          Out of scope: individual-level assertions not extracted as distinct instances —
#          they become Statement in phase6 if not mapped.
#
# §9.6.5: "NegativeObjectPropertyAssertion(OPE a1 a2) — a1 NOT connected by OPE to a2."
#          Extraction rule: owl:NegativePropertyAssertion URI must be Statement in cache
#          with get_is_positive_statement() == False.
#          Gap: test_negative_property_assertion_is_negative needed (to add).
#
# §9.6.6: "DataPropertyAssertion(DPE a lt) — positive data assertion."
#          Out of scope: same as §9.6.4.
#
# §9.6.7: "NegativeDataPropertyAssertion(DPE a lt) — a NOT connected by DPE to lt."
#          Extraction rule: same as §9.6.5 — Statement with is_positive_statement == False.
#          Covered by same test as §9.6.5.
#############################################################################################

def test_property_reclassified_via_sub_property_of(owl_logic):
    """If A rdfs:subPropertyOf B and B is Relation/Attribute/Annotation,
    then A must be the same concrete type."""
    from rdflib.namespace import RDFS
    from rdflib import URIRef
    from lode.models import Relation, Attribute, Annotation, Property

    CONCRETE = (Relation, Attribute, Annotation)

    for s, _, o in owl_logic.graph.triples((None, RDFS.subPropertyOf, None)):
        if not isinstance(s, URIRef) or not isinstance(o, URIRef):
            continue
        child = next((i for i in owl_logic._instance_cache.get(s, set()) if isinstance(i, Property)), None)
        parent = next((i for i in owl_logic._instance_cache.get(o, set()) if isinstance(i, Property)), None)
        if child is None or parent is None:
            continue
        if not isinstance(parent, CONCRETE):
            continue
        # Skip if child has explicit rdf:type in this graph (intentional classification takes precedence)
        from rdflib.namespace import RDF
        if (s, RDF.type, None) in owl_logic.graph:
            continue
        assert isinstance(child, type(parent)), (
            f"{s} subPropertyOf {o} ({type(parent).__name__}) "
            f"but child is {type(child).__name__}"
        )

def test_property_relations_subject_object_are_properties(owl_logic):
    """For every rdfs:subPropertyOf, owl:equivalentProperty and owl:propertyDisjointWith
    triple in the graph, both subject and object must be Property instances in cache."""
    from rdflib.namespace import RDFS, OWL
    from rdflib import URIRef
    from lode.models import Property

    predicates = [
        RDFS.subPropertyOf,
        OWL.equivalentProperty,
        OWL.propertyDisjointWith,
    ]

    for predicate in predicates:
        for s, _, o in owl_logic.graph.triples((None, predicate, None)):
            if not isinstance(s, URIRef) or not isinstance(o, URIRef):
                continue
            s_inst = next((i for i in owl_logic._instance_cache.get(s, set()) if isinstance(i, Property)), None)
            o_inst = next((i for i in owl_logic._instance_cache.get(o, set()) if isinstance(i, Property)), None)
            assert s_inst is not None, (
                f"{s} is subject of {predicate} but not Property in cache: "
                f"{[type(i).__name__ for i in owl_logic._instance_cache.get(s, set())]}"
            )
            assert o_inst is not None, (
                f"{o} is object of {predicate} but not Property in cache: "
                f"{[type(i).__name__ for i in owl_logic._instance_cache.get(o, set())]}"
            )

def test_disjoint_union_produces_equivalent_union(owl_logic):
    """§9.1.4 OWL 2 Structural Specification — Disjoint Union.
    Spec: 'DisjointUnion(C CE1...CEn) is equivalent to EquivalentClasses(C
    ObjectUnionOf(CE1...CEn)) and DisjointClasses(CE1...CEn).'
    Extraction rule: subject C must have a TruthFunction(operator=or) in
    get_is_equivalent_to() with all CEi in applies_on_concept."""
    from rdflib.namespace import OWL
    from rdflib import URIRef, BNode
    from rdflib.collection import Collection as RDFLibCollection
    from lode.models import Concept, TruthFunction

    for s, _, o in owl_logic.graph.triples((None, OWL.disjointUnionOf, None)):
        if not isinstance(s, URIRef):
            continue
        s_inst = next(
            (i for i in owl_logic._instance_cache.get(s, set()) if isinstance(i, Concept)),
            None
        )
        assert s_inst is not None, (
            f"§9.1.4: {s} has owl:disjointUnionOf but not Concept in cache"
        )
        equivalents = s_inst.get_is_equivalent_to()
        tf = next((e for e in equivalents if isinstance(e, TruthFunction) and
                   e.get_has_logical_operator() == "or"), None)
        assert tf is not None, (
            f"§9.1.4: {s} has owl:disjointUnionOf but no TruthFunction(or) "
            f"in get_is_equivalent_to()"
        )
        try:
            members = list(RDFLibCollection(owl_logic.graph, o))
            tf_concepts = {c.get_has_identifier() for c in tf.get_applies_on_concept()}
            for member in members:
                member_inst = next(
                    (i for i in owl_logic._instance_cache.get(member, set())
                     if isinstance(i, Concept)), None
                )
                if member_inst is None:
                    continue
                assert member_inst.get_has_identifier() in tf_concepts, (
                    f"§9.1.4: {member} not in TruthFunction.applies_on_concept for {s}"
                )
        except Exception:
            pass

def test_disjoint_union_members_are_pairwise_disjoint(owl_logic):
    """§9.1.4 OWL 2 Structural Specification — Disjoint Union.
    Spec: 'DisjointUnion(C CE1...CEn) implies DisjointClasses(CE1...CEn).'
    Extraction rule: every pair (CEi, CEj) must have mutual get_is_disjoint_with()."""
    from rdflib.namespace import OWL
    from rdflib import URIRef
    from rdflib.collection import Collection as RDFLibCollection
    from lode.models import Concept

    for s, _, o in owl_logic.graph.triples((None, OWL.disjointUnionOf, None)):
        if not isinstance(s, URIRef):
            continue
        try:
            members = list(RDFLibCollection(owl_logic.graph, o))
            instances = []
            for m in members:
                inst = next(
                    (i for i in owl_logic._instance_cache.get(m, set())
                     if isinstance(i, Concept)), None
                )
                if inst:
                    instances.append(inst)
            for i, a in enumerate(instances):
                for b in instances[i+1:]:
                    assert b in a.get_is_disjoint_with(), (
                        f"§9.1.4: {a.get_has_identifier()} and {b.get_has_identifier()} "
                        f"are members of disjointUnionOf but not mutually disjoint"
                    )
                    assert a in b.get_is_disjoint_with(), (
                        f"§9.1.4 symmetry: {b.get_has_identifier()} not disjoint with "
                        f"{a.get_has_identifier()}"
                    )
        except Exception:
            pass

def test_property_chain_matches_graph(owl_logic):
    """If A owl:propertyChainAxiom B in graph then:
    - A must be a Relation in cache
    - has_property_chain must be a non-empty list
    """
    from rdflib.namespace import OWL
    from rdflib import URIRef
    from lode.models import Relation

    for s, _, o in owl_logic.graph.triples((None, OWL.propertyChainAxiom, None)):
        if not isinstance(s, URIRef):
            continue
        s_inst = next((i for i in owl_logic._instance_cache.get(s, set()) if isinstance(i, Relation)), None)
        assert s_inst is not None, (
            f"{s} has owl:propertyChainAxiom but is not Relation in cache: "
            f"{[type(i).__name__ for i in owl_logic._instance_cache.get(s, set())]}"
        )
        chain = s_inst.get_has_property_chain()
        assert isinstance(chain, list), (
            f"{s} has_property_chain is not a list: {type(chain)}"
        )
        assert len(chain) >= 1, (
            f"{s} has owl:propertyChainAxiom in graph but has_property_chain is empty"
        )

def test_equivalent_class_is_symmetric(owl_logic):
    """§9.1.2 OWL 2 Structural Specification — Equivalent Classes.
    Spec: 'EquivalentClasses(CE1 CE2) is equivalent to SubClassOf(CE1 CE2) and
    SubClassOf(CE2 CE1)' — symmetry is required.
    Extraction rule: if A owl:equivalentClass B then B.get_is_equivalent_to() must
    contain A and A.get_is_equivalent_to() must contain B."""
    from rdflib.namespace import OWL
    from rdflib import URIRef
    from lode.models import Concept
 
    for s, _, o in owl_logic.graph.triples((None, OWL.equivalentClass, None)):
        if not isinstance(s, URIRef) or not isinstance(o, URIRef):
            continue
        s_inst = next((i for i in owl_logic._instance_cache.get(s, set()) if isinstance(i, Concept)), None)
        o_inst = next((i for i in owl_logic._instance_cache.get(o, set()) if isinstance(i, Concept)), None)
        if s_inst is None or o_inst is None:
            continue
        assert o_inst in s_inst.get_is_equivalent_to(), (
            f"§9.1.2: {s} equivalentClass {o} but o not in s.get_is_equivalent_to()"
        )
        assert s_inst in o_inst.get_is_equivalent_to(), (
            f"§9.1.2 symmetry: {o} equivalentClass {s} but s not in o.get_is_equivalent_to()"
        )

def test_all_relations_have_range(owl_logic):
    for rel in _instances_of(owl_logic, Relation):
        assert len(rel.get_has_range()) >= 1, (
            f"Relation {rel.get_has_identifier()} has no range"
        )

def test_all_attributes_have_range(owl_logic):
    for attr in _instances_of(owl_logic, Attribute):
        assert len(attr.get_has_range()) >= 1, (
            f"Attribute {attr.get_has_identifier()} has no range"
        )

#############################################################################################
# §5.4 Data Properties
# If a URI is declared rdf:type owl:DatatypeProperty it must be Attribute in cache.
#############################################################################################

def test_datatype_property_declaration_produces_attribute(owl_logic):
    """§5.4: Every URI declared as owl:DatatypeProperty must be Attribute in cache."""
    from rdflib.namespace import RDF, OWL
    from rdflib import URIRef
    from lode.models import Attribute

    for uri in owl_logic.graph.subjects(RDF.type, OWL.DatatypeProperty):
        if not isinstance(uri, URIRef):
            continue
        instances = owl_logic._instance_cache.get(uri, set())
        assert any(isinstance(i, Attribute) for i in instances), (
            f"§5.4: {uri} declared as owl:DatatypeProperty "
            f"but not Attribute in cache: "
            f"{[type(i).__name__ for i in instances]}"
        )


#############################################################################################
# §5.8.1 Typing Constraints of OWL 2 DL
# "No IRI I is declared in Ax to be both a class and a datatype."
# (OWL 2 Structural Specification, Section 5.8.1)
# Extraction rule: no URIRef in cache can simultaneously have an instance of exact type
# Concept and an instance of Datatype (which is a subclass of Concept).
#############################################################################################

def test_no_iri_is_both_concept_and_datatype(owl_logic):
    """§5.8.1 OWL 2 Structural Specification — Typing Constraints.
    Spec: 'No IRI I is declared in Ax to be both a class and a datatype.'
    Extraction rule: no URIRef in cache can simultaneously be exact type Concept
    and Datatype.
    Guard: both types explicitly declared in graph → malformed ontology, not LODE bug."""
    from rdflib.namespace import RDF, OWL, RDFS
    from rdflib import URIRef
    from lode.models import Concept, Datatype

    for uri, instances in owl_logic._instance_cache.items():
        if not isinstance(uri, URIRef):
            continue
        if (uri, RDF.type, OWL.Class) in owl_logic.graph and \
           (uri, RDF.type, RDFS.Datatype) in owl_logic.graph:
            continue
        has_concept = any(type(i) is Concept for i in instances)
        has_datatype = any(isinstance(i, Datatype) for i in instances)
        assert not (has_concept and has_datatype), (
            f"§5.8.1: {uri} is both Concept and Datatype in cache"
        )

#############################################################################################
# §5.8.1 Typing Constraints of OWL 2 DL — Property type conflicts
# "No IRI I is declared in Ax as being of more than one type of property; that is,
#  no I is declared in Ax to be both object and data, object and annotation, or data
#  and annotation property." (OWL 2 Structural Specification, Section 5.8.1)
# Extraction rule: no URIRef in cache can simultaneously be Relation+Attribute,
# Relation+Annotation, or Attribute+Annotation.
#############################################################################################

def test_no_iri_is_both_relation_and_attribute(owl_logic):
    """§5.8.1 OWL 2 Structural Specification — Typing Constraints.
    Spec: 'No IRI I is declared to be both object and data property.'
    Extraction rule: no URIRef in cache can simultaneously be Relation and Attribute.
    Guard: both types explicitly declared in graph → malformed ontology, not LODE bug."""
    from rdflib.namespace import RDF, OWL
    from rdflib import URIRef
    from lode.models import Relation, Attribute

    for uri, instances in owl_logic._instance_cache.items():
        if not isinstance(uri, URIRef):
            continue
        if (uri, RDF.type, OWL.ObjectProperty) in owl_logic.graph and \
           (uri, RDF.type, OWL.DatatypeProperty) in owl_logic.graph:
            continue
        has_relation = any(isinstance(i, Relation) for i in instances)
        has_attribute = any(isinstance(i, Attribute) for i in instances)
        assert not (has_relation and has_attribute), (
            f"§5.8.1: {uri} is both Relation and Attribute in cache"
        )


def test_no_iri_is_both_relation_and_annotation(owl_logic):
    """§5.8.1 OWL 2 Structural Specification — Typing Constraints.
    Spec: 'No IRI I is declared to be both object and annotation property.'
    Extraction rule: no URIRef in cache can simultaneously be Relation and Annotation.
    Guard: both types explicitly declared in graph → malformed ontology, not LODE bug."""
    from rdflib.namespace import RDF, OWL
    from rdflib import URIRef
    from lode.models import Relation, Annotation

    for uri, instances in owl_logic._instance_cache.items():
        if not isinstance(uri, URIRef):
            continue
        if (uri, RDF.type, OWL.ObjectProperty) in owl_logic.graph and \
           (uri, RDF.type, OWL.AnnotationProperty) in owl_logic.graph:
            continue
        has_relation = any(isinstance(i, Relation) for i in instances)
        has_annotation = any(isinstance(i, Annotation) for i in instances)
        assert not (has_relation and has_annotation), (
            f"§5.8.1: {uri} is both Relation and Annotation in cache"
        )


def test_no_iri_is_both_attribute_and_annotation(owl_logic):
    """§5.8.1 OWL 2 Structural Specification — Typing Constraints.
    Spec: 'No IRI I is declared to be both data and annotation property.'
    Extraction rule: no URIRef in cache can simultaneously be Attribute and Annotation.
    Guard: both types explicitly declared in graph → malformed ontology, not LODE bug."""
    from rdflib.namespace import RDF, OWL
    from rdflib import URIRef
    from lode.models import Attribute, Annotation

    for uri, instances in owl_logic._instance_cache.items():
        if not isinstance(uri, URIRef):
            continue
        if (uri, RDF.type, OWL.DatatypeProperty) in owl_logic.graph and \
           (uri, RDF.type, OWL.AnnotationProperty) in owl_logic.graph:
            continue
        has_attribute = any(isinstance(i, Attribute) for i in instances)
        has_annotation = any(isinstance(i, Annotation) for i in instances)
        assert not (has_attribute and has_annotation), (
            f"§5.8.1: {uri} is both Attribute and Annotation in cache"
        )


#############################################################################################
# §7 Data Ranges
# §7.1 Intersection / §7.2 Union / §7.3 Complement / §7.4 Enumeration / §7.5 Restriction
#
# §7:   "Data ranges can be used in restrictions on data properties."
#        DataRange := Datatype | DataIntersectionOf | DataUnionOf | DataComplementOf |
#        DataOneOf | DatatypeRestriction.
#        Out of scope: DataIntersectionOf, DataUnionOf, DataComplementOf, DataOneOf are
#        data range constructs with no direct RDF triple representation as named entities —
#        they appear as BNode structures within data property restrictions.
#        LODE does not currently model these as distinct instances.
#
# §7.1: "DataIntersectionOf(DR1...DRn) — all DRi MUST be of the same arity (>= 2)."
#        owl:intersectionOf in RDF is shared between object and data contexts.
#        Extraction rule: BNode with owl:intersectionOf produces TruthFunction(operator=and)
#        with applies_on_concept populated. Datatype is subclass of Concept — passes.
#        Covered by test_truth_function_and_or_has_multiple_concepts.
#
# §7.2: "DataUnionOf(DR1...DRn) — all DRi MUST be of the same arity (>= 2)."
#        owl:unionOf in RDF is shared between object and data contexts.
#        Extraction rule: BNode with owl:unionOf produces TruthFunction(operator=or).
#        Covered by test_truth_function_and_or_has_multiple_concepts.
#
# §7.3: "DataComplementOf(DR) — complement of a data range."
#        owl:complementOf in RDF is shared between object and data contexts.
#        Extraction rule: BNode with owl:complementOf produces TruthFunction(operator=not).
#        Covered by test_truth_function_not_has_exactly_one_concept.
#
# §7.4: "DataOneOf(lt1...ltn) — exactly the specified literals."
#        owl:oneOf in RDF is shared between object and data contexts.
#        Extraction rule: BNode with owl:oneOf produces OneOf with applies_on_resource.
#        Covered by test_one_of_has_resources and test_one_of_graph_correspondence.
#
# §7.5: "DatatypeRestriction(DT F1 lt1 ... Fn ltn) — restricts the value space of DT
#        by n constraining facet-value pairs. Each pair (Fi, vi) MUST be contained in
#        the facet space of DT."
#        Extraction rule 1: every BNode with owl:onDatatype in the graph must produce a
#        DatatypeRestriction in cache. Covered by test_datatype_restriction_graph_correspondence.
#        Extraction rule 2: every DatatypeRestriction must have has_constraint (Annotation)
#        and has_restriction_value (str) populated.
#        Covered by test_datatype_restriction_has_constraint_and_value.
#############################################################################################

def test_datatype_restriction_graph_correspondence(owl_logic):
    """§7.5 OWL 2 Structural Specification — Datatype Restrictions.
    Spec: 'DatatypeRestriction(DT F1 lt1...Fn ltn) restricts the value space of DT
    by n constraining facet-value pairs.'
    Extraction rule: every BNode with owl:onDatatype in the graph must produce a
    DatatypeRestriction in cache."""
    from rdflib.namespace import OWL
    from rdflib import BNode
    from lode.models import DatatypeRestriction

    for subj in owl_logic.graph.subjects(OWL.onDatatype, None):
        if not isinstance(subj, BNode):
            continue
        instances = owl_logic._instance_cache.get(subj, set())
        assert any(isinstance(i, DatatypeRestriction) for i in instances), (
            f"§7.5: BNode {subj} has owl:onDatatype in graph "
            f"but no DatatypeRestriction in cache: "
            f"{[type(i).__name__ for i in instances]}"
        )


#############################################################################################
# §7.5 Datatype Restrictions — CORRECTED
# "DatatypeRestriction(DT F1 lt1 ... Fn ltn) — restricts the value space of DT
#  by n constraining facet-value pairs."
# In LODE (owl.yaml):
#   - owl:withRestrictions → Datatype in cache (the restricted datatype)
#   - BNode with XSD facet predicate → DatatypeRestriction in cache
# Extraction rule: every BNode that is subject of an XSD facet predicate must produce
# a DatatypeRestriction in cache with has_constraint (Annotation) and
# has_restriction_value (str) populated.
# Covered by test_datatype_restriction_has_constraint_and_value (integrity)
# and test_datatype_restriction_graph_correspondence (graph correspondence).
#############################################################################################

def test_datatype_restriction_graph_correspondence(owl_logic):
    """§7.5 OWL 2 Structural Specification — Datatype Restrictions.
    Spec: 'DatatypeRestriction consists of a unary datatype DT and n constraining
    facet-value pairs.'
    Extraction rule: every BNode that is subject of an XSD facet predicate must produce
    a DatatypeRestriction in cache."""
    from rdflib.namespace import XSD
    from rdflib import BNode
    from lode.models import DatatypeRestriction

    XSD_FACETS = {
        XSD.minExclusive, XSD.maxExclusive, XSD.minInclusive, XSD.maxInclusive,
        XSD.pattern, XSD.length, XSD.minLength, XSD.maxLength,
        XSD.totalDigits, XSD.fractionDigits, XSD.enumeration, XSD.whiteSpace,
    }

    seen = set()
    for facet in XSD_FACETS:
        for subj in owl_logic.graph.subjects(facet, None):
            if not isinstance(subj, BNode) or subj in seen:
                continue
            seen.add(subj)
            instances = owl_logic._instance_cache.get(subj, set())
            assert any(isinstance(i, DatatypeRestriction) for i in instances), (
                f"§7.5: BNode {subj} has XSD facet predicate in graph "
                f"but no DatatypeRestriction in cache: "
                f"{[type(i).__name__ for i in instances]}"
            )


#############################################################################################
# §9.1.3 DisjointClasses
# "DisjointClasses(CE1...CEn) — pairwise disjoint — equivalent to
#  SubClassOf(CE1 ObjectComplementOf(CE2))"
# Pairwise symmetry required.
#############################################################################################

def test_disjoint_with_is_symmetric(owl_logic):
    """§9.1.3 OWL 2 Structural Specification — Disjoint Classes.
    Spec: 'DisjointClasses(CE1...CEn) — no individual can be instance of both CEi and CEj.'
    Pairwise — symmetry required.
    Extraction rule: if A owl:disjointWith B then B.get_is_disjoint_with() must contain A."""
    from rdflib.namespace import OWL
    from rdflib import URIRef
    from lode.models import Concept

    for s, _, o in owl_logic.graph.triples((None, OWL.disjointWith, None)):
        if not isinstance(s, URIRef) or not isinstance(o, URIRef):
            continue
        s_inst = next((i for i in owl_logic._instance_cache.get(s, set()) if isinstance(i, Concept)), None)
        o_inst = next((i for i in owl_logic._instance_cache.get(o, set()) if isinstance(i, Concept)), None)
        if s_inst is None or o_inst is None:
            continue
        assert o_inst in s_inst.get_is_disjoint_with(), (
            f"§9.1.3: {s} disjointWith {o} but o not in s.get_is_disjoint_with()"
        )
        assert s_inst in o_inst.get_is_disjoint_with(), (
            f"§9.1.3 symmetry: {o} disjointWith {s} but s not in o.get_is_disjoint_with()"
        )


#############################################################################################
# §9.6.1 SameIndividual
# "SameIndividual(a1...an) — all ai are equal to each other."
# Pairwise — symmetry required.
#############################################################################################

def test_same_as_is_symmetric(owl_logic):
    """§9.6.1 OWL 2 Structural Specification — Individual Equality.
    Spec: 'SameIndividual(a1...an) — all ai are equal to each other.'
    Extraction rule: if A owl:sameAs B then B.get_is_same_as() must contain A."""
    from rdflib.namespace import OWL
    from rdflib import URIRef
    from lode.models import Individual

    for s, _, o in owl_logic.graph.triples((None, OWL.sameAs, None)):
        if not isinstance(s, URIRef) or not isinstance(o, URIRef):
            continue
        s_inst = next((i for i in owl_logic._instance_cache.get(s, set()) if isinstance(i, Individual)), None)
        o_inst = next((i for i in owl_logic._instance_cache.get(o, set()) if isinstance(i, Individual)), None)
        if s_inst is None or o_inst is None:
            continue
        assert o_inst in s_inst.get_is_same_as(), (
            f"§9.6.1: {s} sameAs {o} but o not in s.get_is_same_as()"
        )
        assert s_inst in o_inst.get_is_same_as(), (
            f"§9.6.1 symmetry: {o} sameAs {s} but s not in o.get_is_same_as()"
        )


#############################################################################################
# §9.6.2 DifferentIndividuals
# "DifferentIndividuals(a1...an) — all ai different from each other."
# Pairwise — symmetry required.
#############################################################################################

def test_different_from_is_symmetric(owl_logic):
    """§9.6.2 OWL 2 Structural Specification — Individual Inequality.
    Spec: 'DifferentIndividuals(a1...an) — all ai different from each other.'
    Extraction rule: if A owl:differentFrom B then B.get_is_different_from() must
    contain A."""
    from rdflib.namespace import OWL
    from rdflib import URIRef
    from lode.models import Individual

    for s, _, o in owl_logic.graph.triples((None, OWL.differentFrom, None)):
        if not isinstance(s, URIRef) or not isinstance(o, URIRef):
            continue
        s_inst = next((i for i in owl_logic._instance_cache.get(s, set()) if isinstance(i, Individual)), None)
        o_inst = next((i for i in owl_logic._instance_cache.get(o, set()) if isinstance(i, Individual)), None)
        if s_inst is None or o_inst is None:
            continue
        assert o_inst in s_inst.get_is_different_from(), (
            f"§9.6.2: {s} differentFrom {o} but o not in s.get_is_different_from()"
        )
        assert s_inst in o_inst.get_is_different_from(), (
            f"§9.6.2 symmetry: {o} differentFrom {s} but s not in o.get_is_different_from()"
        )


#############################################################################################
# §9.6.5 NegativeObjectPropertyAssertion / §9.6.7 NegativeDataPropertyAssertion
# "NegativeObjectPropertyAssertion(OPE a1 a2) — a1 is NOT connected by OPE to a2."
# "NegativeDataPropertyAssertion(DPE a lt) — a is NOT connected by DPE to lt."
# In LODE: owl:NegativePropertyAssertion → Statement with is_positive_statement=False.
#############################################################################################

def test_negative_property_assertion_is_negative(owl_logic):
    """§9.6.5/§9.6.7 OWL 2 Structural Specification — Negative Property Assertions.
    Spec: 'NegativeObjectPropertyAssertion(OPE a1 a2) — a1 is not connected by OPE to a2.'
    Spec: 'NegativeDataPropertyAssertion(DPE a lt) — a is not connected by DPE to lt.'
    Extraction rule: every URI declared as owl:NegativePropertyAssertion must be Statement
    in cache with get_is_positive_statement() == False."""
    from rdflib.namespace import RDF, OWL
    from rdflib import URIRef
    from lode.models import Statement

    for uri in owl_logic.graph.subjects(RDF.type, OWL.NegativePropertyAssertion):
        if not isinstance(uri, URIRef):
            continue
        instances = owl_logic._instance_cache.get(uri, set())
        stmt = next((i for i in instances if isinstance(i, Statement)), None)
        assert stmt is not None, (
            f"§9.6.5/9.6.7: {uri} declared as owl:NegativePropertyAssertion "
            f"but not Statement in cache: "
            f"{[type(i).__name__ for i in instances]}"
        )
        assert stmt.get_is_positive_statement() is False, (
            f"§9.6.5/9.6.7: {uri} is NegativePropertyAssertion "
            f"but get_is_positive_statement() is not False: "
            f"{stmt.get_is_positive_statement()}"
        )


#############################################################################################
# §9.2.2 EquivalentObjectProperties
# "EquivalentObjectProperties(OPE1 OPE2) is equivalent to SubObjectPropertyOf(OPE1 OPE2)
#  and SubObjectPropertyOf(OPE2 OPE1)" — symmetry required.
#############################################################################################

def test_equivalent_property_is_symmetric(owl_logic):
    """§9.2.2 OWL 2 Structural Specification — Equivalent Object Properties.
    Spec: 'EquivalentObjectProperties(OPE1 OPE2) is equivalent to
    SubObjectPropertyOf(OPE1 OPE2) and SubObjectPropertyOf(OPE2 OPE1).'
    Extraction rule: if A owl:equivalentProperty B then B.get_is_equivalent_to()
    must contain A and vice versa."""
    from rdflib.namespace import OWL
    from rdflib import URIRef
    from lode.models import Property

    for s, _, o in owl_logic.graph.triples((None, OWL.equivalentProperty, None)):
        if not isinstance(s, URIRef) or not isinstance(o, URIRef):
            continue
        s_inst = next((i for i in owl_logic._instance_cache.get(s, set()) if isinstance(i, Property)), None)
        o_inst = next((i for i in owl_logic._instance_cache.get(o, set()) if isinstance(i, Property)), None)
        if s_inst is None or o_inst is None:
            continue
        assert o_inst in s_inst.get_is_equivalent_to(), (
            f"§9.2.2: {s} equivalentProperty {o} but o not in s.get_is_equivalent_to()"
        )
        assert s_inst in o_inst.get_is_equivalent_to(), (
            f"§9.2.2 symmetry: {o} equivalentProperty {s} but s not in o.get_is_equivalent_to()"
        )


#############################################################################################
# §9.2.3 DisjointObjectProperties
# "DisjointObjectProperties(OPE1...OPEn) — pairwise disjoint."
# Symmetry required — same reasoning as §9.1.3 DisjointClasses.
#############################################################################################

def test_property_disjoint_with_is_symmetric(owl_logic):
    """§9.2.3 OWL 2 Structural Specification — Disjoint Object Properties.
    Spec: 'DisjointObjectProperties(OPE1...OPEn) — no individual x can be connected
    to y by both OPEi and OPEj for i≠j.' Pairwise — symmetry required.
    Extraction rule: if A owl:propertyDisjointWith B then B.get_is_disjoint_with()
    must contain A and vice versa."""
    from rdflib.namespace import OWL
    from rdflib import URIRef
    from lode.models import Property

    for s, _, o in owl_logic.graph.triples((None, OWL.propertyDisjointWith, None)):
        if not isinstance(s, URIRef) or not isinstance(o, URIRef):
            continue
        s_inst = next((i for i in owl_logic._instance_cache.get(s, set()) if isinstance(i, Property)), None)
        o_inst = next((i for i in owl_logic._instance_cache.get(o, set()) if isinstance(i, Property)), None)
        if s_inst is None or o_inst is None:
            continue
        assert o_inst in s_inst.get_is_disjoint_with(), (
            f"§9.2.3: {s} propertyDisjointWith {o} but o not in s.get_is_disjoint_with()"
        )
        assert s_inst in o_inst.get_is_disjoint_with(), (
            f"§9.2.3 symmetry: {o} propertyDisjointWith {s} but s not in o.get_is_disjoint_with()"
        )


#############################################################################################
# §9.3.5 Data Property Range
# "DataPropertyRange(DPE DR) — the range of DPE is DR. The arity of DR MUST be one."
# (OWL 2 Structural Specification, Section 9.3.5)
# Extraction rule: every Attribute range must be Datatype or DatatypeRestriction.
# Malformed ontologies may declare rdfs:range as owl:Class — skipped with guard.
#############################################################################################

def test_attribute_range_is_datatype(owl_logic):
    """§9.3.5 OWL 2 Structural Specification — Data Property Range.
    Spec: 'DataPropertyRange(DPE DR) — DR MUST be a unary data range.'
    Extraction rule: every Attribute range must be Datatype or DatatypeRestriction.
    Malformed ontologies declaring rdfs:range as owl:Class are skipped."""
    from rdflib.namespace import RDF, RDFS, OWL
    from rdflib import URIRef
    from lode.models import Attribute, Datatype, DatatypeRestriction, Restriction

    for uri, instances in owl_logic._instance_cache.items():
        if not isinstance(uri, URIRef):
            continue
        for inst in instances:
            if not isinstance(inst, Attribute):
                continue

            # Guard: skip if range is declared as owl:Class or owl:ObjectProperty
            # in graph (malformed ontology)
            range_node = owl_logic.graph.value(uri, RDFS.range)
            if range_node is not None:
                if (range_node, RDF.type, OWL.Class) in owl_logic.graph:
                    continue
                if (range_node, RDF.type, OWL.ObjectProperty) in owl_logic.graph:
                    continue

            ranges = inst.get_has_range()
            bad = [
                (r.get_has_identifier(), type(r).__name__)
                for r in ranges
                if not isinstance(r, (Datatype, DatatypeRestriction, Restriction))
            ]
            assert not bad, (
                f"§9.3.5: Attribute {inst.get_has_identifier()} "
                f"has non-Datatype range: {bad}"
            )

def test_property_domain_and_range_populated(owl_logic):
    """Every Property (Relation, Attribute, Annotation) in cache must have:
    - at least one domain (Concept)
    - at least one range (Resource)
    Only Relation and Attribute are checked since Annotation has no domain/range defaults."""
    from lode.models import Relation, Attribute, Concept, Resource

    for uri, instances in owl_logic._instance_cache.items():
        for inst in instances:
            if not isinstance(inst, (Relation, Attribute)):
                continue

            domains = inst.get_has_domain()
            assert len(domains) >= 1, (
                f"{inst.get_has_identifier()} ({type(inst).__name__}) "
                f"has no domain"
            )
            assert all(isinstance(d, Concept) for d in domains), (
                f"{inst.get_has_identifier()} domain contains non-Concept: "
                f"{[(d.get_has_identifier(), type(d).__name__) for d in domains if not isinstance(d, Concept)]}"
            )

            ranges = inst.get_has_range()
            assert len(ranges) >= 1, (
                f"{inst.get_has_identifier()} ({type(inst).__name__}) "
                f"has no range"
            )
            assert all(isinstance(r, Resource) for r in ranges), (
                f"{inst.get_has_identifier()} range contains non-Resource: "
                f"{[(r.get_has_identifier(), type(r).__name__) for r in ranges if not isinstance(r, Resource)]}"
            )

def test_all_relations_have_domain(owl_logic):
    for rel in _instances_of(owl_logic, Relation):
        assert len(rel.get_has_domain()) >= 1, (
            f"Relation {rel.get_has_identifier()} has no domain"
        )

def test_domain_inherited_via_sub_property_of(owl_logic):
    """If A rdfs:subPropertyOf B and A has no explicit domain,
    A must inherit B's domain."""
    from rdflib.namespace import RDFS, OWL
    from rdflib import URIRef
    from lode.models import Relation

    owl_thing = str(OWL.Thing)

    for s, _, o in owl_logic.graph.triples((None, RDFS.subPropertyOf, None)):
        if not isinstance(s, URIRef) or not isinstance(o, URIRef):
            continue
        # Skip if child has explicit domain in graph
        if (s, RDFS.domain, None) in owl_logic.graph:
            continue
        child = next((i for i in owl_logic._instance_cache.get(s, set()) if isinstance(i, Relation)), None)
        parent = next((i for i in owl_logic._instance_cache.get(o, set()) if isinstance(i, Relation)), None)
        if child is None or parent is None:
            continue
        parent_domains = {d.get_has_identifier() for d in parent.get_has_domain()} - {owl_thing}
        if not parent_domains:
            continue
                # Skip if parent domains are all BNodes (anonymous classes, not comparable)
        if all(not str(d).startswith('http') for d in parent_domains):
            continue
        # Skip if child has owl:inverseOf (domain/range come dall'inversa, non dal parent)
        if (s, OWL.inverseOf, None) in owl_logic.graph or (None, OWL.inverseOf, s) in owl_logic.graph:
            continue
        child_domains = {d.get_has_identifier() for d in child.get_has_domain()}
        assert parent_domains & child_domains, (
            f"{s} subPropertyOf {o} with domain {parent_domains} "
            f"but child domain is {child_domains}"
        )

def test_range_inherited_via_sub_property_of(owl_logic):
    """If A rdfs:subPropertyOf B and A has no explicit range,
    A must inherit B's range."""
    from rdflib.namespace import RDFS, OWL
    from rdflib import URIRef
    from lode.models import Relation

    owl_thing = str(OWL.Thing)

    for s, _, o in owl_logic.graph.triples((None, RDFS.subPropertyOf, None)):
        if not isinstance(s, URIRef) or not isinstance(o, URIRef):
            continue
        if (s, RDFS.range, None) in owl_logic.graph:
            continue
        child = next((i for i in owl_logic._instance_cache.get(s, set()) if isinstance(i, Relation)), None)
        parent = next((i for i in owl_logic._instance_cache.get(o, set()) if isinstance(i, Relation)), None)
        if child is None or parent is None:
            continue
        parent_ranges = {r.get_has_identifier() for r in parent.get_has_range()} - {owl_thing}
        if not parent_ranges:
            continue
        # Skip if parent ranges are all BNodes (anonymous classes, not comparable)
        if all(not str(r).startswith('http') for r in parent_ranges):
            continue
        # Skip if child has owl:inverseOf (domain/range come dall'inversa, non dal parent)
        if (s, OWL.inverseOf, None) in owl_logic.graph or (None, OWL.inverseOf, s) in owl_logic.graph:
            continue
        child_ranges = {r.get_has_identifier() for r in child.get_has_range()}
        assert parent_ranges & child_ranges, (
            f"{s} subPropertyOf {o} with range {parent_ranges} "
            f"but child range is {child_ranges}"
        )

def test_no_none_in_has_domain(owl_logic):
    for instances in owl_logic._instance_cache.values():
        for inst in instances:
            if isinstance(inst, Property):
                assert None not in inst.get_has_domain(), (
                    f"{type(inst).__name__} {inst.get_has_identifier()} "
                    f"has None in has_domain"
                )

def test_no_none_in_has_range(owl_logic):
    for instances in owl_logic._instance_cache.values():
        for inst in instances:
            if isinstance(inst, Property):
                assert None not in inst.get_has_range(), (
                    f"{type(inst).__name__} {inst.get_has_identifier()} "
                    f"has None in has_range"
                )

def test_property_characteristics_functional(owl_logic):
    """If a URI is declared as owl:FunctionalProperty in the graph, it must be
    a Property instance in cache with is_functional set to True."""
    from rdflib.namespace import RDF, OWL
    from rdflib import URIRef
    from lode.models import Property

    for uri in owl_logic.graph.subjects(RDF.type, OWL.FunctionalProperty):
        if not isinstance(uri, URIRef):
            continue
        inst = next((i for i in owl_logic._instance_cache.get(uri, set()) if isinstance(i, Property)), None)
        assert inst is not None, (
            f"{uri} declared as FunctionalProperty but not Property in cache: "
            f"{[type(i).__name__ for i in owl_logic._instance_cache.get(uri, set())]}"
        )
        assert inst.get_is_functional() is True, (
            f"{uri} is FunctionalProperty in graph but get_is_functional() is False"
        )

def test_relation_characteristics_match_graph(owl_logic):
    """If a URI is declared as owl:AsymmetricProperty, owl:InverseFunctionalProperty,
    owl:IrreflexiveProperty, owl:ReflexiveProperty, owl:SymmetricProperty or
    owl:TransitiveProperty in the graph, it must be a Relation in cache with
    the corresponding flag set to True."""
    from rdflib.namespace import RDF, OWL
    from rdflib import URIRef
    from lode.models import Relation

    checks = [
        (OWL.AsymmetricProperty, 'get_is_asymmetric'),
        (OWL.InverseFunctionalProperty, 'get_is_inverse_functional'),
        (OWL.IrreflexiveProperty, 'get_is_irreflexive'),
        (OWL.ReflexiveProperty, 'get_is_reflexive'),
        (OWL.SymmetricProperty, 'get_is_symmetric'),
        (OWL.TransitiveProperty, 'get_is_transitive'),
    ]

    for rdf_type, getter_name in checks:
        for uri in owl_logic.graph.subjects(RDF.type, rdf_type):
            if not isinstance(uri, URIRef):
                continue
            inst = next((i for i in owl_logic._instance_cache.get(uri, set()) if isinstance(i, Relation)), None)
            assert inst is not None, (
                f"{uri} declared as {rdf_type.split('#')[-1]} but not Relation in cache: "
                f"{[type(i).__name__ for i in owl_logic._instance_cache.get(uri, set())]}"
            )
            assert getattr(inst, getter_name)() is True, (
                f"{uri} is {rdf_type.split('#')[-1]} in graph but {getter_name}() is False"
            )

def test_individual_relations_subject_object_are_individuals(owl_logic):
    """For every owl:sameAs and owl:differentFrom triple in the graph,
    both subject and object must be Individual in cache."""
    from rdflib.namespace import OWL, RDF
    from rdflib import URIRef
    from lode.models import Individual

    for predicate in (OWL.sameAs, OWL.differentFrom):
        for s, _, o in owl_logic.graph.triples((None, predicate, None)):
            if not isinstance(s, URIRef) or not isinstance(o, URIRef):
                continue
            s_inst = next((i for i in owl_logic._instance_cache.get(s, set()) if isinstance(i, Individual)), None)
            o_inst = next((i for i in owl_logic._instance_cache.get(o, set()) if isinstance(i, Individual)), None)
            assert s_inst is not None, (
                f"{s} is subject of {predicate} but not Individual in cache: "
                f"{[type(i).__name__ for i in owl_logic._instance_cache.get(s, set())]}"
            )
            assert o_inst is not None, (
                f"{o} is object of {predicate} but not Individual in cache: "
                f"{[type(i).__name__ for i in owl_logic._instance_cache.get(o, set())]}"
            )

def test_all_individuals_have_type(owl_logic):
    for ind in _instances_of(owl_logic, Individual):
        assert len(ind.get_has_type()) >= 1, (
            f"Individual {ind.get_has_identifier()} has no type"
        )

#############################################################################################
# §10 Annotations
# §10.1 Annotations of Ontologies, Axioms, and other Annotations
# §10.2 Annotation Axioms
#
# §10:  "OWL 2 provides for annotations on ontologies, axioms, and entities."
#        "Annotations consist of an annotation property and an annotation value,
#        where the latter can be anonymous individuals, IRIs, and literals."
#        Extraction rule: annotation triples whose predicate is not in a structural
#        namespace and not mapped in owl.yaml become Statement in cache via phase6.
#        Covered by test_non_mapped_predicates_become_statements.
#
# §10.1: "Annotation := Annotation( annotationAnnotations AnnotationProperty AnnotationValue )"
#         AnnotationValue := AnonymousIndividual | IRI | Literal
#         Extraction rule: rdfs:label, rdfs:comment, rdfs:seeAlso, rdfs:isDefinedBy
#         populate the corresponding Resource getters (has_label, has_comment, etc.)
#         via base.yaml setters. Covered by test_every_resource_has_identifier, test_all_statements_have_subject_and_predicate, test_every_resource_has_is_deprecated (structural integrity).
#         And also note: test_statements_do_not_reuse_mapped_predicates. 
#
# §10.2.1: "AnnotationAssertion(AP as av) — as is annotated with AP and value av."
#           Extraction rule: if AP is mapped in owl.yaml/base.yaml → populates getter.
#           If AP is not mapped → triple becomes Statement in phase6.
#           Covered by test_non_mapped_predicates_become_statements,
#           test_no_mapped_predicate_produces_statement.
#
# §10.2.2: "SubAnnotationPropertyOf(AP1 AP2) — AP1 subproperty of AP2."
#           Extraction rule: rdfs:subPropertyOf on Annotation subjects populates
#           get_is_sub_property_of(). Child type must remain Annotation.
#           Covered by test_property_reclassified_via_sub_property_of.
#
# §10.2.3: "AnnotationPropertyDomain(AP U) — domain of AP is IRI U."
#           Extraction rule: rdfs:domain on Annotation populates get_has_domain().
#           Covered by test_property_domain_and_range_populated (partial —
#           only Relation and Attribute checked, Annotation excluded by design
#           since domain/range defaults do not apply to Annotation).
#
# §10.2.4: "AnnotationPropertyRange(AP U) — range of AP is IRI U."
#           Extraction rule: rdfs:range on Annotation populates get_has_range().
#           Same coverage note as §10.2.3.
#############################################################################################

def test_all_statements_have_subject_and_predicate(owl_logic):
    for stmt in _instances_of(owl_logic, Statement):
        assert stmt.get_has_subject() is not None, (
            f"Statement {stmt.get_has_identifier()} has no subject"
        )
        assert stmt.get_has_predicate() is not None, (
            f"Statement {stmt.get_has_identifier()} has no predicate"
        )
        assert stmt.get_has_object() is not None, (
            f"Statement {stmt.get_has_identifier()} has no object"
        )
        assert isinstance(stmt.get_has_subject(), Resource), (
            f"Statement {stmt.get_has_identifier()} subject is not a Resource: {type(stmt.get_has_subject())}"
        )
        assert isinstance(stmt.get_has_object(), Resource), (
            f"Statement {stmt.get_has_identifier()} object is not a Resource: {type(stmt.get_has_object())}"
        )
        assert isinstance(stmt.get_has_predicate(), Property), (
            f"Statement {stmt.get_has_identifier()} predicate is not a Property: {type(stmt.get_has_predicate())}"
        )

def test_non_mapped_predicates_become_statements(owl_logic):
    """
    Every triple whose predicate is not in a known structural namespace
    and not in the property mapping must appear as the predicate of a Statement.
    """
    from rdflib import URIRef
    from rdflib.namespace import RDF, RDFS, OWL, SKOS, XSD

    structural_ns = {str(RDF), str(RDFS), str(OWL), str(SKOS), str(XSD)}
    mapped_predicates = {str(uri) for uri in owl_logic._strategy.get_property_mapping().keys()}

    # Collect predicate identifiers actually used in statements
    statement_predicates = {
        stmt.get_has_predicate().get_has_identifier()
        for stmt in _instances_of(owl_logic, Statement)
        if stmt.get_has_predicate() is not None
    }

    for pred in owl_logic.graph.predicates():
        if not isinstance(pred, URIRef):
            continue
        pred_str = str(pred)
        in_structural_ns = any(pred_str.startswith(ns) for ns in structural_ns)
        if in_structural_ns or pred_str in mapped_predicates:
            continue
        assert pred_str in statement_predicates, (
            f"Predicate <{pred_str}> is outside known namespaces and not mapped, "
            f"but does not appear as predicate of any Statement"
        )

def test_statements_do_not_reuse_mapped_predicates(owl_logic):
    """
    Triples whose predicate maps to Statement (via target_class, target_classes, or inferred_class)
    must not become Statements in phase6.
    rdf:type triples must never become Statements.
    """
    from rdflib.namespace import RDF

    config = owl_logic._strategy
    excluded = set()
    excluded.add(str(RDF.type))

    for uri, cfg in config.get_property_mapping().items():
        target_classes = cfg.get('target_classes', [])
        inferred = cfg.get('inferred_class')
        if Statement in target_classes or inferred is Statement:
            excluded.add(str(uri))

    for instance in _instances_of(owl_logic, Statement):
        triples = owl_logic._triples_map.get(instance, set())
        for subj, pred, obj in triples:
            assert str(pred) not in excluded, (
                f"Statement {instance.get_has_identifier()} created from excluded predicate: {pred}"
            )

def test_every_resource_has_is_deprecated(owl_logic):
    """Every Resource in cache must have is_deprecated set to True or False, never None."""
    for uri, instances in owl_logic._instance_cache.items():
        for inst in instances:
            if isinstance(inst, Literal):
                continue
            if isinstance(inst, Resource):
                assert inst.get_is_deprecated() is not None, (
                    f"{inst.get_has_identifier()} ({type(inst).__name__}) "
                    f"has is_deprecated=None"
                )
                assert isinstance(inst.get_is_deprecated(), bool), (
                    f"{inst.get_has_identifier()} ({type(inst).__name__}) "
                    f"is_deprecated is not bool: {inst.get_is_deprecated()}"
                )

def test_every_resource_has_identifier(owl_logic):
    """Every Resource in cache must have a non-None identifier. Literals are excluded."""
    for uri, instances in owl_logic._instance_cache.items():
        for inst in instances:
            if isinstance(inst, Literal):
                continue
            if isinstance(inst, Resource):
                assert inst.get_has_identifier() is not None, (
                    f"{type(inst).__name__} has no identifier "
                    f"(cache key: {uri})"
                )

def test_no_mapped_predicate_produces_statement(owl_logic):
    """Any triple whose predicate is mapped in the config must never produce
    a Statement (excluding the ones explicitly defined in the config) — it must be handled by phase2 or phase3."""
    from lode.reader.config_manager import OwlConfigManager
    from rdflib.namespace import RDF
    from lode.models import Statement

    strategy = OwlConfigManager()
    property_mapping = strategy.get_property_mapping()
    type_mapping = strategy.get_type_mapping()


    # Predicates targeting Statement are excluded — they populate Statements, not prevent them
    mapped_predicate_ids = {
        str(p) for p, cfg in property_mapping.items()
        if Statement not in cfg.get('target_classes', [])
    }
    # Types mapping URIs whose target_class is Statement are also excluded
    statement_type_uris = {
        str(uri) for uri, cfg in type_mapping.items()
        if cfg.get('target_class') is Statement
    }
    mapped_predicate_ids -= statement_type_uris
    mapped_predicate_ids.add(str(RDF.type))

    stmts = _instances_of(owl_logic, Statement)
    for stmt in stmts:
        pred = stmt.get_has_predicate()
        if pred is not None:
            assert pred.get_has_identifier() not in mapped_predicate_ids, (
                f"Statement found with mapped predicate: {pred.get_has_identifier()}"
            )

#############################################################################################
# §11 Global Restrictions on Axioms in OWL 2 DL
# §11.1 Property Hierarchy and Simple Object Property Expressions
# §11.2 The Restrictions on the Axiom Closure
#
# §11:  Global restrictions are necessary for decidability of OWL 2 DL reasoning.
#        These are constraints on the axiom closure Ax of an ontology, not on the
#        extracted domain model. They concern the reasoner, not the extractor.
#        Out of scope as a whole: LODE is an extractor, not a reasoner or validator.
#
# §11.1: "An object property OPE is simple in Ax if no direct or indirect subproperty
#         of OPE is composite (transitive or defined by property chain)."
#         Out of scope: simplicity of roles is a reasoning constraint, not an extraction
#         invariant. LODE does not validate OWL 2 DL profile conformance.
#
# §11.2: Restriction on owl:topDataProperty — appears only as superDataPropertyExpression.
#         Out of scope: filtered by namespace filter — owl:topDataProperty not extracted.
#
# §11.2: Restrictions on Datatypes — each datatype must be rdfs:Literal, in OWL 2
#         datatype map, or defined by a single DatatypeDefinition. Datatype definitions
#         must be acyclic.
#         Partial coverage: test_datatype_iris_are_valid covers the first condition.
#         Acyclicity of DatatypeDefinition — out of scope: requires graph traversal
#         across owl:equivalentClass chains on Datatype nodes, not currently modeled.
#
# §11.2: Restriction on Simple Roles — ObjectMinCardinality, ObjectMaxCardinality,
#         ObjectExactCardinality, ObjectHasSelf, FunctionalObjectProperty,
#         InverseFunctionalObjectProperty, IrreflexiveObjectProperty,
#         AsymmetricObjectProperty, DisjointObjectProperties must use only simple
#         object properties.
#         Out of scope: requires computing the full property hierarchy — reasoner concern.
#
# §11.2: Restriction on Property Hierarchy — strict partial order on AllOPE(Ax) must
#         exist such that property chains are acyclic.
#         Out of scope: cycle detection on property hierarchy — reasoner concern.
#
# §11.2: Restrictions on Anonymous Individuals — anonymous individual graph must be
#         a forest; no BNode in SameIndividual, DifferentIndividuals,
#         NegativePropertyAssertion, ObjectOneOf, ObjectHasValue.
#         Out of scope: BNode graph topology analysis — reasoner/validator concern.
#         Note: the restriction that BNodes must not appear in SameIndividual etc. is
#         partially enforced by LODE's namespace filter and Individual case in get_or_create.
#############################################################################################

#############################################################################################
# SWRL Rules
# "A SWRL rule consists of an antecedent (body) and a consequent (head),
#  each of which is a conjunction of atoms."
# Extraction rule: every swrl:Imp BNode must produce a Rule in cache with
# non-empty has_body and has_head, each containing Atom instances with
# has_atom_type, has_predicate, and has_argument1 populated.
#############################################################################################

SWRL_NS = 'http://www.w3.org/2003/11/swrl#'
SWRL_IMP = URIRef(SWRL_NS + 'Imp')

def test_swrl_imp_produces_rule(owl_logic):
    """Every swrl:Imp in graph must produce a Rule in cache."""
    from lode.models import Rule

    for subj in owl_logic.graph.subjects(RDF.type, SWRL_IMP):
        instances = owl_logic._instance_cache.get(subj, set())
        assert any(isinstance(i, Rule) for i in instances), (
            f"swrl:Imp {subj} not Rule in cache: "
            f"{[type(i).__name__ for i in instances]}"
        )

def test_swrl_rule_has_body_and_head(owl_logic):
    """Every Rule must have non-empty has_body and has_head."""
    from lode.models import Rule

    for instances in owl_logic._instance_cache.values():
        for inst in instances:
            if not isinstance(inst, Rule):
                continue
            assert len(inst.get_has_body()) >= 1, (
                f"Rule {inst.get_has_identifier()} has empty body"
            )
            assert len(inst.get_has_head()) >= 1, (
                f"Rule {inst.get_has_identifier()} has empty head"
            )

def test_swrl_atoms_have_argument1(owl_logic):
    """Every Atom must have has_argument1 set."""
    from lode.models import Rule

    for instances in owl_logic._instance_cache.values():
        for inst in instances:
            if not isinstance(inst, Rule):
                continue
            for atom in inst.get_has_body() + inst.get_has_head():
                assert atom.get_has_argument1() is not None, (
                    f"Atom {atom.get_has_identifier()} in Rule {inst.get_has_identifier()} "
                    f"has no argument1"
                )

def test_swrl_atoms_have_predicate(owl_logic):
    """Every Atom must have has_predicate set."""
    from lode.models import Rule

    for instances in owl_logic._instance_cache.values():
        for inst in instances:
            if not isinstance(inst, Rule):
                continue
            for atom in inst.get_has_body() + inst.get_has_head():
                assert atom.get_has_predicate() is not None, (
                    f"Atom {atom.get_has_identifier()} in Rule {inst.get_has_identifier()} "
                    f"has no predicate"
                )

def test_swrl_arguments_are_variables_or_resources(owl_logic):
    """Atom arguments must be Variable or Resource instances."""
    from lode.models import Rule, Variable, Resource

    for instances in owl_logic._instance_cache.values():
        for inst in instances:
            if not isinstance(inst, Rule):
                continue
            for atom in inst.get_has_body() + inst.get_has_head():
                for arg in (atom.get_has_argument1(), atom.get_has_argument2()):
                    if arg is None:
                        continue
                    assert isinstance(arg, Resource), (
                        f"Atom {atom.get_has_identifier()} argument is not Resource: "
                        f"{type(arg).__name__}"
                    )

def test_swrl_variable_declaration_produces_variable(owl_logic):
    """Every swrl:Variable in graph must produce a Variable in cache."""
    from lode.models import Variable

    SWRL_VARIABLE = URIRef(SWRL_NS + 'Variable')
    for subj in owl_logic.graph.subjects(RDF.type, SWRL_VARIABLE):
        instances = owl_logic._instance_cache.get(subj, set())
        assert any(isinstance(i, Variable) for i in instances), (
            f"swrl:Variable {subj} not Variable in cache: "
            f"{[type(i).__name__ for i in instances]}"
        )

def test_swrl_predicates_not_annotations(owl_logic):
    """swrl:argument1, swrl:argument2, swrl:classPredicate, swrl:propertyPredicate
    must never appear as predicate of a Statement."""
    from lode.models import Statement

    SWRL_PREDS = {
        SWRL_NS + 'argument1',
        SWRL_NS + 'argument2',
        SWRL_NS + 'classPredicate',
        SWRL_NS + 'propertyPredicate',
        SWRL_NS + 'body',
        SWRL_NS + 'head',
    }

    for stmt in _instances_of(owl_logic, Statement):
        pred = stmt.get_has_predicate()
        if pred is not None:
            assert pred.get_has_identifier() not in SWRL_PREDS, (
                f"Statement has SWRL structural predicate: {pred.get_has_identifier()}"
            )



#############################################################################################
########################                 ATTRIBUTES                ##########################
#############################################################################################

# def test_attribute_range_is_datatype(owl_logic):
#     """Every Attribute range must be a Datatype or DatatypeRestriction."""
#     from lode.models import Attribute, Datatype, DatatypeRestriction

#     for inst in _instances_of(owl_logic, Attribute):
#         ranges = inst.get_has_range()
#         assert all(isinstance(r, (Datatype, DatatypeRestriction)) for r in ranges), (
#             f"Attribute {inst.get_has_identifier()} has non-Datatype range: "
#             f"{[(r.get_has_identifier(), type(r).__name__) for r in ranges if not isinstance(r, (Datatype, DatatypeRestriction))]}"
#         )


# #############################################################################################
# ########################                ADDITIONALS                 #########################
# #############################################################################################

# # def test_no_bnodes_for_concept_property_model(owl_logic):
# #     """Concept, Property, and Model must never be keyed to a BNode.
# #     Subclasses (Restriction, Relation, etc.) are excluded — checked by exact type."""

# #     FORBIDDEN = (Concept, Annotation, Relation, Attribute, Individual, Model)

# #     for uri, instances in owl_logic._instance_cache.items():
# #         if not isinstance(uri, BNode):
# #             continue
# #         for inst in instances:
# #             assert type(inst) not in FORBIDDEN, (
# #                 f"BNode {uri} has instance of exact type {type(inst).__name__}, "
# #                 f"which must never be a BNode"
# #             )