# modules.py - RDF graph enrichment modules
"""Enrichment modules: load external documents and add them to the graph of the
documented ontology.

Three modules, activated by the Loader (one at a time; partial_import takes precedence):

  imported        direct owl:imports (depth 1)
  closure         transitive closure of owl:imports (depth N)
  partial_import  only the definitions of the external terms mentioned, taken from
                  their "home" ontology (1-hop dereferencing)

Two ways of loading an external document, shared by the modules:

  formal import    declared with owl:imports; its own owl:imports are followed
                   (_load_formal_import, used by imported and closure)
  informal import  a document reached by dereferencing a mentioned IRI; loaded alone,
                   its imports are not followed (_load_informal_import, used by
                   partial_import)

Provenance. The graph received is a ProvenanceGraph: one named graph per source
document, named after the ontology IRI declared in the document (owl:Ontology or
skos:ConceptScheme), falling back to the URL it was loaded from. Modules never build
contexts by hand: every document enters through ProvenanceGraph.add_document, so each
triple stays in the graph of the document that asserts it.

Every external document is loaded with a Loader without modules: no implicit
recursion, and the same security checks as the main document.

Contract: every apply_* modifies the graph in place and returns (graph, visited),
where visited is the set of sources loaded successfully.
"""
from rdflib import Graph, OWL, URIRef, BNode, RDF, RDFS, XSD
from urllib.parse import urldefrag
from typing import Optional

from lode.helpers.rdf import iri_namespace, iri_stem
from lode.reader.provenance_graph import ProvenanceGraph

# Core vocabularies: never treated as external terms to dereference.
_SKIP_NS = (str(RDF), str(RDFS), str(OWL), str(XSD))

# ----------------------------------------------------------
#  DOCUMENT LOADERS: formal / informal imports
# ----------------------------------------------------------

def _load_formal_import(graph: ProvenanceGraph, source: str, depth: int,
                        max_depth: Optional[int], visited: set) -> None:
    """Load a formally imported document (owl:imports) into its own named graph and
    follow its owl:imports, depth-first, down to max_depth (None = no limit).

    `visited` prevents cycles and documents imported by several ontologies: each one
    is loaded only once. An unreachable document does not stop loading: it is
    reported and skipped, together with its imports."""
    if source in visited:
        return
    if max_depth is not None and depth > max_depth:
        return

    visited.add(source)

    # Reuse the Loader for the whole load (content negotiation, formats, security).
    # Modules are not propagated: each imported ontology is loaded as-is, and the
    # recursion over imports is handled by this function.
    from lode.reader.loader import Loader  # local import: loader imports modules
    try:
        imported_loader = Loader(source)
    except Exception:
        print(f"  [formal import] could not load {source}")
        return

    imported_graph = imported_loader.get_graph()
    print(f"  [formal import] {len(imported_graph)} triples from {source}")
    # Context = ontology IRI declared in the document (fallback: source)
    graph.add_document(imported_graph, source)

    for nested_uri in list(imported_graph.objects(None, OWL.imports)):
        _load_formal_import(graph, str(nested_uri), depth + 1, max_depth, visited)


def _load_informal_import(source: str, target: ProvenanceGraph, visited: set, failed: set,
                          homes: dict) -> None:
    """Load a single document reached by dereferencing an IRI (informal import) into
    its own named graph of `target`. Its owl:imports are not followed.

    Records the outcome: success -> visited + homes[source] (name of its named graph);
    error -> failed (never retried)."""
    if source in visited or source in failed:
        return
    from lode.reader.loader import Loader  # local import: loader imports modules
    try:
        g = Loader(source).get_graph()
    except Exception as e:
        failed.add(source)
        print(f"  [informal import] could not load {source}: {type(e).__name__}: {e}")
        return
    visited.add(source)
    print(f"  [informal import] {len(g)} triples from {source}")
    homes[source] = target.add_document(g, source)

# ----------------------------------------------------------
#  IMPORTED / CLOSURE MODULES (formal imports)
# ----------------------------------------------------------

def _expand_formal_imports(graph: ProvenanceGraph, max_depth: Optional[int]):
    """Load every owl:imports of the graph, down to max_depth (None = no limit)."""
    visited: set = set()
    for uri in list(graph.objects(None, OWL.imports)):
        _load_formal_import(graph, str(uri), depth=1, max_depth=max_depth, visited=visited)
    return graph, visited


def apply_imported(graph: ProvenanceGraph):
    """Add the directly imported ontologies (depth 1)."""
    return _expand_formal_imports(graph, max_depth=1)


def apply_closure(graph: ProvenanceGraph):
    """Add the full transitive closure of owl:imports (depth N, max_depth=None)."""
    return _expand_formal_imports(graph, max_depth=None)

