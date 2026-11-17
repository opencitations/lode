import pytest
from pathlib import Path
from lode.artefact import Artefact
from lode.profiles.owl.viewer import OwlViewer
from lode.viewer import get_viewer


class TestArtefactWithLoadedOntology:
    @pytest.fixture
    def artefact(self, tmp_path):
        """Artefact read from a simple OWL ontology"""
        owl_content = """<?xml version="1.0"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
         xmlns:owl="http://www.w3.org/2002/07/owl#"
         xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#">
    <owl:Ontology rdf:about="http://example.org/test"/>
    <owl:Class rdf:about="http://example.org/test#Person">
        <rdfs:label>Person</rdfs:label>
    </owl:Class>
    <owl:ObjectProperty rdf:about="http://example.org/test#knows">
        <rdfs:label>knows</rdfs:label>
    </owl:ObjectProperty>
</rdf:RDF>"""

        owl_file = tmp_path / "test.owl"
        owl_file.write_text(owl_content)

        return Artefact(str(owl_file), read_as='OWL')

    def test_reading_populates_entities(self, artefact):
        assert len(artefact.entities) > 0

    def test_get_viewer_picks_the_viewer_of_the_format(self, artefact):
        viewer = get_viewer(artefact)
        assert isinstance(viewer, OwlViewer)
        assert hasattr(viewer.artefact, 'instances')

    def test_reading_fills_every_field_of_the_artefact(self, artefact):
        assert artefact.profile.name == "owl" and artefact.read_as == "owl"
        assert len(artefact.graph) > 0 and artefact.artefact_iri is not None
        assert artefact.logic is not None and artefact.warnings == []
        assert str(artefact.artefact_base_iri).startswith("http://example.org/")
        assert callable(artefact.provenance)


