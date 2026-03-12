# modules.py - Moduli di arricchimento del grafo RDF
from rdflib import Graph, OWL
from typing import Optional

def apply_imported(graph: Graph) -> Graph:
    """Arricchisce il grafo con le triple delle ontologie direttamente importate (profondita 1)."""
    return _expand_owl_imports(graph, max_depth=1)


def apply_closure(graph: Graph) -> Graph:
    """Arricchisce il grafo con la chiusura transitiva completa di owl:imports."""
    return _expand_owl_imports(graph, max_depth=None)

def _expand_owl_imports(graph: Graph, max_depth: Optional[int]) -> Graph:
    visited: set = set()
    for _, _, uri in graph.triples((None, OWL.imports, None)):
        _load_into(graph, str(uri), depth=1, max_depth=max_depth, visited=visited)
    return graph


def _load_into(graph: Graph, source: str, depth: int, max_depth: Optional[int], visited: set) -> None:
    if source in visited:
        return
    if max_depth is not None and depth > max_depth:
        return

    visited.add(source)

    # Riusa il Loader per tutto il caricamento (content negotiation, formati, ecc.)
    # I moduli non vengono propagati: ogni ontologia importata viene caricata as-is
    from lode.reader.loader import Loader
    try:
        imported_loader = Loader(source)
    except Exception:
        print(f"  [modules] Warning: could not load {source}")
        return

    imported_graph = imported_loader.get_graph()
    print(f"  [modules] Imported {len(imported_graph)} triples from {source}")
    graph += imported_graph

    for _, _, nested_uri in imported_graph.triples((None, OWL.imports, None)):
        _load_into(graph, str(nested_uri), depth + 1, max_depth, visited)