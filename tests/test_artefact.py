"""Artefact accessors: entities are listed without literals, by exact class name."""
from rdflib import Graph, URIRef
import pytest

from lode.artefact import Artefact
from lode.models import Collection, Concept, Literal, Resource


def _artefact():
    """Build an Artefact with a concept, a collection, a punned IRI and one literal."""
    concept, collection, punned = Concept(), Collection(), Collection()
    concept.set_has_identifier("http://ex.org/a")
    collection.set_has_identifier("http://ex.org/b")
    literal = Literal()
    literal.set_has_value("x")
    entities = {
        URIRef("http://ex.org/a"): {concept, punned},
        URIRef("http://ex.org/b"): {collection},
        "LITERAL::x@^^": {literal},
    }
    return Artefact.from_parts(entities=entities, graph=Graph()), concept, collection, punned

def test_instances_lists_entities_and_skips_literals():
    artefact, *_ = _artefact()
    assert len(artefact.instances()) == 3
    assert all(not isinstance(i, Literal) for i in artefact.instances())

def test_instances_by_exact_class_name():
    artefact, concept, collection, punned = _artefact()
    assert artefact.instances(Concept) == [concept]
    assert set(artefact.instances(Collection)) == {collection, punned}

def test_instances_include_subclasses():
    artefact, *_ = _artefact()
    assert artefact.instances(Resource) == artefact.instances()

def test_class_name_instead_of_class_raises():
    artefact, *_ = _artefact()
    with pytest.raises(TypeError):
        artefact.instances("Concept")

def test_get_instance_returns_the_punned_set():
    artefact, concept, _, punned = _artefact()
    assert artefact.get_instance("http://ex.org/a") == {concept, punned}

def test_get_instance_unknown_iri_is_none():
    artefact, *_ = _artefact()
    assert artefact.get_instance("http://ex.org/missing") is None

def test_from_parts_leaves_the_rest_empty():
    artefact = Artefact.from_parts(entities={}, graph=Graph())
    assert artefact.profile is None and artefact.read_as is None
    assert artefact.warnings == [] and artefact.imported_uris == set()
    assert artefact.artefact_base_iri is None
    assert len(artefact.provenance(object())) == 0
