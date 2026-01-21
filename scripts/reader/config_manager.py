# config_magarer.py - STRATEGIE CON CONFIG UNIFICATA

import yaml
from pathlib import Path
from abc import ABC, abstractmethod
from rdflib import URIRef, Graph, Node
from models import *


class ConfigManager(ABC):
    """Strategia basata su config YAML unico"""
    
    def __init__(self):
        self.config = self._load_config()
        self._type_mapping_cache = None
        self._property_mapping_cache = None
    
    @abstractmethod
    def create_logic(self, graph: Graph, cache: dict):
        """Factory method per creare Logic specifica"""
        pass
    
    def _load_config(self) -> dict:
        """Carica config da file YAML unico"""
        config_path = Path(__file__).parent / 'config' / 'base.yaml'
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        return config
    
    # ========== NAMESPACE MAP ==========
    NAMESPACES = {
        'owl': 'http://www.w3.org/2002/07/owl#',
        'rdfs': 'http://www.w3.org/2000/01/rdf-schema#',
        'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
        'skos': 'http://www.w3.org/2004/02/skos/core#'
    }
    
    # ========== CLASS MAP ==========
    CLASSES = {
        'Concept': Concept,
        'Property': Property,
        'Relation': Relation,
        'Attribute': Attribute,
        'Annotation': Annotation,
        'Restriction': Restriction,
        'Quantifier': Quantifier,
        'Cardinality': Cardinality,
        'TruthFunction': TruthFunction,
        'Container': Container,
        'OneOf': OneOf,
        'Value': Value,
        'Model': Model,
        'Collection': Collection,
        'Statement': Statement,
        'Datatype': Datatype,
        'Literal': Literal,
        'Resource': Resource,
        'Individual': Individual
    }
    
    def _parse_uri(self, uri_str: str) -> URIRef:
        """owl:Class -> URIRef"""
        if ':' not in uri_str:
            return URIRef(uri_str)
        
        prefix, local = uri_str.split(':', 1)
        return URIRef(self.NAMESPACES[prefix] + local)
    
    def _parse_class(self, class_name: str):
        """'Concept' -> Concept class"""
        return self.CLASSES[class_name]
    
    def _parse_value(self, value):
        """Parse valore config"""
        if value == 'Literal':
            return 'Literal'
        elif value is True or value is False:
            return value
        elif isinstance(value, str) and value in self.CLASSES:
            return self._parse_class(value)
        return value
    
    # ========== CONFIG ACCESSORS ==========
    
    def get_type_mapping(self) -> dict[URIRef, dict]:
        """rdf:type -> {target_class, setters, ...}"""
        if self._type_mapping_cache is None:
            self._type_mapping_cache = {
                self._parse_uri(uri): self._parse_config(cfg)
                for uri, cfg in self.config['mapper'].items()
                if cfg.get('is') == 'class'
            }
        return self._type_mapping_cache

    def get_property_mapping(self) -> dict[URIRef, dict]:
        """predicate -> {target_classes, setters, handler, ...}"""
        if self._property_mapping_cache is None:
            self._property_mapping_cache = {
                self._parse_uri(uri): self._parse_config(cfg)
                for uri, cfg in self.config['mapper'].items()
                if cfg.get('is') == 'predicate'
            }
        return self._property_mapping_cache
    
    def _parse_config(self, cfg: dict) -> dict:
        """Parse un blocco di config"""
        parsed = cfg.copy()
        
        if 'target_class' in parsed:
            parsed['target_class'] = self._parse_class(parsed['target_class'])
        
        if 'inferred_class' in parsed:
            parsed['inferred_class'] = self._parse_class(parsed['inferred_class'])
        
        if 'target_classes' in parsed:
            parsed['target_classes'] = [
                self._parse_class(tc) for tc in parsed['target_classes']
            ]
        
        if 'setters' in parsed:
            parsed['setters'] = [
                {k: self._parse_value(v)} if isinstance(item, dict) else item
                for item in parsed['setters']
                for k, v in (item.items() if isinstance(item, dict) else [(item, None)])
            ]
        
        return parsed
    
    def get_group_axioms(self) -> dict[URIRef, str]:
        """Group axioms: URI -> handler_name"""
        return {
            self._parse_uri(uri): handler
            for uri, handler in self.config.get('enricher', {}).items()
        }
    
    def get_fallback_class(self) -> type | None:
        """Classe fallback per risorse non categorizzate"""
        fallback = self.config.get('mapper', {}).get('fallback_class')
        if fallback:
            return self.CLASSES.get(fallback, Statement)
        return None
    
    # ========== HELPER METHODS ==========
    
    def get_classifier_predicates(self) -> set[URIRef]:
        """Predicati con 'inferred_class'"""
        return {
            pred for pred, cfg in self.get_property_mapping().items()
            if 'inferred_class' in cfg
        }
    
    def classify_by_predicate(self, uri: Node, graph: Graph) -> type | None:
        """Classifica guardando predicati"""
        for predicate, cfg in self.get_property_mapping().items():
            if 'inferred_class' in cfg and (uri, predicate, None) in graph:
                return cfg['inferred_class']
        return None


# ========== CONCRETE STRATEGIES ==========

class OwlConfigManager(ConfigManager):
    def create_logic(self, graph: Graph, cache: dict):
        from logic import OwlLogic
        return OwlLogic(graph, cache, self)


# class RdfsConfigManager(ConfigManager):
#     def create_logic(self, graph: Graph, cache: dict):
#         from logic import RdfsLogic
#         return RdfsLogic(graph, cache, self)


class RdfConfigManager(ConfigManager):
    def create_logic(self, graph: Graph, cache: dict):
        from logic import RdfLogic
        return RdfLogic(graph, cache, self)


class SkosConfigManager(ConfigManager):
    def create_logic(self, graph: Graph, cache: dict):
        from logic import SkosLogic
        return SkosLogic(graph, cache, self)


# ========== CONFIGURATIONS REGISTRY ==========

CONFIGURATION_REGISTRY = {
    'OWL': OwlConfigManager,
    # 'RDFS': RdfsConfigManager,
    'SKOS': SkosConfigManager,
    'RDF': RdfConfigManager
}


def get_configuration(configuration_name: str) -> ConfigManager:
    key = configuration_name.upper()
    if key not in CONFIGURATION_REGISTRY:
        available = ', '.join(CONFIGURATION_REGISTRY.keys())
        raise ValueError(f"Unknown configuration: '{configuration_name}'. Available: {available}")
    return CONFIGURATION_REGISTRY[key]()