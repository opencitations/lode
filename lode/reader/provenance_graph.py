"""Named-graph container that keeps track of which ontology each triple comes from.

Used when imports or partial imports are enabled: every loaded document lives
in its own named graph, named after its ontology IRI, while the rest of the
pipeline keeps reading the union of all of them as if it were a single Graph.
"""
import os
from pathlib import Path
from urllib.parse import urlparse, quote
from rdflib import Dataset, Graph, URIRef, OWL, RDF
from rdflib.namespace import SKOS

_ONTOLOGY_TYPES = (OWL.Ontology, SKOS.ConceptScheme)
QUAD_FORMATS = frozenset({"trig", "nquads"})

class ProvenanceGraph(Dataset):
    """Dataset with one named graph per source ontology, presented to the pipeline as a Graph.

    default_union makes queries see the union of all named graphs, so readers
    and viewers need no knowledge of the provenance; only the code that cares
    about the origin of a triple asks for a specific named graph.
    """

    def __init__(self, **kw):
        """Create an empty dataset whose default graph is the union of its named graphs."""
        super().__init__(default_union=True, **kw)

    def __iter__(self):
        """Iterate over the plain triples of the union, like a Graph does."""
        return self.triples((None, None, None))

    def add_document(self, g: Graph, fallback: str) -> URIRef:
        """Copy the triples of `g` into the named graph of its ontology and return its IRI.

        The graph is named by `ontology_iri`; `fallback` (usually the source URL
        or path) is used when the document declares no ontology.
        """
        ctx =self.ontology_iri(g, fallback)
        self.graph(ctx).__iadd__(g)
        return ctx

    @staticmethod
    def ontology_iri(g: Graph, fallback: str) -> URIRef:
        """Return the IRI that names the graph of a document.

        Uses the first owl:Ontology or skos:ConceptScheme subject with an IRI.
        Without one, falls back to the source itself: http(s)/file URLs as they
        are, local paths as file:// URIs (a one-letter scheme is a Windows
        drive), anything else as a urn:lode:source: URN.
        """
        for t in _ONTOLOGY_TYPES:
            for s in g.subjects(RDF.type, t):
                if isinstance(s, URIRef):
                    return s
        parsed = urlparse(fallback)
        if parsed.scheme in {"http", "https", "file"}:
            return URIRef(fallback)
        if not parsed.scheme or len(parsed.scheme) == 1:
            return URIRef(Path(os.path.abspath(fallback)).as_uri())
        return URIRef(f"urn:lode:source:{quote(fallback, safe='')}")