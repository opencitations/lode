import pytest
from pathlib import Path
from lode.reader import Reader

# ============================================
# CONFIGURAZIONE ONTOLOGIE
# ============================================
ONTOLOGIES = [
    {
        "name": "pizza",
        "url": "https://protege.stanford.edu/ontologies/pizza/pizza.owl",
        "read_as": "OWL",
        "expects_punning": False,
        "expects_axioms": True
    },
    {
        "name": "icon",
        "url": "https://w3id.org/icon/ontology/",
        "read_as": "OWL",
        "expects_punning": True,
        "expects_axioms": True
    },
    {
        "name": "write",
        "url": "https://raw.githubusercontent.com/WenDAng-project/thesaurus/refs/heads/main/writeThesaurus_v.1.0.ttl",
        "read_as": "SKOS",
        "expects_punning": False,
        "expects_axioms": False
    },


]

# ============================================
# FIXTURE PARAMETRIZZATA
# ============================================
@pytest.fixture(params=ONTOLOGIES, ids=lambda x: x["name"])
def ontology_reader(request):
    """Carica un'ontologia dai parametri"""
    config = request.param
    reader = Reader()
    reader.load_instances(config["url"], read_as=config["read_as"])
    reader.config = config
    return reader


# ============================================
# TEST PARAMETRIZZATI
# ============================================
class TestOntologyLoading:
    """Test base - tutti i formati"""
    
    def test_ontology_loads(self, ontology_reader):
        """Verifica caricamento"""
        name = ontology_reader.config['name']
        cache_size = len(ontology_reader._instance_cache)
        
        assert ontology_reader is not None
        assert cache_size > 0
        
        print(f"\n{'='*70}")
        print(f"SEMANTIC ARTEFACT: {name.upper()}")
        print(f"{'='*70}")
        print(f"Status: ✓ Reader initialized")
        print(f"Cache populated. Cache size: {cache_size} entries")
    
    def test_viewer_works(self, ontology_reader):
        """Verifica viewer"""
        name = ontology_reader.config['name']
        viewer = ontology_reader.get_viewer()
        instances = viewer.get_all_instances()
        
        assert len(instances) > 0
        
        print(f"\n{'='*70}")
        print(f"VIEWER: {name.upper()}")
        print(f"{'='*70}")
        print(f"Total instances (excluded Literals): {len(instances)}")
        print(f"Status: ✓ Viewer working correctly")


class TestPunning:
    """Test punning - solo ontologie che lo supportano"""
    
    def test_detect_punning_cases(self, ontology_reader):
        """Rileva punning"""
        name = ontology_reader.config['name']
        
        if not ontology_reader.config.get("expects_punning"):
            pytest.skip(f"Punning not expected in {name}")
        
        punning_cases = []
        for uri, inst_set in ontology_reader._instance_cache.items():
            if isinstance(inst_set, set) and len(inst_set) > 1:
                instance_types = [type(inst).__name__ for inst in inst_set]
                punning_cases.append({
                    'uri': str(uri),
                    'types': instance_types,
                    'count': len(inst_set)
                })
        
        print(f"\n{'='*70}")
        print(f"PUNNING DETECTION: {name.upper()}")
        print(f"{'='*70}")
        print(f"Total punning cases found: {len(punning_cases)}")
        
        if punning_cases:
            print(f"\nFirst 5 examples:")
            for i, case in enumerate(punning_cases[:5], 1):
                print(f"\n  {i}. URI: {case['uri']}")
                print(f"     Types: {', '.join(case['types'])}")
                print(f"     Count: {case['count']}")
        
        print(f"\nStatus: ✓ Punning cases detected")
        assert len(punning_cases) > 0
    
    def test_punning_triples_are_separated(self, ontology_reader):
        """Verifica separazione triple in punning"""
        name = ontology_reader.config['name']
        
        if not ontology_reader.config.get("expects_punning"):
            pytest.skip(f"Punning not expected in {name}")
        
        triples_map = ontology_reader._logic._triples_map
        
        # Trova primo caso di punning
        punning_uri, instance_set = next(
            ((uri, inst_set) for uri, inst_set in ontology_reader._instance_cache.items()
             if isinstance(inst_set, set) and len(inst_set) > 1),
            (None, None)
        )
        
        if not instance_set:
            pytest.skip("No punning found")
        
        instances = list(instance_set)
        triple_sets = [triples_map.get(inst, set()) for inst in instances]
        
        print(f"\n{'='*70}")
        print(f"PUNNING TRIPLES SEPARATION: {name.upper()}")
        print(f"{'='*70}")
        print(f"Testing URI: {punning_uri}")
        print(f"Instances involved: {len(instances)}")
        
        # Verifica che ogni istanza abbia triple
        all_have_triples = True
        for i, (inst, triples) in enumerate(zip(instances, triple_sets), 1):
            has_triples = len(triples) > 0
            all_have_triples = all_have_triples and has_triples
            
            print(f"\n  Instance {i}: {type(inst).__name__}")
            print(f"    Triples count: {len(triples)}")
            print(f"    Status: {'✓' if has_triples else '✗'}")
            
            assert has_triples, f"{type(inst).__name__} has no triples"
        
        # Verifica che siano diverse
        if len(triple_sets) >= 2:
            set1, set2 = triple_sets[0], triple_sets[1]
            shared = set1 & set2
            unique_1 = set1 - set2
            unique_2 = set2 - set1
            
            print(f"\n  Triple comparison:")
            print(f"    Shared triples: {len(shared)}")
            print(f"    Unique to instance 1: {len(unique_1)}")
            print(f"    Unique to instance 2: {len(unique_2)}")
            
            triples_differ = len(unique_1) > 0 or len(unique_2) > 0
            print(f"    Triples are different: {'✓' if triples_differ else '✗'}")
            
            assert triples_differ, "Triples must differ"
        
        print(f"\nStatus: ✓ Punning triples correctly separated")


