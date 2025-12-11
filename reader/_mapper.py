from rdflib import URIRef, RDF, Node
from .loader import Parser
from .factory import *
from .models import *


class GraphMapper:
    """
    API principale per caricare istanze da grafi RDF.
    
    Metodo principale:
        load_instances(graph_path, read_as='OWL')
    
    Getter:
        get_instance(uri) -> singola istanza o None
    """
    
    def __init__(self):
        self._instance_cache = {}  # {uri_str: instance}
        self._factory = None
        self._graph = None
    
    # ==================== METODO PRINCIPALE ====================
    
    def load_instances(self, graph_path : str, read_as : str):
        """
        Carica TUTTE le istanze da un grafo RDF.
        
        Args:
            graph_path: URL or local file path
            read_as: Semantic Artefact Type (OWL, RDF, RDFS, SKOS)
        
        Example:
            mapper = GraphMapper()
            mapper.load_instances("http://purl.org/spar/cito/", read_as='OWL')
            
            # Poi usa getter
            cites = mapper.get_instance("http://purl.org/spar/cito/cites")
        """
        # 1. Carica grafo 
        parser = Parser(graph_path)
        self._graph = parser.get_graph()
        
        # 2. Assegna e crea la factory appropriata 
        if read_as.upper() == 'OWL':
            self._factory = OwlFactory(self._graph, instance_cache=self._instance_cache)
        elif read_as.upper() == 'RDF':
            self._factory = RdfFactory(self._graph, instance_cache=self._instance_cache)
        # elif read_as.upper() == 'RDFS':
        #     self._factory = RdfsFactory(self._graph)
        # elif read_as.upper() == 'SKOS':
        #     self._factory = SkosFactory(self._graph)
        else:
            raise ValueError(f"read_as should be 'OWL', 'RDF', 'RDFS' o 'SKOS', '{read_as}' not allowed")
        
        # 3. Estrai tutte le istanze
        self._instances = self._create_all_instances(read_as)
    
    # ==================== GETTER ====================
    
    def get_instance(self, uri: str):
        """
        Ottiene una singola istanza per URI.
        
        Args:
            uri: URI della risorsa (es. "http://purl.org/spar/cito/cites")
        
        Returns:
            Instance popolata o None se non trovata
        
        Example:
            cites = mapper.get_instance("http://purl.org/spar/cito/cites")
            if cites:
                print(cites.get_has_label()[0].get_has_value())
        """
        return self._instance_cache.get(uri)
    
    # ==================== LOGICA INTERNA ====================
    
    # Mapping RDF type → Python class
    RDF_TO_PYTHON_MAP = {
        'OWL' : {
            URIRef("http://www.w3.org/2002/07/owl#ObjectProperty"): Relation,
            URIRef("http://www.w3.org/2002/07/owl#DatatypeProperty"): Attribute,
            URIRef("http://www.w3.org/2002/07/owl#AnnotationProperty"): Annotation,
            URIRef("http://www.w3.org/2002/07/owl#Class"): Concept,
            URIRef("http://www.w3.org/2000/01/rdf-schema#Datatype"): Datatype,
            URIRef("http://www.w3.org/2002/07/owl#Restriction"): Restriction,
            URIRef("http://www.w3.org/2002/07/owl#Ontology"): Model,
        }, 
        'RDF' : {
            URIRef("http://www.w3.org/2000/01/rdf-schema#Class"): Concept,
            URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#Property"): Property,
        }
    }
    
    def _create_all_instances(self, read_as : str):
        """Estrae tutte le istanze dal grafo (logica a 2 fasi)"""
        instances = {}
        
        # FASE 1: Creazione istanze vuote
        for rdf_type, python_class in self.RDF_TO_PYTHON_MAP[read_as].items():
            for uri in self._graph.subjects(RDF.type, rdf_type):
                if not isinstance(uri, Node):
                    continue
                
                uri_str = str(uri)
                if uri_str in instances:
                    continue
                
                instance = self._factory._get_or_create_instance(uri, python_class)
                instances[uri_str] = instance
        
        # FASE 2: Popolamento
        for uri_str, instance in instances.items():
            uri = URIRef(uri_str)
            self._populate_instance(instance, uri)
        
        return instances
    
    def _populate_instance(self, instance, uri):
        """Popola un'istanza in base al suo tipo"""
        if isinstance(instance, Relation):
            self._factory._populate_relation(instance, uri)
        elif isinstance(instance, Attribute):
            self._factory._populate_attribute(instance, uri)
        elif isinstance(instance, Annotation):
            self._factory._populate_annotation(instance, uri)
        elif isinstance(instance, Datatype):
            self._factory._populate_datatype(instance, uri)
        elif isinstance(instance, Concept):
            self._factory._populate_concept(instance, uri)
        elif isinstance(instance, Property):
            self._factory._populate_property(instance, uri)
        elif isinstance(instance, Resource):
            self._factory._populate_resource(instance, uri)
        elif isinstance(instance, Restriction):
            self._factory._populate_restriction(instance, uri)
        elif isinstance(instance, Model):
            self._factory._populate_model(instance, uri)