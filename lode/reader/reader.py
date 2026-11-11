"""Generic orchestrator that turns a loaded RDF graph into model instances.

The Reader sits between the Loader (parsing) and the Viewer (rendering): it
picks the configuration for the artefact type and runs the logic phases, so
CLI, API and viewers never depend on parsing details.
"""
from lode.reader.loader import Loader
from lode.reader.config_manager import get_configuration
from lode.models import *
from typing import Optional
from rdflib import Graph, URIRef
from lode.artefact import Artefact, Provenance
from lode.provenance_graph import ProvenanceGraph

import logging
logger = logging.getLogger(__name__)

def _value_key(value) -> str:
    """Comparable form of a model value: lexical form for literals, IRI otherwise."""
    get_value = getattr(value, "get_has_value", None)
    if get_value is not None and get_value() is not None:
        return str(get_value())
    get_id = getattr(value, "get_has_identifier", None)
    if get_id is not None and get_id():
        return str(get_id())
    return str(value)

class Reader:
    """
    Generic RDF Reader/Orchestrator.
    
    Responsibilities:
    - Calls the loader to parse input RDF (via rdflib)
    - Orchestrates Python model population phases
    - Delegates specific logics for extraction and population to other modules
    """
    
    def __init__(self):
        """Create an empty Reader; call load_instances() to populate it."""
        self._instance_cache = {}
        self._logic = None  # specialised logic (OWL, SKOS, RDF/RDFS)
        self._graph = None
        self._configuration = None
        self._imported_uris = set()   # needed to get the model before imported/closure models
        self._ontology_iri = None

    def get_warnings(self) -> list:
        """Return the warnings collected while reading, or [] when they were not requested."""
        if not getattr(self, '_warnings_enabled', False):
            return []
        if self._logic and hasattr(self._logic, '_warnings'):
            return self._logic._warnings
        return []

    def _prioritize_documented_values(self) -> None:
        """Reorder every multi-valued field so that values asserted by the documented
        ontology (main named graph) come before those from imported or home graphs.

        Needed because the graph does not preserve insertion order across named graphs.
        The sort is stable: within each group the original order is kept."""
        main = self._graph.graph(self._ontology_iri)
        for uri, instances in self._instance_cache.items():
            if not isinstance(uri, URIRef):
                continue
            local = {str(o) for o in main.objects(uri, None)}
            
            if not local:
                continue
            for instance in instances:
                for value in vars(instance).values():
                    if isinstance(value, list) and len(value) > 1:
                        value.sort(key=lambda v: _value_key(v) not in local)


    def load_instances(self, graph_path: str, read_as: str, imported=None, closure=None, partial_import=None,
                       warnings=False, source_name: Optional[str] = None):
        """Load an artefact and extract its model instances.

        `read_as` selects the configuration (owl, rdf, skos). Imports, closure and
        partial_import are forwarded to the Loader; `warnings` turns on the reader
        warnings. `source_name` names the artefact when `graph_path` is only a local
        copy of it. Blocking: it may fetch remote documents.
        """
        self._warnings_enabled = warnings

        # 1. Generic parsing
        loader = Loader(graph_path, imported=imported, closure=closure, partial_import=partial_import,
                        source_name=source_name)
        self._graph = loader.get_graph()
        self._ontology_iri = loader.ontology_iri
        
        # 1.5 saves the imported/closure uris to be reused in viewer so the model metadata are not overwritten 
        self._imported_uris = getattr(loader, "imported_uris", set())

        # 2. Select the configuration for the artefact type
        self._configuration = get_configuration(read_as)
        
        # 3. Create the specialised logic
        self._logic = self._configuration.create_logic(self._graph, self._instance_cache)

        # 4. Run the extraction phases
        self._extract_instances()

        # 5. Documented ontology first (only when a module is active)
        if isinstance(self._graph, ProvenanceGraph):
            self._prioritize_documented_values()
    
    def get_triples_for_instance(self, instance):
        """Return the RDF triples that produced a model instance (empty set if unknown)."""
        if self._logic and hasattr(self._logic, '_triples_map'):
            return self._logic._triples_map.get(instance, set())
        return set()

    def get_all_triples_map(self) -> dict:
        """Return the full instance -> triples map (empty dict if no logic is loaded)."""
        if self._logic and hasattr(self._logic, '_triples_map'):
            return self._logic._triples_map
        return {}

    def get_main_graph(self) -> Graph:
        """Return the triples of the loaded artefact only (see Artefact.main_graph)."""
        return self.get_artefact().main_graph()

    def get_provenance_subgraph(self, instance):
        """Return the rdflib.Graph subgraph that provenanced `instance`."""
        if self._logic and hasattr(self._logic, 'build_provenance_subgraph'):
            return self._logic.build_provenance_subgraph(instance)
        return Graph()
    
     
    # function reused by the api to push instances
    def to_dict(self, instance) -> dict:
        """Serialize a model instance into a JSON-friendly dict, including its RDF triples.

        Empty values are left out of "properties"; every value is converted to a string.
        """
        result = {
            "instance": str(instance),
            "type": type(instance).__name__,
            "uri": str(instance.has_identifier) if instance.has_identifier else None,
            "properties": {},
            "rdf_triples": []
        }
        
        # Serialize the instance properties
        for attr_name in instance.__dict__.keys():
            value = getattr(instance, attr_name)
            # removes empty values from the properties
            if value is not None and not (isinstance(value, (list, set)) and not value):
                result["properties"][attr_name] = str(value)
        
        # Add the associated RDF triples
        triples = self.get_triples_for_instance(instance)
        for s, p, o in triples:
            triple_dict = {
                "subject": str(s),
                "predicate": str(p),
                "object": str(o)
            }
            result["rdf_triples"].append(triple_dict)
        
        return result

    # def _serialize_value(self, value):
    #     """Convert a value into a JSON-friendly form, recursing into lists and sets."""
    #     if isinstance(value, (str, int, float, bool)):
    #         return value
    #     elif isinstance(value, (list, set)):
    #         return [self._serialize_value(v) for v in value]
    #     elif hasattr(value, 'uri'):
    #         return str(value.uri)
    #     else:
    #         return str(value)
        
    def get_artefact(self) -> Artefact:
        """Return what a viewer needs from this read, with no reference to the reader.
        Entities are shared with the reader's cache, not copied. Provenance stays
        lazy. It needs no configuration, so it also works on a reader whose graph
        was set without a full load (the API spool relies on this).
        """
        return Artefact(
            entities=self._instance_cache,
            graph=self._graph,
            ontology_iri=self._ontology_iri,
            imported_uris=self._imported_uris,
            warnings=self.get_warnings(),
            provenance=Provenance(getattr(self._logic, "build_provenance_subgraph", None)),
            read_as=self._configuration.config_name if self._configuration else None,
        )
    
    def clear_cache(self):
        """Drop every cached instance, in the Reader and in its logic."""
        self._instance_cache.clear()
        if self._logic:
            self._logic.clear_cache()
    
    # ==================== EXTRACTION (ORCHESTRATION) ====================
    
    def _extract_instances(self):
        """Run the extraction phases in order, delegating each one to the logic.

        Phases 1-4 depend on the artefact type; fallback, statements and
        namespaces are shared. Post-pipeline warning checks run only when enabled.
        """        
        # PHASES 1-4: delegated to the specific logic
        self._logic.phase1_classify_from_predicates()
        self._logic.phase2_create_from_types()
        self._logic.phase3_populate_properties()
        self._logic.phase4_process_group_axioms()
        
        # PHASE 5: fallback (shared)
        self._logic.phase5_fallback()
        
        # PHASE 6: statements
        self._logic.phase6_create_statements()

        # FASE 7: Namespaces 
        self._logic.populate_namespaces()

        # Post-pipeline warning checks
        if self._warnings_enabled:
            from lode.reader.warnings import owl_warnings
            owl_warnings.run_post_checks(self._logic)

            if self._logic._warnings:
                logger.warning("%d reader warnings", len(self._logic._warnings))
                # details only at DEBUG: the viewer words them with display names
                # for popups, report and CLI, so raw model names would be confusing
                for w in self._logic._warnings:
                    logger.debug("[%s] %s", w['code'], w['message'])
    
    def _phase5_fallback(self):
        """Fallback per risorse non categorizzate (comune)"""
        
        fallback_class = self._configuration.get_fallback_class()
        if not fallback_class:
            logger.warning("No fallback class configured")
            return
        
        all_subjects = set(self._graph.subjects())
        fallback_count = 0
        
        for subj in all_subjects:
            if subj not in self._instance_cache:
                self._logic.get_or_create(subj, fallback_class)
                fallback_count += 1