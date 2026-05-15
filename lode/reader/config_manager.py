# config_magarer.py - STRATEGIE CON CONFIG UNIFICATA

import yaml
from pathlib import Path
from abc import ABC, abstractmethod
from rdflib import URIRef, Graph, Node
from lode.models import *

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

    @property
    @abstractmethod
    def config_name(self) -> str:
        """Nome del file config specifico: 'owl' | 'skos' | 'rdfs'"""
        pass
    
    def _load_config(self) -> dict:
        config_dir = Path(__file__).parent / 'config'
        
        with open(config_dir / 'base.yaml') as f:
            base = yaml.safe_load(f)
        
        with open(config_dir / f'{self.config_name}.yaml') as f:
            specific = yaml.safe_load(f)
        
        return self._deep_merge(base, specific)
    
    def _deep_merge(self, base: dict, override: dict) -> dict:
        result = base.copy()
        for key, value in override.items():
            if key in ('name', 'inherits'):
                continue
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result
    
    # def _load_config(self) -> dict:
    #     """Carica config da file YAML unico"""
    #     config_path = Path(__file__).parent / 'config' / 'base.yaml'
        
    #     with open(config_path, 'r') as f:
    #         config = yaml.safe_load(f)
        
    #     return config
    
    @abstractmethod
    def create_viewer(self, reader):
        """Factory method per creare Viewer specifico"""
        pass
    
    # ========== NAMESPACE MAP ==========
    NAMESPACES = {
        'owl': 'http://www.w3.org/2002/07/owl#',
        'rdfs': 'http://www.w3.org/2000/01/rdf-schema#',
        'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
        'skos': 'http://www.w3.org/2004/02/skos/core#', 
        'xsd': "http://www.w3.org/2001/XMLSchema#",
        'swrl': 'http://www.w3.org/2003/11/swrl#'
    }
    
    def _parse_uri(self, uri_str: str) -> URIRef:
        """owl:Class -> URIRef"""
        if ':' not in uri_str:
            return URIRef(uri_str)
        
        prefix, local = uri_str.split(':', 1)
        return URIRef(self.NAMESPACES[prefix] + local)
    
    def _parse_class(self, class_name: str):
        import lode.models as _models
        cls = getattr(_models, class_name, None)
        if cls is None:
            raise KeyError(class_name)
        return cls

    def _parse_value(self, value):
        if value == 'Literal':
            return 'Literal'
        elif value is True or value is False:
            return value
        elif isinstance(value, str):
            import lode.models as _models
            cls = getattr(_models, value, None)
            if cls is not None:
                return cls
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
        fallback = self.config.get('mapper', {}).get('fallback_class')
        if fallback:
            import lode.models as _models
            return getattr(_models, fallback, Statement)
        return None
        
    # ========== HELPER METHODS ==========
    
    def get_classifier_predicates(self) -> set[URIRef]:
        """Predicati con 'inferred_class'"""
        return {
            pred for pred, cfg in self.get_property_mapping().items()
            if 'inferred_class' in cfg
        }
    
    def classify_by_predicate(self, uri: Node, graph: Graph) -> type | None:
            """Classifica guardando predicati.
            - inferred_class: tipo del soggetto (BNode restrictions, quantifiers, etc.) -> priorita' massima
              Se piu' predicati hanno inferred_class, vince la classe piu' specifica (issubclass).
            - target_classes con 1 elemento, nessun inferred_class, classify != false: 
              tipo implicito del soggetto (fallback)
            - target_classes con 2+ elementi: ambiguo, gestito dall'handler -> None
            - classify: false nel config: il predicato non classifica il soggetto,
              serve solo per i setters in phase3 (es. facet XSD)
            """
            fallback = None
            inferred = None
            for predicate, cfg in self.get_property_mapping().items():
                if (uri, predicate, None) in graph:
                    if 'inferred_class' in cfg:
                        candidate = cfg['inferred_class']
                        if inferred is None or issubclass(candidate, inferred):
                            inferred = candidate
                    elif fallback is None and len(cfg.get('target_classes', [])) == 1:
                        if cfg.get('classify', True):
                            fallback = cfg['target_classes'][0]
            return inferred if inferred else fallback
    
    def get_punning_priority(self):
        names = self.config.get('punning_priority', [])
        return [self._parse_class(n) for n in names]
    
    
# config_manager.py - aggiungi nei concrete managers

class OwlConfigManager(ConfigManager):
    
    @property
    def config_name(self) -> str:
        return 'owl'
    
    def create_logic(self, graph: Graph, cache: dict):
        from lode.reader.logic import OwlLogic
        return OwlLogic(graph, cache, self)
    
    def create_viewer(self, reader):
        from lode.viewer import OwlViewer
        return OwlViewer(reader)

class RdfConfigManager(ConfigManager):
    @property
    def config_name(self) -> str:
        return 'rdf'

    def create_logic(self, graph: Graph, cache: dict):
        from lode.reader.logic import RdfLogic
        return RdfLogic(graph, cache, self)

    def create_viewer(self, reader):
        from lode.viewer import BaseViewer
        return BaseViewer(reader)


class SkosConfigManager(ConfigManager):
    @property
    def config_name(self) -> str:
        return 'skos'

    def create_logic(self, graph: Graph, cache: dict):
        from lode.reader.logic import SkosLogic
        return SkosLogic(graph, cache, self)

    def create_viewer(self, reader):
        from lode.viewer import BaseViewer
        return BaseViewer(reader)

# ========== CONFIGURATIONS REGISTRY ==========

CONFIGURATION_REGISTRY = {
    'OWL': OwlConfigManager,
    'SKOS': SkosConfigManager,
    'RDF': RdfConfigManager
}


def get_configuration(configuration_name: str) -> ConfigManager:
    key = configuration_name.upper()
    if key not in CONFIGURATION_REGISTRY:
        available = ', '.join(CONFIGURATION_REGISTRY.keys())
        raise ValueError(f"Unknown configuration: '{configuration_name}'. Available: {available}")
    return CONFIGURATION_REGISTRY[key]()