class TestReaderTriplesMap:
    @pytest.fixture
    def artefact(self, tmp_path):
        """Artefact con ontologia per testare il mapping delle triple"""
        owl_content = """<?xml version="1.0"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
         xmlns:owl="http://www.w3.org/2002/07/owl#"
         xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#">

    <owl:Ontology rdf:about="http://example.org/test"/>

    <owl:Class rdf:about="http://example.org/test#Person">
        <rdfs:label>Person</rdfs:label>
        <rdfs:comment>A human being</rdfs:comment>
    </owl:Class>

    <owl:Class rdf:about="http://example.org/test#Student">
        <rdfs:subClassOf rdf:resource="http://example.org/test#Person"/>
        <rdfs:label>Student</rdfs:label>
    </owl:Class>

    <owl:ObjectProperty rdf:about="http://example.org/test#knows">
        <rdfs:label>knows</rdfs:label>
        <rdfs:domain rdf:resource="http://example.org/test#Person"/>
        <rdfs:range rdf:resource="http://example.org/test#Person"/>
    </owl:ObjectProperty>

</rdf:RDF>"""

        owl_file = tmp_path / "test_triples.owl"
        owl_file.write_text(owl_content)

        return Artefact(str(owl_file), read_as='OWL')

    def test_triples_map_exists(self, artefact):
        """Verifica che triples_map sia stata creata"""
        assert hasattr(artefact.logic, '_triples_map')
        triples_map = artefact.logic._triples_map
        assert isinstance(triples_map, dict)

    def test_triples_map_has_entries(self, artefact):
        """Verifica che ci siano entry nella triples_map"""
        triples_map = artefact.logic._triples_map
        assert len(triples_map) > 0

    def test_get_triples_for_instance(self, artefact):
        """Verifica che possiamo ottenere triple per una specifica istanza"""
        viewer = get_viewer(artefact)

        # Usa il viewer per ottenere l'istanza
        instance_set = viewer.artefact.get_instance("http://example.org/test#Person")
        assert instance_set is not None

        # Prendi la prima istanza dal set
        person = next(iter(instance_set))

        # Ottieni le sue triple tramite la logic dell'artefact
        triples_map = artefact.logic._triples_map
        triples = triples_map.get(person, set())

        assert isinstance(triples, set)
        print(f"\n=== TRIPLES PER {person} ===")
        for s, p, o in triples:
            print(f"  {s} -> {p} -> {o}")

        assert len(triples) > 0, "L'istanza dovrebbe avere almeno una tripla"

    def test_triples_contain_expected_predicates(self, artefact):
        """Verifica che le triple contengano i predicati attesi"""
        viewer = get_viewer(artefact)
        instance_set = viewer.artefact.get_instance("http://example.org/test#Person")
        person = next(iter(instance_set))

        triples_map = artefact.logic._triples_map
        triples = triples_map.get(person, set())

        predicates = {str(p) for s, p, o in triples}
        print(f"\n=== PREDICATI TROVATI ===")
        for pred in predicates:
            print(f"  - {pred}")

        assert any('type' in pred for pred in predicates), "Manca rdf:type"
        assert any('label' in pred for pred in predicates), "Manca rdfs:label"

    def test_triples_contain_expected_objects(self, artefact):
        """Verifica che le triple contengano gli oggetti attesi"""
        viewer = get_viewer(artefact)
        instance_set = viewer.artefact.get_instance("http://example.org/test#Person")
        person = next(iter(instance_set))

        triples_map = artefact.logic._triples_map
        triples = triples_map.get(person, set())

        objects = {str(o) for s, p, o in triples}
        print(f"\n=== OGGETTI TROVATI ===")
        for obj in objects:
            print(f"  - {obj}")

        assert any('Person' in obj for obj in objects), "Manca il literal 'Person'"

    def test_subclass_has_subClassOf_triple(self, artefact):
        """Verifica che Student abbia la tripla rdfs:subClassOf"""
        viewer = get_viewer(artefact)
        instance_set = viewer.artefact.get_instance("http://example.org/test#Student")
        assert instance_set is not None

        student = next(iter(instance_set))

        triples_map = artefact.logic._triples_map
        triples = triples_map.get(student, set())

        print(f"\n=== TRIPLES PER STUDENT ===")
        for s, p, o in triples:
            print(f"  {s} -> {p} -> {o}")

        has_subclass = any('subClassOf' in str(p) for s, p, o in triples)
        assert has_subclass, "Student dovrebbe avere rdfs:subClassOf"

        subclass_objects = {str(o) for s, p, o in triples if 'subClassOf' in str(p)}
        assert any('Person' in obj for obj in subclass_objects), "subClassOf dovrebbe puntare a Person"

    def test_property_has_domain_range_triples(self, artefact):
        """Verifica che la property 'knows' abbia domain e range"""
        viewer = get_viewer(artefact)
        instance_set = viewer.artefact.get_instance("http://example.org/test#knows")
        assert instance_set is not None

        knows = next(iter(instance_set))

        triples_map = artefact.logic._triples_map
        triples = triples_map.get(knows, set())

        print(f"\n=== TRIPLES PER KNOWS PROPERTY ===")
        for s, p, o in triples:
            print(f"  {s} -> {p} -> {o}")

        predicates = {str(p) for s, p, o in triples}

        assert any('domain' in pred for pred in predicates), "Manca rdfs:domain"
        assert any('range' in pred for pred in predicates), "Manca rdfs:range"

    def test_all_instances_have_triples(self, artefact):

        # top sintetici creati da LODE come radici implicite: niente triple di backing
        SYNTHETIC_TOP = {
            "http://www.w3.org/2002/07/owl#Thing",
            "http://www.w3.org/2000/01/rdf-schema#Literal",
        }

        viewer = get_viewer(artefact)
        triples_map = artefact.logic._triples_map
        graph = artefact.logic.graph

        orphans = []
        for inst in viewer.artefact.instances():
            if triples_map.get(inst):
                continue
            ident = inst.get_has_identifier()
            if ident in SYNTHETIC_TOP:          # <-- aggiungi questo
                continue
            # referenced-only (datatype XSD / classe esterna): lecito se appare come oggetto
            from rdflib import URIRef
            if ident and (None, None, URIRef(ident)) in graph:
                continue
            orphans.append(inst)

        assert not orphans, f"Istanze orfane reali: {[(type(i).__name__, i.get_has_identifier()) for i in orphans]}"

    def test_triples_map_keys_are_instances(self, artefact):
        """Verifica che le chiavi della triples_map siano istanze Python"""
        triples_map = artefact.logic._triples_map

        print(f"\n=== CHIAVI DELLA TRIPLES_MAP ===")
        for key in list(triples_map.keys())[:5]:  # Mostra solo le prime 5
            print(f"  {type(key).__name__}: {key}")

        from lode.models import Resource
        for key in triples_map.keys():
            assert isinstance(key, Resource), \
                f"Chiave {key} non è un'istanza di Resource ma {type(key)}"
