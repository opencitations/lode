from rdflib import URIRef, RDF, Node, IdentifiedNode, BNode
from rdflib.namespace import RDF, RDFS, OWL, SKOS
from .loader import Loader
from .strategy import get_strategy, MappingStrategy
from .models import *

class Reader:
    """
    Orchestratore generale: coordina Reader → Strategy → Factory.
    
    Responsabilità:
    - Caricare il grafo RDF tramite Loader
    - Selezionare la strategia di mapping appropriata
    - Coordinare il processo di estrazione in 2 fasi
    - Fornire API pubblica per accesso alle istanze
    
    NON sa di:
    - Semantica OWL/RDFS/SKOS specifica
    - Dettagli di popolamento delle istanze
    - Inferenze o regole specifiche
    """
    
    def __init__(self):
        self._instance_cache = {} # contains {rdflib_object_id : set(python emtpy object)}
        self._factory = None
        self._graph = None
        self._strategy = None
    
    # ==================== API PUBBLICA ====================
    
    def load_instances(self, graph_path: str, read_as: str):
        """
        Carica TUTTE le istanze da un grafo RDF secondo la strategia specificata.
        
        Args:
            graph_path: URL o percorso file locale
            read_as: Strategia di interpretazione ('OWL', 'RDFS', 'SKOS')
        
        Example:
            mapper = GraphMapper()
            mapper.load_instances("http://purl.org/spar/cito/", read_as='OWL')
            
            cites = mapper.get_instance("http://purl.org/spar/cito/cites")
            print(cites.get_has_label()[0].get_has_value())
        """
        # 1. Carica grafo RDF (usa il Loader esistente)
        loader = Loader(graph_path)
        self._graph = loader.get_graph()
        
        # 2. Seleziona strategia di mapping
        self._strategy = get_strategy(read_as)
        
        # 3. Crea factory dalla strategia
        self._factory = self._strategy.create_factory(
            self._graph,
            self._instance_cache
        )
        
        # 4. Esegui estrazione in 2 fasi
        self._extract_instances()
    
    def get_instance(self, uri: str, instance_type=None):
        """
        Ottiene istanze per URI.
        
        Args:
            uri: URI della risorsa come stringa
            instance_type: (opzionale) Tipo specifico da restituire
        
        Returns:
            - Se instance_type è specificato: singola istanza di quel tipo o None
            - Altrimenti: set di tutte le istanze per quell'URI o None
        """
        
        # Cerca la risorsa nel grafo per ottenere l'Identifier corretto
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
        
        # Cerca istanza di tipo specifico
        try:
            for instance in instances:
                if isinstance(instance, instance_type):
                    return instance
        except Exception as e:
            print(f"Cannot find Resource {uri} in loaded Semantic Artefact: {e}")
            return None
    
    # def get_instances(self) -> dict:
    #     """
    #     Raggruppa le istanze per tipo di classe.
        
    #     Returns:
    #         dict: {class_name: [instances]}
    #     """
    #     grouped = {}
        
    #     for uri_str, instances_set in self._instance_cache.items():
    #         for instance in instances_set:
    #             class_name = instance.__class__.__name__
    #             if class_name not in grouped:
    #                 grouped[class_name] = []
    #             grouped[class_name].append(instance)
        
    #     return grouped

    def get_instances(self) -> dict:
        """
        Raggruppa le istanze per tipo di classe.
        
        Returns:
            dict: {class_name: [instances]}
        """
        grouped = {}
        
        for uri_identifier, instances in self._instance_cache.items():
            # Salta i Literal (che hanno una chiave stringa composita "LITERAL::...") TO BE CHANGED
            if isinstance(uri_identifier, str) and uri_identifier.startswith("LITERAL::"):
                continue
            
            # Gestisci sia set che singole istanze
            if isinstance(instances, set):
                instances_list = instances
            else:
                instances_list = [instances]
            
            for instance in instances_list:
                class_name = instance.__class__.__name__
                if class_name not in grouped:
                    grouped[class_name] = []
                grouped[class_name].append(instance)
        
        return grouped
    
    def clear_cache(self):
        """Pulisce la cache delle istanze"""
        self._instance_cache.clear()
        if self._factory:
            self._factory.clear_cache()
    
    # ==================== LOGICA INTERNA ====================
    
    def _extract_instances(self):
        """
        Processo di estrazione in 2 fasi (agnostico dalla strategia).
        
        FASE 1: Creazione istanze vuote secondo mapping strategico
        FASE 2: Popolamento con dipendenze risolte
        """
        type_mapping = self._strategy.get_type_mapping()
        
        # FASE 1: Creazione istanze vuote
        self._create_empty_instances(type_mapping)
        
        # FASE 2: Popolamento
        self._populate_all_instances()
    
    def _create_empty_instances(self, type_mapping: dict):
        """
        FASE 1: Crea tutte le istanze vuote secondo il mapping strategico.
        """
        processed_uris = set()
        
        print("\n=== FASE 1: Creazione istanze ===")
        
        # FASE 1A: Processa tipi espliciti dal type_mapping
        for rdf_type, python_class in type_mapping.items():
            for uri in self._graph.subjects(RDF.type, rdf_type):
                if not isinstance(uri, Node):
                    continue
                
                final_class = python_class
                
                print(f"\nTrovato URI: {uri}")
                print(f"   - rdf:type: {rdf_type}")
                print(f"   - Classe default: {final_class.__name__}")
                
                if isinstance(uri, BNode):
                    print(f"   - E un BNode! Chiedo alla strategy...")
                    better_class = self._strategy.classify_restriction(uri, self._graph)
                    print(f"   - Strategy dice: {better_class.__name__}")
                    
                    if better_class != Concept:
                        final_class = better_class
                        print(f"   - Uso la classe specifica: {final_class.__name__}")
                
                class_name = final_class.__name__
                if (uri, class_name) in processed_uris:
                    print(f"   - Gia processato, skip")
                    continue
                
                print(f"   - Creo come: {final_class.__name__}")
                self._factory.create_empty_instance(uri, final_class)
                processed_uris.add((uri, class_name))
        
        # FASE 1B: Processa restriction implicite (quelle SENZA rdf:type)
        print("\n=== Cerco restriction implicite ===")
        implicit_restrictions = self._strategy.find_implicit_restrictions(self._graph)
        
        print(f"\nTrovate {len(implicit_restrictions)} restriction implicite")
        for uri, python_class in implicit_restrictions.items():
            print(f"\nBNode implicito: {uri}")
            print(f"   - Classe: {python_class.__name__}")
            
            class_name = python_class.__name__
            
            if any(uri == processed_uri for processed_uri, _ in processed_uris):
                print(f"   - Gia processato, skip")
                continue
            
            print(f"   - Creo come: {python_class.__name__}")
            self._factory.create_empty_instance(uri, python_class)
            processed_uris.add((uri, class_name))
        
        # FASE 1C: Cerca BNode annidati dentro le istanze gia create
        print("\n=== Cerco BNode annidati dentro Concept ===")
        for uri in list(self._instance_cache.keys()):
            if not isinstance(uri, (URIRef, BNode)):
                continue
            
            # Cerca equivalentClass, intersectionOf, unionOf, oneOf
            for predicate in [OWL.equivalentClass, OWL.intersectionOf, OWL.unionOf, OWL.oneOf, OWL.hasValue]:
                for obj in self._graph.objects(uri, predicate):
                    if isinstance(obj, BNode) and not any(obj == processed_uri for processed_uri, _ in processed_uris):
                        # Classifica e crea
                        python_class = self._strategy.classify_restriction(obj, self._graph)
                        print(f"Trovato BNode annidato: {obj} -> {python_class.__name__}")
                        self._factory.create_empty_instance(obj, python_class)
                        processed_uris.add((obj, python_class.__name__))
                    
                    # Se è una lista RDF, esplora dentro
                    if predicate in [OWL.intersectionOf, OWL.unionOf, OWL.oneOf, OWL.hasValue]:
                        for item in self._graph.items(obj):
                            if isinstance(item, BNode) and not any(item == processed_uri for processed_uri, _ in processed_uris):
                                python_class = self._strategy.classify_restriction(item, self._graph)
                                print(f"  Trovato BNode in lista: {item} -> {python_class.__name__}")
                                self._factory.create_empty_instance(item, python_class)
                                processed_uris.add((item, python_class.__name__))

        # FASE 1D: Cattura TUTTE le risorse rimanenti come fallback
        print("\n=== FASE 1D: Cattura risorse senza tipo esplicito ===")
        fallback_class = self._strategy.associate_fallback_class()
        print(f"Classe fallback: {fallback_class.__name__}")

    def _populate_all_instances(self):
        """
        FASE 2: Popola tutte le istanze create.
        """
        # Crea una lista delle chiavi per evitare "dictionary changed size during iteration"
        uri_list = list(self._instance_cache.keys())
    
        for uri in uri_list:  # URIRef o BNode
            instances_set = self._instance_cache[uri]
            for instance in list(instances_set):
                self._factory.populate_instance(instance, uri)