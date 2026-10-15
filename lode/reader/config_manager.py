"""Configuration managers: bind each artefact type to its YAML mapper, logic and viewer.

The mapping from RDF/OWL/SKOS constructs to the model lives in the YAML files
under reader/config, not in Python: a manager loads base.yaml, merges the
type-specific file on top and exposes the result to the logic classes.
"""

import yaml
from pathlib import Path
from abc import ABC, abstractmethod
from rdflib import URIRef, Graph, Node
from lode.models import *

class ConfigManager(ABC):
    """Strategy driven by a single merged YAML configuration.

    Subclasses only say which config file they use and how to build their
    logic and viewer; parsing and caching of the mappings is shared here.
    """

    def __init__(self):
        """Load and merge the YAML configuration; mappings are parsed lazily."""
        self.config = self._load_config()
        self._type_mapping_cache = None
        self._property_mapping_cache = None
    
    @abstractmethod
    def create_logic(self, graph: Graph, cache: dict):
        """Factory method: build the logic specific to this artefact type."""
        pass

    @property
    @abstractmethod
    def config_name(self) -> str:
        """Name of the type-specific config file: 'owl' | 'skos' | 'rdf'."""
        pass
    
    def _load_config(self) -> dict:
        """Read base.yaml and the type-specific YAML, and return them deep-merged.

        Files are looked up next to this module so the config ships inside the wheel.
        """
        config_dir = Path(__file__).parent / 'config'
        
        with open(config_dir / 'base.yaml') as f:
            base = yaml.safe_load(f)
        
        with open(config_dir / f'{self.config_name}.yaml') as f:
            specific = yaml.safe_load(f)
        
        return self._deep_merge(base, specific)
    
    def _deep_merge(self, base: dict, override: dict) -> dict:
        """Merge `override` into a copy of `base`, recursing into nested dicts.

        The 'name' and 'inherits' keys only describe the file and are not merged.
        """
        result = base.copy()
        for key, value in override.items():
            if key in ('name', 'inherits'):
                continue
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result
    
    @abstractmethod
    def create_viewer(self, reader):
        """Factory method: build the viewer specific to this artefact type."""
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
        """Resolve a model class name from the YAML into the class itself.

        Raises KeyError for an unknown name, so a typo in the config fails loudly.
        """
        import lode.models as _models
        cls = getattr(_models, class_name, None)
        if cls is None:
            raise KeyError(class_name)
        return cls

    def _parse_value(self, value):
        """Convert a setter argument from the YAML: model class names become classes.

        'Literal', booleans and strings that are not model classes are kept as they are.
        """
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
        """Parse one mapper entry: resolve class names (and setter arguments) into classes."""
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
        """Return the class given to resources no mapping recognised, or None if unset.

        An unknown class name in the config falls back to Statement.
        """
        fallback = self.config.get('mapper', {}).get('fallback_class')
        if fallback:
            import lode.models as _models
            return getattr(_models, fallback, Statement)
        return None
        
    # ========== HELPER METHODS ==========
    
    def get_classifier_predicates(self) -> set[URIRef]:
        """Predicates whose config declares an 'inferred_class'."""
        return {
            pred for pred, cfg in self.get_property_mapping().items()
            if 'inferred_class' in cfg
        }
    
    def classify_by_predicate(self, uri: Node, graph: Graph) -> type | None:
            """Classify a subject by looking at the mapped predicates it uses.
            - inferred_class: type of the subject (BNode restrictions, quantifiers, etc.) -> highest priority.
              If several predicates have an inferred_class, the most specific class wins (issubclass).
            - target_classes with 1 element, no inferred_class, classify != false: 
              implicit type of the subject (fallback)
            - target_classes with 2+ elements: ambiguous, left to the handler -> None
            - classify: false in the config: the predicate does not classify the subject,
              it is only used by the setters in phase3 (e.g. XSD facets)
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
        """Return the classes in the order that decides which one wins on a punned IRI."""
        names = self.config.get('punning_priority', [])
        return [self._parse_class(n) for n in names]
    
    
# ========== CONCRETE MANAGERS ==========

class OwlConfigManager(ConfigManager):
    """Configuration for OWL artefacts."""
    
    @property
    def config_name(self) -> str:
        """Use owl.yaml on top of base.yaml."""
        return 'owl'

    def create_logic(self, graph: Graph, cache: dict):
        """Build the OWL logic."""
        from lode.reader.logic import OwlLogic
        return OwlLogic(graph, cache, self)
    
    def create_viewer(self, reader):
        """Build the OWL viewer."""
        from lode.viewer import OwlViewer
        return OwlViewer(reader)

class RdfConfigManager(ConfigManager):
    """Configuration for RDF/RDFS artefacts."""

    @property
    def config_name(self) -> str:
        """Use rdf.yaml on top of base.yaml."""
        return 'rdf'

    def create_logic(self, graph: Graph, cache: dict):
        """Build the RDF logic."""
        from lode.reader.logic import RdfLogic
        return RdfLogic(graph, cache, self)

    def create_viewer(self, reader):
        """Build the RDF viewer."""
        from lode.viewer import RdfViewer
        return RdfViewer(reader)


class SkosConfigManager(ConfigManager):
    """Configuration for SKOS artefacts."""

    @property
    def config_name(self) -> str:
        """Use skos.yaml on top of base.yaml."""
        return 'skos'

    def create_logic(self, graph: Graph, cache: dict):
        """Build the SKOS logic."""
        from lode.reader.logic import SkosLogic
        return SkosLogic(graph, cache, self)

    def create_viewer(self, reader):
        """Build the SKOS viewer."""
        from lode.viewer import SkosViewer
        return SkosViewer(reader)

# ========== CONFIGURATIONS REGISTRY ==========

CONFIGURATION_REGISTRY = {
    'OWL': OwlConfigManager,
    'SKOS': SkosConfigManager,
    'RDF': RdfConfigManager
}


def get_configuration(configuration_name: str) -> ConfigManager:
    """Return a new manager for the given artefact type (case-insensitive).

    Raises ValueError listing the available types when the name is unknown.
    """
    key = configuration_name.upper()
    if key not in CONFIGURATION_REGISTRY:
        available = ', '.join(CONFIGURATION_REGISTRY.keys())
        raise ValueError(f"Unknown configuration: '{configuration_name}'. Available: {available}")
    return CONFIGURATION_REGISTRY[key]()