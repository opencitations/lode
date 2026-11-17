"""Reader: runs the extraction pipeline and writes what it extracts on an Artefact.

The Reader sits between the document loader and the viewers: it loads the graph, takes the
configuration and the logic of the artefact's format, runs the logic phases and hands the
result over by filling the Artefact it is given, so CLI, API and viewers never depend on
parsing details. It keeps no state and imports nothing from lode.artefact: it only sets the
attributes the Artefact declares.
"""
import logging
from typing import Optional

from rdflib import URIRef

from lode.provenance_graph import ProvenanceGraph
from lode.reader import modules
from lode.reader.config_manager import ConfigManager
from lode.reader.loader import load_document

logger = logging.getLogger(__name__)


# ==========================================================================
# 1. ENTRY POINT
# ==========================================================================
def read_into(artefact, source: str, *, imported=None, closure=None, partial_import=None,
              warnings: bool = False, source_name: Optional[str] = None) -> None:
    """Load `source` and fill `artefact` with what the extraction pipeline produces.

    The format comes from `artefact.profile`. Sets graph, artefact_iri, imported_uris,
    entities, logic, warnings and provenance on `artefact` and returns nothing: the
    Artefact is the only place where the result lives. `imported`, `closure` and
    `partial_import` are forwarded to `load_graph`; `warnings` turns on the reader warnings;
    `source_name` names the artefact when `source` is only a local copy of it. Blocking:
    it may fetch remote documents.
    """
    graph, artefact_iri, imported_uris = load_graph(
        source, imported=imported, closure=closure,
        partial_import=partial_import, source_name=source_name)
    artefact.graph = graph
    artefact.artefact_iri = artefact_iri
    artefact.imported_uris = imported_uris
    artefact.entities = {}

    configuration = ConfigManager(artefact.profile)
    logic = artefact.profile.make_logic(artefact.graph, artefact.entities, configuration)
    _extract_instances(logic, artefact.profile, warnings)

    artefact.logic = logic
    artefact.warnings = logic.warnings if warnings else []
    artefact.provenance = logic.build_provenance_subgraph
    # Documented semantic artefact first (only when a module is active)
    if isinstance(artefact.graph, ProvenanceGraph):
        _prioritize_documented_values(artefact)


# ==========================================================================
# 2. LOADING
# ==========================================================================
def load_graph(source: str, *, imported=None, closure=None, partial_import=None,
               source_name: Optional[str] = None):
    """Load the graph of an artefact: its document, named, with the requested modules applied.

    Returns (graph, artefact_iri, imported_uris). The graph is a plain Graph, or a
    ProvenanceGraph (one named graph per source document) when `imported`, `closure` or
    `partial_import` is requested; in both cases `artefact_iri` names the loaded artefact.
    `source_name` names the artefact when `source` is only a local copy of it (for example
    a cached download): it names the graph if the ontology declares no IRI. `imported_uris`
    holds the IRIs of the imported documents, so that the viewer can keep the metadata of
    the original model.
    """
    graph = load_document(source)
    name = source_name or source
    if not (imported or closure or partial_import):
        # No modules: the graph stays plain, only its name is needed so that the
        # provenance of an entity can still be written as a quad.
        return graph, ProvenanceGraph.artefact_iri(graph, name), set()

    raw, graph = graph, ProvenanceGraph()
    artefact_iri = graph.add_document(raw, name)
    graph, imported_uris = modules.apply(graph, imported=imported, closure=closure,
                                         partial_import=partial_import)
    return graph, artefact_iri, imported_uris


# ==========================================================================
# 3. EXTRACTION
# ==========================================================================
def _extract_instances(logic, profile, warnings_enabled: bool) -> None:
    """Run the extraction phases in order, delegating each one to the logic.

    Phases 1-5 depend on the artefact type; statements and namespaces are shared.
    The post-extraction checks of the profile run only when warnings are enabled.
    """
    logic.phase1_classify_from_predicates()
    logic.phase2_create_from_types()
    logic.phase3_populate_properties()
    logic.phase4_process_group_axioms()
    logic.phase5_fallback()
    logic.phase6_create_statements()
    logic.populate_namespaces()

    if warnings_enabled:
        profile.run_post_checks(logic)

        if logic.warnings:
            logger.warning("%d reader warnings", len(logic.warnings))
            # details only at DEBUG: the viewer words them with display names
            # for popups, report and CLI, so raw model names would be confusing
            for w in logic.warnings:
                logger.debug("[%s] %s", w['code'], w['message'])


def _value_key(value) -> str:
    """Comparable form of a model value: lexical form for literals, IRI otherwise."""
    get_value = getattr(value, "get_has_value", None)
    if get_value is not None and get_value() is not None:
        return str(get_value())
    get_id = getattr(value, "get_has_identifier", None)
    if get_id is not None and get_id():
        return str(get_id())
    return str(value)


def _prioritize_documented_values(artefact) -> None:
    """Reorder every multi-valued field so that values asserted by the documented
    semantic artefact (main named graph) come before those from imported or home graphs.

    Needed because the graph does not preserve insertion order across named graphs.
    The sort is stable: within each group the original order is kept.
    """
    main = artefact.graph.graph(artefact.artefact_iri)
    for uri, instances in artefact.entities.items():
        if not isinstance(uri, URIRef):
            continue
        local = {str(o) for o in main.objects(uri, None)}
        if not local:
            continue
        for instance in instances:
            for value in vars(instance).values():
                if isinstance(value, list) and len(value) > 1:
                    value.sort(key=lambda v: _value_key(v) not in local)