# ----------------------------------------------------------
#  PARTIAL IMPORT MODULE (informal imports)
# ----------------------------------------------------------
#
#  Boundary: an external term receives
#    - what the documented ontology says about it (with priority, per predicate), and
#    - the triples of its "home" graph, i.e. of the ontology that owns it.
#  Redefinitions found in third-party ontologies (formally imported ones included) are
#  NOT copied: they belong to the import closure, available through imported/closure.
#  If the home cannot be reached, the term receives no external definition.

def _namespace(term) -> str:
    """Namespace of an IRI, without the trailing separator:
    'http://ex.org/onto#T' -> 'http://ex.org/onto', 'http://ex.org/voc/t' -> 'http://ex.org/voc'."""
    s = str(term)
    return iri_stem(iri_namespace(term))


def _home(term, homes: dict):
    """Home graph of the term, or None. Criteria, in order:

    1. a loaded ontology whose IRI matches the term's namespace;
    2. a document downloaded from a URL in the same namespace (vocabularies without
       owl:Ontology, e.g. DC Terms: a single download for all its terms; or BIBO,
       whose namespace .../bibo/status matches the downloaded URL);
    3. the document obtained by dereferencing the term itself (ontology IRI that
       differs from the namespace, e.g. a versioned IRI or a purl redirect).

    `homes` maps every successfully downloaded source to the name of its named graph."""
    ns = _namespace(term)
    for ctx in homes.values():
        if iri_stem(ctx) == ns:
            return ctx
    for source, ctx in homes.items():
        if iri_stem(source) == ns or _namespace(source) == ns:
            return ctx
    return homes.get(urldefrag(str(term))[0])


def _namespace_failed(term, failed: set) -> bool:
    """True if a URL in the same namespace has already failed: avoids retrying, term
    by term, a vocabulary that answers with HTML or does not answer at all."""
    ns = _namespace(term)
    return any(iri_stem(f) == ns or _namespace(f) == ns for f in failed)


def apply_partial_import(graph: ProvenanceGraph):
    """Dereference (1 hop) the external IRIs mentioned and add ONLY their definition,
    taken from their home ontology (not the redefinitions in other ontologies)."""
    # 1. External terms: IRIs mentioned in the graph, excluding the import IRIs, the
    #    core vocabularies and the ontology's own terms.
    import_iris = set(graph.objects(None, OWL.imports))
    own = tuple(iri_stem(o) for o in graph.subjects(RDF.type, OWL.Ontology))
    mentioned = {t for triple in graph for t in triple if isinstance(t, URIRef)} - import_iris
    external = {t for t in mentioned
                if not str(t).startswith(_SKIP_NS) and not (own and str(t).startswith(own))}

    # 2. Load into a separate graph (one named graph per document). The owl:imports
    #    documents are loaded first, as informal imports (no recursion): they are often
    #    the home of the mentioned terms, so they are not downloaded again. Then one
    #    attempt per namespace not covered yet.
    fetched = ProvenanceGraph()
    visited, failed, homes = set(), set(), {}           # homes: source -> loaded ontology IRI
    for iri in import_iris:
        _load_informal_import(str(iri), fetched, visited, failed, homes)
    for term in external:
        if _home(term, homes) is None and not _namespace_failed(term, failed):
            _load_informal_import(urldefrag(str(term))[0], fetched, visited, failed, homes)

    # 3. Headers of external ontologies (owl:Ontology) are not terms to document.
    external -= set(fetched.subjects(RDF.type, OWL.Ontology))

    # 4. Priority to the documented ontology: predicates it already asserts on an
    #    external term (e.g. rdfs:label) are not copied again from the home.
    base_pairs = {(s, p) for s, p, _ in graph if s in external}

    # 5. Copy from the home graph only, into its own named graph.
    seen: set = set()
    for term in external:
        home = _home(term, homes)
        if home is not None:                            # home unreachable: no external definition
            _copy_description(fetched, term, graph, seen, skip=base_pairs, ctx=home)
    return graph, visited


def _copy_description(src: ProvenanceGraph, node, dst: ProvenanceGraph, seen: set,
                      skip=frozenset(), ctx=None) -> None:
    """Copy into `dst` the triples of `src` whose subject is `node`, in the same named graph.

    ctx   restricts the copy to a single graph (the home); None = all graphs.
    skip  (subject, predicate) pairs already populated in the base: not overwritten.
    Blank nodes (restrictions, lists) are copied in full and stay in their parent's
    context; `seen` prevents cycles and repeated copies."""
    if node in seen:
        return
    seen.add(node)
    for _, p, o, c in src.quads((node, None, None, ctx)):
        if (node, p) in skip:
            continue
        dst.graph(c).add((node, p, o))
        if isinstance(o, BNode):
            _copy_description(src, o, dst, seen, ctx=c)