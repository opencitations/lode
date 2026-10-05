import os
from pathlib import Path
from urllib.parse import urlparse, quote
from rdflib import Dataset, Graph, URIRef, OWL, RDF
from rdflib.namespace import SKOS

_ONTOLOGY_TYPES = (OWL.Ontology, SKOS.ConceptScheme)
QUAD_FORMATS = frozenset({"trig", "nquads"})

class ProvenanceGraph(Dataset):
    """Dataset a named graph (uno per ontologia sorgente) che si presenta al pipeline come un Graph."""

    def __init__(self, **kw):
        super().__init__(default_union=True, **kw)

    def __iter__(self):
        return self.triples((None, None, None))

    def add_document(self, g: Graph, fallback: str) -> URIRef:
        ctx = self.ontology_iri(g, fallback)
        self.graph(ctx).__iadd__(g)
        return ctx

    @staticmethod
    def ontology_iri(g: Graph, fallback: str) -> URIRef:
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