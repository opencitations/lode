"""RDF helpers shared across LODE: IRIs and graphs.

Stateless utilities with no knowledge of the LODE pipeline (no models, no reader
phases, no network): they take IRIs or rdflib graphs and return plain values.
Pipeline types built on top of them (e.g. ProvenanceGraph) live with the reader.
"""
from pathlib import Path
from typing import Optional

from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF, SKOS

# ----------------------------------------------------------
#  IRIs
# ----------------------------------------------------------


def iri_namespace(iri) -> str:
    """Namespace of an IRI, trailing separator included.

    Splits on the last '#' if the IRI has one, otherwise on the last '/':
      'http://ex.org/onto#T' -> 'http://ex.org/onto#'
      'http://ex.org/voc/t'  -> 'http://ex.org/voc/'
    """
    s = str(iri)
    if "#" in s:
        return s.rsplit("#", 1)[0] + "#"
    return s.rsplit("/", 1)[0] + "/"


def iri_local_name(iri) -> str:
    """Local name of an IRI: the last segment after '#' and '/', trailing '/' ignored.
    Never contains '#' or '/', so it is safe as a file name or attribute name:
      'http://ex.org/onto#T' -> 'T'
      'http://ex.org/voc/t/' -> 't'
    """
    return str(iri).rstrip("/").split("#")[-1].split("/")[-1]


def iri_stem(iri) -> str:
    """IRI without trailing '/' or '#', to compare IRIs that differ only in the
    separator ('http://ex.org/onto#' == 'http://ex.org/onto' == 'http://ex.org/onto/')."""
    return str(iri).rstrip("/#")


def source_iri(source: str) -> str:
    """IRI of a load source: URLs as they are, local paths as absolute file: URIs."""
    if "://" in source:
        return source
    return Path(source).resolve().as_uri()


# ----------------------------------------------------------
#  Graphs
# ----------------------------------------------------------

# Node types that name a document: owl:Ontology first, then skos:ConceptScheme.
ONTOLOGY_TYPES = (OWL.Ontology, SKOS.ConceptScheme)


def declared_ontology_iri(g: Graph) -> Optional[URIRef]:
    """IRI of the ontology (or concept scheme) a document declares, or None.
    owl:Ontology wins over skos:ConceptScheme; blank nodes are ignored."""
    for t in ONTOLOGY_TYPES:
        for s in g.subjects(RDF.type, t):
            if isinstance(s, URIRef):
                return s
    return None

# Formats tried, in order, when the serialization is unknown. Turtle comes before N3
# (N3 is a superset and slower to fail); N-Triples is also valid Turtle.
PARSE_FORMATS = ("xml", "turtle", "json-ld", "nt", "n3")


def parse_any(data, preferred: Optional[str] = None) -> Optional[Graph]:
    """Parse RDF `data` (str or bytes) of unknown serialization.

    Tries `preferred` first (e.g. the format declared by the Content-Type), then
    PARSE_FORMATS in order. Returns the first graph that parses, or None if no
    format works: raising a meaningful error is left to the caller."""
    formats = ([preferred] if preferred else []) + [f for f in PARSE_FORMATS if f != preferred]
    for fmt in formats:
        g = Graph()
        try:
            g.parse(data=data, format=fmt)
            return g
        except Exception:
            continue
    return None