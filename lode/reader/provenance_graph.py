from pathlib import Path
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
        if "://" not in fallback:
            fallback = Path(fallback).resolve().as_uri()
        return URIRef(fallback)