class TestGeneralAxioms:
    """Test GCA - solo ontologie che li contengono"""
    
    def test_detect_general_axioms(self, ontology_reader):
        """Rileva general axioms"""
        name = ontology_reader.config['name']
        
        if not ontology_reader.config.get("expects_axioms"):
            pytest.skip(f"Axioms not expected in {name}")
        
        viewer = ontology_reader.get_viewer()
        all_instances = viewer.get_all_instances()
        
        axiom_types = {}
        for instance in all_instances:
            type_name = type(instance).__name__
            if type_name in ['Restriction', 'TruthFunction', 'Quantifier', 'Cardinality', 'OneOf']:
                axiom_types.setdefault(type_name, []).append(instance)
        
        print(f"\n{'='*70}")
        print(f"GENERAL CLASS AXIOMS: {name.upper()}")
        print(f"{'='*70}")
        print(f"Total axiom types found: {len(axiom_types)}")
        
        if axiom_types:
            print(f"\nBreakdown by type:")
            for axiom_type, instances in sorted(axiom_types.items(), key=lambda x: len(x[1]), reverse=True):
                print(f"  {axiom_type:20} {len(instances):>5} instances")
        
        print(f"\nStatus: ✓ General axioms detected")
        assert len(axiom_types) > 0


class TestTriplesMapIntegrity:
    """Test integrità - tutti i formati"""
    
    def test_triples_map_keys_are_hashable(self, ontology_reader):
        """CRITICO: verifica hashability delle chiavi"""
        name = ontology_reader.config['name']
        triples_map = ontology_reader._logic._triples_map
        
        unhashable = []
        for k in triples_map.keys():
            try:
                hash(k)
            except TypeError:
                unhashable.append(k)
        
        print(f"\n{'='*70}")
        print(f"TRIPLES MAP HASHABILITY: {name.upper()}")
        print(f"{'='*70}")
        print(f"Total keys: {len(triples_map)}")
        print(f"Unhashable keys: {len(unhashable)}")
        
        if unhashable:
            print(f"\n⚠ WARNING: Found unhashable keys!")
            for i, k in enumerate(unhashable[:5], 1):
                print(f"  {i}. Type: {type(k).__name__}")
                print(f"     Value: {k}")
        else:
            print(f"\nStatus: ✓ All keys are hashable")
        
        assert len(unhashable) == 0, f"Found {len(unhashable)} unhashable keys!"
    
    def test_instances_triples_statistics(self, ontology_reader):
        """Statistiche triple"""
        name = ontology_reader.config['name']
        viewer = ontology_reader.get_viewer()
        all_instances = viewer.get_all_instances()
        triples_map = ontology_reader._logic._triples_map
        
        with_triples = 0
        without_triples = 0
        external_refs = []
        
        for inst in all_instances:
            triples = triples_map.get(inst, set())
            if len(triples) > 0:
                with_triples += 1
            else:
                without_triples += 1
                external_refs.append(inst)
        
        print(f"\n{'='*70}")
        print(f"TRIPLES STATISTICS: {name.upper()}")
        print(f"{'='*70}")
        print(f"Total instances: {len(all_instances)}")
        print(f"  With triples: {with_triples} ({with_triples/len(all_instances)*100:.1f}%)")
        print(f"  External refs: {without_triples} ({without_triples/len(all_instances)*100:.1f}%)")
        
        if external_refs:
            type_breakdown = {}
            for inst in external_refs:
                type_name = type(inst).__name__
                type_breakdown[type_name] = type_breakdown.get(type_name, 0) + 1
            
            print(f"\n  External references breakdown:")
            for type_name, count in sorted(type_breakdown.items(), key=lambda x: x[1], reverse=True)[:10]:
                print(f"    {type_name:20} {count:>4}")
        
        print(f"\nStatus: ✓ Statistics calculated")
        assert with_triples > 0


