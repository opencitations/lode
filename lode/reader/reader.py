# reader.py - ORCHESTRATOR GENERICO
from rdflib.namespace import DCTERMS, DC, OWL, RDF, RDFS
from lode.reader.loader import Loader
from lode.reader.config_manager import get_configuration
from lode.models import *

class Reader:
    """
    Generic RDF Reader/Orchestrator.
    
    Responsibilities:
    - Calls the loader to parse input RDF (via rdflib)
    - Orchestrates Python model population phases
    - Delegates specific logics for extraction and population to other modules
    """
    
    def __init__(self):
        self._instance_cache = {}
        self._logic = None  # Logic specializzata (OWL, SKOS, RDF, RDFS)
        self._graph = None
        self._configuration = None
    
    def load_instances(self, graph_path: str, read_as: str):
        """Carica e processa grafo RDF"""
        # 1. Parse generico
        loader = Loader(graph_path)
        self._graph = loader.get_graph()
        
        # 2. Seleziona strategia
        self._configuration = get_configuration(read_as)
        
        # 3. Crea Logic specializzata
        self._logic = self._configuration.create_logic(self._graph, self._instance_cache)
        
        # 4. Esecuzione fasi
        self._extract_instances()
    
    def get_instance(self, uri: str, instance_type=None):
        """Ottiene istanze per URI"""
        uri_identifier = None
        
        for identifier in self._instance_cache.keys():
            if str(identifier) == uri:
                uri_identifier = identifier
                break
        
        if uri_identifier is None:
            return None
        
        instances = self._instance_cache[uri_identifier]
        
        if instance_type is None:
            return instances
        
        for instance in instances:
            if isinstance(instance, instance_type):
                return instance
        
        return None
    
    def get_instances(self) -> dict:
        """Raggruppa istanze per tipo"""
        grouped = {}
        
        for uri_identifier, instances in self._instance_cache.items():
            if isinstance(uri_identifier, str) and uri_identifier.startswith("LITERAL::"):
                continue
            
            instances_list = instances if isinstance(instances, set) else [instances]
            
            for instance in instances_list:
                class_name = instance.__class__.__name__
                if class_name not in grouped:
                    grouped[class_name] = []
                grouped[class_name].append(instance)
        
        return grouped
    
    def get_triples_for_instance(self, instance):
        """Ottiene le triple RDF associate a un'istanza Python"""
        if self._logic and hasattr(self._logic, '_triples_map'):
            return self._logic._triples_map.get(instance, set())
        return set()

    def get_all_triples_map(self) -> dict:
        """Ottiene la mappa completa instance → triple"""
        if self._logic and hasattr(self._logic, '_triples_map'):
            return self._logic._triples_map
        return {}
    
     
    # function reused by the api to push instances
    def to_dict(self, instance) -> dict:
        """Serializza un'istanza Python in dict JSON, includendo le triple RDF"""
        result = {
            "instance": str(instance),
            "type": type(instance).__name__,
            "uri": str(instance.has_identifier) if instance.has_identifier else None,
            "properties": {},
            "rdf_triples": []
        }
        
        # Serializza le proprietà dell'istanza
        for attr_name in instance.__dict__.keys():
            value = getattr(instance, attr_name)
            # removes empty values from the properties
            if value is not None and not (isinstance(value, (list, set)) and not value):
                result["properties"][attr_name] = str(value)
        
        # Aggiungi le triple RDF associate
        triples = self.get_triples_for_instance(instance)
        for s, p, o in triples:
            triple_dict = {
                "subject": str(s),
                "predicate": str(p),
                "object": str(o)
            }
            result["rdf_triples"].append(triple_dict)
        
        return result

    def _serialize_value(self, value):
        """Helper per serializzare diversi tipi di valori"""
        if isinstance(value, (str, int, float, bool)):
            return value
        elif isinstance(value, (list, set)):
            return [self._serialize_value(v) for v in value]
        elif hasattr(value, 'uri'):
            return str(value.uri)
        else:
            return str(value)
        
    def get_viewer(self):
        """Ottiene il viewer appropriato per il formato corrente."""
        if not self._configuration:
            raise ValueError("No configuration loaded. Call load_instances() first.")

        return self._configuration.create_viewer(self)
    
    def clear_cache(self):
        """Pulisce la cache"""
        self._instance_cache.clear()
        if self._logic:
            self._logic.clear_cache()
    
    # ==================== ESTRAZIONE (ORCHESTRAZIONE) ====================
    
    def _extract_instances(self):
        """Estrazione in 6 fasi orchestrate"""
        print("\n" + "="*60)
        print("ESTRAZIONE INSTANCES")
        print("="*60)
        
        # FASE 0: Pre-crea datatypes (comune a tutti)
        # self._phase0_create_datatypes()
        
       # FASE 1-4: Delegate alla Logic specifica
        self._logic.phase1_classify_from_predicates()
        self._logic.phase2_create_from_types()
        self._logic.phase3_populate_properties()
        self._logic.phase4_process_group_axioms()
        
        # FASE 5: Fallback (comune)
        self._logic.phase5_fallback()
        
        # FASE 6: Statements (solo RDF)
        self._logic.phase6_create_statements()
    
    # def _phase0_create_datatypes(self):
    #     """Pre-crea tutti i Datatype (comune a tutti i formati)"""
    #     print("\n--- FASE 0: Datatypes ---")
        
    #     created = 0
        
    #     # 1. URI XSD
    #     for s, p, o in self._graph:
    #         if isinstance(s, URIRef) and str(s).startswith(str(XSD)):
    #             if s not in self._instance_cache:
    #                 self._logic.create_empty_instance(s, Datatype)
    #                 created += 1
            
    #         if isinstance(o, URIRef) and str(o).startswith(str(XSD)):
    #             if o not in self._instance_cache:
    #                 self._logic.create_empty_instance(o, Datatype)
    #                 created += 1
        
    #     # 2. rdfs:Literal
    #     if RDFS.Literal not in self._instance_cache:
    #         self._logic.create_empty_instance(RDFS.Literal, Datatype)
    #         created += 1
        
    #     # 3. BNode Datatypes
    #     for bnode in self._graph.subjects(RDF.type, RDFS.Datatype):
    #         if isinstance(bnode, BNode) and bnode not in self._instance_cache:
    #             self._logic.create_empty_instance(bnode, Datatype)
    #             created += 1
        
    #     print(f"  Creati {created} datatypes")
    
    def _phase5_fallback(self):
        """Fallback per risorse non categorizzate (comune)"""
        print("\n--- FASE 5: Fallback ---")
        
        fallback_class = self._configuration.get_fallback_class()
        if not fallback_class:
            print("  Nessun fallback configurato")
            return
        
        all_subjects = set(self._graph.subjects())
        fallback_count = 0
        
        for subj in all_subjects:
            if subj not in self._instance_cache:
                self._logic.get_or_create(subj, fallback_class)
                fallback_count += 1
        
        print(f"  Fallback: {fallback_count} risorse -> {fallback_class.__name__}")

    def get_ontology_metadata(self) -> Model:
        """
        Extracts metadata and returns a populated Model object.
        """
        if self._graph is None:
            return Model()

        # 1. Create the Model instance
        ontology_model = Model()

        # 2. Find the owl:Ontology node
        ontology_node = self._graph.value(predicate=RDF.type, object=OWL.Ontology)

        if ontology_node:
            # --- IDENTIFIER (IRI) ---
            ontology_model.set_has_identifier(str(ontology_node))

            # --- TITLE (Label) ---
            title = (
                    self._graph.value(ontology_node, DCTERMS.title) or
                    self._graph.value(ontology_node, DC.title) or
                    self._graph.value(ontology_node, RDFS.label)
            )
            if title:
                ontology_model.set_has_label(str(title))

            # --- DESCRIPTION (Comment) ---
            comment = (
                    self._graph.value(ontology_node, DCTERMS.description) or
                    self._graph.value(ontology_node, RDFS.comment)
            )
            if comment:
                ontology_model.set_has_comment(str(comment))

            # --- VERSION INFO ---
            version_info = self._graph.value(ontology_node, OWL.versionInfo)
            if version_info:
                ontology_model.set_has_version_info(str(version_info))

            # --- VERSION IRI ---
            version_iri = self._graph.value(ontology_node, OWL.versionIRI)
            if version_iri:
                v_model = Model()
                v_model.set_has_identifier(str(version_iri))
                ontology_model.set_has_version(v_model)

            # --- IMPORTS ---
            for imported_iri in self._graph.objects(ontology_node, OWL.imports):
                imported_model = Model()
                imported_model.set_has_identifier(str(imported_iri))
                ontology_model.set_imports(imported_model)

            # --- CREATORS (Custom handling) ---
            for pred in [DCTERMS.creator, DC.creator]:
                for creator in self._graph.objects(ontology_node, pred):
                    ontology_model.set_has_creator(creator)


            # --- CONTRIBUTORS (Custom handling) ---
            for pred in [DCTERMS.contributor, DC.contributor]:
                for contributor in self._graph.objects(ontology_node, pred):
                    ontology_model.set_has_contributor(contributor)

        return ontology_model