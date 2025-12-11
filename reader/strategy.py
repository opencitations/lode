from abc import ABC, abstractmethod
from rdflib import URIRef, Graph, BNode, Node
from rdflib.namespace import RDF, RDFS, OWL, SKOS
from .models import *


class MappingStrategy(ABC):
    """
    Classe astratta: definisce la strategia di mapping RDF → Python.
    Ogni strategia sa:
    - QUALI tipi RDF mappare a QUALI classi Python
    - QUALE factory usare per la semantica
    """
    
    @abstractmethod
    def get_type_mapping(self) -> dict[Node, type]:
        """
        Ritorna il dizionario di mapping: {rdf_type: python_class}
        
        Returns:
            dict: Mapping tra URIRef RDF e classi Python
        """
        pass

    def find_implicit_restrictions(self, graph: Graph) -> dict[BNode, type]:
        """
        Di default, nessuna strategia ha restriction implicite.
        Solo OWL le ha, quindi override solo lì.
        """
        return {}

    @abstractmethod
    def associate_fallback_class():
        ""
        pass
    
    @abstractmethod
    def create_factory(self, graph: Graph, cache: dict):
        """
        Crea la factory appropriata per questa strategia.
        
        Args:
            graph: Grafo RDF caricato
            cache: Cache condivisa per le istanze
        
        Returns:
            SemanticFactory: Factory configurata per questa strategia
        """
        pass


class OwlMappingStrategy(MappingStrategy):
    """
    Mapping strategy for interpreting OWL ontologies.
    """
    
    def get_type_mapping(self) -> dict[Node, type]:
        return {
            OWL.ObjectProperty: Relation,
            OWL.DatatypeProperty: Attribute,
            OWL.AnnotationProperty: Annotation,
            OWL.Class: Concept,
            RDFS.Datatype: Datatype,
            OWL.Restriction: Restriction,
            OWL.Ontology: Model,
            OWL.NamedIndividual: Individual,
            # Statement is the fallback here
        }
    
    def find_implicit_restrictions(self, graph: Graph) -> dict[BNode, type]:
        """
        Trova RICORSIVAMENTE tutti i BNode che sono Restriction implicite,
        inclusi quelli annidati dentro liste RDF.
        """
        implicit_restrictions = {}
        processed = set()
        
        # Predicati che indicano una Restriction
        restriction_predicates = [
            OWL.hasValue,
            OWL.someValuesFrom,
            OWL.allValuesFrom,
            OWL.oneOf,
            OWL.cardinality,
            OWL.minCardinality,
            OWL.maxCardinality,
            OWL.intersectionOf,
            OWL.unionOf,
            OWL.complementOf,
        ]
        
        print("\n=== find_implicit_restrictions ===")
        
        # STEP 1: Cerca tutti i BNode radice
        for predicate in restriction_predicates:
            for uri in graph.subjects(predicate, None):
                if isinstance(uri, BNode) and uri not in processed:
                    self._collect_bnodes_recursively(uri, graph, implicit_restrictions, processed)
        
        # STEP 2: CRITICO! Cerca BNode DENTRO le liste RDF gia trovate
        for bnode in list(implicit_restrictions.keys()):
            for predicate, obj in graph.predicate_objects(bnode):
                if predicate in [OWL.intersectionOf, OWL.unionOf, OWL.oneOf, OWL.hasValue]:
                    for item in graph.items(obj):
                        if isinstance(item, BNode) and item not in processed:
                            self._collect_bnodes_recursively(item, graph, implicit_restrictions, processed)
        
        return implicit_restrictions

    def _collect_bnodes_recursively(self, uri: BNode, graph: Graph, 
                                    implicit_restrictions: dict, 
                                    processed: set):
        """Raccoglie ricorsivamente un BNode e tutti i BNode che contiene."""
        if uri in processed:
            return
        
        processed.add(uri)
        
        # Classifica questo BNode
        python_class = self.classify_restriction(uri, graph)
        implicit_restrictions[uri] = python_class
        
        # Cerca BNode annidati
        for predicate, obj in graph.predicate_objects(uri):
            if isinstance(obj, BNode):
                self._collect_bnodes_recursively(obj, graph, implicit_restrictions, processed)
            
            if predicate in [OWL.intersectionOf, OWL.unionOf, OWL.oneOf, OWL.hasValue]:
                for item in graph.items(obj):
                    if isinstance(item, BNode):
                        self._collect_bnodes_recursively(item, graph, implicit_restrictions, processed)
        
    def classify_restriction(self, uri: BNode, graph: Graph) -> type:
        """
        Classifica tutti i BNode anonimi come sottotipi di Restriction.
        """
        
        # PRIMA: controlla se è una restriction specifica
        # -- CASO 1: TruthFunction con rdf:type owl:Class 
        # <owl:Class>
        # <owl:intersectionOf>...</owl:intersectionOf>
        # </owl:Class>
        
        # TruthFunction (operatori booleani)
        if any([
            (uri, OWL.intersectionOf, None) in graph,
            (uri, OWL.unionOf, None) in graph,
            (uri, OWL.complementOf, None) in graph,
        ]):
            return TruthFunction
        
        # Value
        if (uri, OWL.hasValue, None) in graph:
            return Value

        # OneOf
        if (uri, OWL.oneOf, None) in graph:
            return OneOf
        
        # Quantifier
        if any([
            (uri, OWL.someValuesFrom, None) in graph,
            (uri, OWL.allValuesFrom, None) in graph,
        ]):
            return Quantifier
        
        # Cardinality
        if any([
            (uri, OWL.cardinality, None) in graph,
            (uri, OWL.minCardinality, None) in graph,
            (uri, OWL.maxCardinality, None) in graph,
            (uri, OWL.qualifiedCardinality, None) in graph,
            (uri, OWL.minQualifiedCardinality, None) in graph,
            (uri, OWL.maxQualifiedCardinality, None) in graph,
        ]):
            return Cardinality
        
        # Default
        print('RESTRICTION FALLBACK, needs additional study', uri)
        for p, o in graph.predicate_objects(uri):
            print(uri, p, o)

        for s, p in graph.subject_predicates(uri):
            print(s, p, uri)
            for s2, p2 in graph.subject_predicates(s):
                print(s2, p2, s)
        return Restriction

    def associate_fallback_class(self) -> type:
        """
        Ritorna la classe Python da usare come fallback per risorse
        che non matchano nessun tipo RDF nel type_mapping.
        
        Returns:
            type: Classe Python fallback (default: Statement)
        """
        return Statement
    
    def create_factory(self, graph: Graph, cache: dict):
        from .factory import OwlFactory
        return OwlFactory(graph, cache)