class TestTriplesMapDiagnostics:
    """Diagnostica - tutti i formati"""
    
    def test_triples_map_breakdown_by_type(self, ontology_reader):
        """Breakdown per tipo"""
        name = ontology_reader.config['name']
        triples_map = ontology_reader._logic._triples_map
        
        type_counts = {}
        for instance in triples_map.keys():
            type_name = type(instance).__name__
            type_counts[type_name] = type_counts.get(type_name, 0) + 1
        
        print(f"\n{'='*70}")
        print(f"TRIPLES MAP BREAKDOWN: {name.upper()}")
        print(f"{'='*70}")
        print(f"Total keys: {len(triples_map)}")
        print(f"Unique types: {len(type_counts)}")
        
        print(f"\nBreakdown by instance type:")
        for type_name, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
            percentage = count / len(triples_map) * 100
            print(f"  {type_name:30} {count:>5} ({percentage:>5.1f}%)")
        
        print(f"\nStatus: ✓ Breakdown completed")
    
    def test_compare_cache_vs_triples_map(self, ontology_reader):
        """Confronta cache vs triples_map"""
        name = ontology_reader.config['name']
        cache = ontology_reader._instance_cache
        triples_map = ontology_reader._logic._triples_map
        
        # Conta istanze nella cache
        cache_instances = set()
        for uri, instance_set in cache.items():
            if isinstance(uri, str) and uri.startswith("LITERAL::"):
                continue
            
            if isinstance(instance_set, set):
                cache_instances.update(instance_set)
            else:
                cache_instances.add(instance_set)
        
        # Istanze nella triples_map
        triples_map_instances = set(triples_map.keys())
        
        only_in_cache = cache_instances - triples_map_instances
        only_in_triples_map = triples_map_instances - cache_instances
        
        print(f"\n{'='*70}")
        print(f"CACHE vs TRIPLES MAP: {name.upper()}")
        print(f"{'='*70}")
        print(f"Instances in cache: {len(cache_instances)}")
        print(f"Instances in triples_map: {len(triples_map_instances)}")
        print(f"Only in cache (no triples): {len(only_in_cache)}")
        print(f"Only in triples_map (orphans): {len(only_in_triples_map)}")
        
        if only_in_cache:
            type_breakdown = {}
            for inst in only_in_cache:
                type_name = type(inst).__name__
                type_breakdown.setdefault(type_name, []).append(inst)
            
            print(f"\n  Instances without triples breakdown:")
            for type_name, instances in sorted(type_breakdown.items(), key=lambda x: len(x[1]), reverse=True):
                print(f"    {type_name:20} {len(instances):>4}")
                # Mostra primi 3 esempi
                for inst in instances[:3]:
                    uri = inst.has_identifier if hasattr(inst, 'has_identifier') else str(inst)
                    print(f"      - {uri[:60]}...")
        
        if only_in_triples_map:
            print(f"\n  ⚠ WARNING: Orphan instances in triples_map!")
            for inst in list(only_in_triples_map)[:5]:
                print(f"    - {type(inst).__name__}: {inst}")
        
        print(f"\nStatus: ✓ Comparison completed")
    
    def test_triples_per_instance_statistics(self, ontology_reader):
        """Statistiche numero triple per istanza"""
        name = ontology_reader.config['name']
        triples_map = ontology_reader._logic._triples_map
        
        triple_counts = [len(triples) for triples in triples_map.values()]
        type_stats = {}
        
        for instance, triples in triples_map.items():
            type_name = type(instance).__name__
            if type_name not in type_stats:
                type_stats[type_name] = []
            type_stats[type_name].append(len(triples))
        
        print(f"\n{'='*70}")
        print(f"TRIPLES PER INSTANCE: {name.upper()}")
        print(f"{'='*70}")
        print(f"Total instances: {len(triples_map)}")
        print(f"Total triples: {sum(triple_counts)}")
        print(f"\nGlobal statistics:")
        print(f"  Average: {sum(triple_counts) / len(triple_counts):.2f} triples/instance")
        print(f"  Min: {min(triple_counts)} triples")
        print(f"  Max: {max(triple_counts)} triples")
        
        print(f"\nAverage by instance type:")
        for type_name, counts in sorted(type_stats.items(), key=lambda x: sum(x[1])/len(x[1]), reverse=True):
            avg = sum(counts) / len(counts)
            total = sum(counts)
            print(f"  {type_name:30} {avg:>6.2f} avg  (n={len(counts)}, total={total})")
        
        print(f"\nStatus: ✓ Statistics calculated")