import pytest
from pathlib import Path
from lode.logic.reader import Reader


class TestReaderInitialization:
    def test_reader_creates_instance(self, reader):
        assert reader is not None
        assert hasattr(reader, '_instance_cache')
        assert hasattr(reader, '_graph')


class TestReaderBeforeLoading:
    def test_cache_empty_before_load(self, reader):
        assert len(reader._instance_cache) == 0
    
    def test_get_viewer_raises_before_load(self, reader):
        with pytest.raises(ValueError):
            reader.get_viewer()


class TestReaderWithLoadedOntology:
    @pytest.fixture
    def loaded_reader(self, tmp_path):
        """Reader with a simple OWL ontology loaded"""
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
        
        reader = Reader()
        reader.load_instances(str(owl_file), read_as='OWL')
        return reader
    
    def test_load_instances_populates_cache(self, loaded_reader):
        assert len(loaded_reader._instance_cache) > 0
    
    def test_get_viewer_returns_viewer(self, loaded_reader):
        viewer = loaded_reader.get_viewer()
        assert viewer is not None
        assert hasattr(viewer, 'get_all_instances')


class TestReaderClearCache:
    def test_clear_cache_empties_instances(self, reader):
        reader._instance_cache['test'] = 'value'
        assert len(reader._instance_cache) > 0
        
        reader.clear_cache()
        assert len(reader._instance_cache) == 0


class TestReaderTriplesMap:
    @pytest.fixture
    def reader_with_triples(self, tmp_path):
        """Reader con ontologia per testare il mapping delle triple"""
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
        
        reader = Reader()
        reader.load_instances(str(owl_file), read_as='OWL')
        return reader
    
    def test_triples_map_exists(self, reader_with_triples):
        """Verifica che triples_map sia stata creata"""
        assert hasattr(reader_with_triples._logic, '_triples_map')
        triples_map = reader_with_triples._logic._triples_map
        assert isinstance(triples_map, dict)
    
    def test_triples_map_has_entries(self, reader_with_triples):
        """Verifica che ci siano entry nella triples_map"""
        triples_map = reader_with_triples._logic._triples_map
        assert len(triples_map) > 0
    
    def test_get_triples_for_instance(self, reader_with_triples):
        """Verifica che possiamo ottenere triple per una specifica istanza"""
        viewer = reader_with_triples.get_viewer()
        
        # Usa il viewer per ottenere l'istanza
        instance_set = viewer.get_instances_from_single_resource("http://example.org/test#Person")
        assert instance_set is not None
        
        # Prendi la prima istanza dal set
        person = next(iter(instance_set))
        
        # Ottieni le sue triple tramite _logic (non tramite Reader)
        triples_map = reader_with_triples._logic._triples_map
        triples = triples_map.get(person, set())
        
        assert isinstance(triples, set)
        print(f"\n=== TRIPLES PER {person} ===")
        for s, p, o in triples:
            print(f"  {s} -> {p} -> {o}")
        
        assert len(triples) > 0, "L'istanza dovrebbe avere almeno una tripla"
    
    def test_triples_contain_expected_predicates(self, reader_with_triples):
        """Verifica che le triple contengano i predicati attesi"""
        viewer = reader_with_triples.get_viewer()
        instance_set = viewer.get_instances_from_single_resource("http://example.org/test#Person")
        person = next(iter(instance_set))
        
        triples_map = reader_with_triples._logic._triples_map
        triples = triples_map.get(person, set())
        
        predicates = {str(p) for s, p, o in triples}
        print(f"\n=== PREDICATI TROVATI ===")
        for pred in predicates:
            print(f"  - {pred}")
        
        assert any('type' in pred for pred in predicates), "Manca rdf:type"
        assert any('label' in pred for pred in predicates), "Manca rdfs:label"
    
    def test_triples_contain_expected_objects(self, reader_with_triples):
        """Verifica che le triple contengano gli oggetti attesi"""
        viewer = reader_with_triples.get_viewer()
        instance_set = viewer.get_instances_from_single_resource("http://example.org/test#Person")
        person = next(iter(instance_set))
        
        triples_map = reader_with_triples._logic._triples_map
        triples = triples_map.get(person, set())
        
        objects = {str(o) for s, p, o in triples}
        print(f"\n=== OGGETTI TROVATI ===")
        for obj in objects:
            print(f"  - {obj}")
        
        assert any('Person' in obj for obj in objects), "Manca il literal 'Person'"
    
    def test_subclass_has_subClassOf_triple(self, reader_with_triples):
        """Verifica che Student abbia la tripla rdfs:subClassOf"""
        viewer = reader_with_triples.get_viewer()
        instance_set = viewer.get_instances_from_single_resource("http://example.org/test#Student")
        assert instance_set is not None
        
        student = next(iter(instance_set))
        
        triples_map = reader_with_triples._logic._triples_map
        triples = triples_map.get(student, set())
        
        print(f"\n=== TRIPLES PER STUDENT ===")
        for s, p, o in triples:
            print(f"  {s} -> {p} -> {o}")
        
        has_subclass = any('subClassOf' in str(p) for s, p, o in triples)
        assert has_subclass, "Student dovrebbe avere rdfs:subClassOf"
        
        subclass_objects = {str(o) for s, p, o in triples if 'subClassOf' in str(p)}
        assert any('Person' in obj for obj in subclass_objects), "subClassOf dovrebbe puntare a Person"
    
    def test_property_has_domain_range_triples(self, reader_with_triples):
        """Verifica che la property 'knows' abbia domain e range"""
        viewer = reader_with_triples.get_viewer()
        instance_set = viewer.get_instances_from_single_resource("http://example.org/test#knows")
        assert instance_set is not None
        
        knows = next(iter(instance_set))
        
        triples_map = reader_with_triples._logic._triples_map
        triples = triples_map.get(knows, set())
        
        print(f"\n=== TRIPLES PER KNOWS PROPERTY ===")
        for s, p, o in triples:
            print(f"  {s} -> {p} -> {o}")
        
        predicates = {str(p) for s, p, o in triples}
        
        assert any('domain' in pred for pred in predicates), "Manca rdfs:domain"
        assert any('range' in pred for pred in predicates), "Manca rdfs:range"
    
    def test_all_instances_have_triples(self, reader_with_triples):
        """Verifica che ogni istanza abbia almeno una tripla"""
        viewer = reader_with_triples.get_viewer()
        all_instances = viewer.get_all_instances()
        
        triples_map = reader_with_triples._logic._triples_map
        instances_without_triples = []
        
        for instance in all_instances:
            triples = triples_map.get(instance, set())
            if len(triples) == 0:
                instances_without_triples.append(instance)
        
        if instances_without_triples:
            print(f"\n=== INSTANCES SENZA TRIPLE ===")
            for instance in instances_without_triples:
                print(f"  {type(instance).__name__}: {instance}")
        
        assert len(instances_without_triples) == 0, \
            f"Trovate {len(instances_without_triples)} istanze senza triple"
    
    def test_triples_map_keys_are_instances(self, reader_with_triples):
        """Verifica che le chiavi della triples_map siano istanze Python"""
        triples_map = reader_with_triples._logic._triples_map
        
        print(f"\n=== CHIAVI DELLA TRIPLES_MAP ===")
        for key in list(triples_map.keys())[:5]:  # Mostra solo le prime 5
            print(f"  {type(key).__name__}: {key}")
        
        from lode.models import Resource
        for key in triples_map.keys():
            assert isinstance(key, Resource), \
                f"Chiave {key} non è un'istanza di Resource ma {type(key)}"