class RdfsMappingStrategy(MappingStrategy):
    """
    Strategia per interpretazione RDFS.
    Più semplice di OWL: non distingue tipi di proprietà.
    """
    
    def get_type_mapping(self) -> dict[URIRef, type]:
        return {
            # RDFS core
            RDFS.Class: Concept,
            RDF.Property: Property,
            
            # OWL compatibility 
            OWL.Class: Concept,
            OWL.ObjectProperty: Property,
            OWL.DatatypeProperty: Attribute,
            OWL.AnnotationProperty: Annotation,
            OWL.Restriction: Concept,
            OWL.Ontology: Model,

            # SKOS compatibility
            SKOS.Concept: Concept,
            SKOS.ConceptScheme : Model
        }
    
    def create_factory(self, graph: Graph, cache: dict):
        from .factory import RdfsFactory
        return RdfsFactory(graph, cache)


class SkosMappingStrategy(MappingStrategy):
    """
    Strategia per interpretazione SKOS.
    Focus su concetti e schemi concettuali.
    """
    
    def get_type_mapping(self) -> dict[URIRef, type]:
        return {
            SKOS.Concept: Concept,
            SKOS.ConceptScheme : Model
        }
    
    def associate_fallback_class(self) -> type:
        """
        Ritorna la classe Python da usare come fallback per risorse
        che non matchano nessun tipo RDF nel type_mapping.
        
        Returns:
            type: Classe Python fallback (default: Statement) TO BE CHANGED!!
        """
        return Statement
    
    def create_factory(self, graph: Graph, cache: dict):
        from .factory import SkosFactory
        return SkosFactory(graph, cache)


# Registry delle strategie disponibili
STRATEGY_REGISTRY = {
    'OWL': OwlMappingStrategy,
    'RDFS': RdfsMappingStrategy,
    'SKOS': SkosMappingStrategy,
}


def get_strategy(strategy_name: str) -> MappingStrategy:
    """
    Factory function per ottenere una strategia dal nome.
    
    Args:
        strategy_name: Nome della strategia ('OWL', 'RDFS', 'SKOS')
    
    Returns:
        MappingStrategy: Istanza della strategia richiesta
    
    Raises:
        ValueError: Se la strategia non esiste
    """
    key = strategy_name.upper()
    
    if key not in STRATEGY_REGISTRY:
        available = ', '.join(STRATEGY_REGISTRY.keys())
        raise ValueError(
            f"Unknown strategy: '{strategy_name}'. "
            f"Available strategies: {available}"
        )
    
    return STRATEGY_REGISTRY[key]()