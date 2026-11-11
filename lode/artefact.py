"""Artefact: the hand-over between the Reader and the viewers.

The Reader builds an Artefact once the extraction is done; viewers, the static
builder and the API read only from it, never from the Reader or its logic. This
keeps the Reader/Model/Viewer layers independent.
"""
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from rdflib import Graph, URIRef

from lode.provenance_graph import ProvenanceGraph

# Prefix of the literal entries in the reader's instance cache. Literals are values,
# not entities, and must never be listed as such.
_LITERAL_PREFIX = "LITERAL::"


class Provenance:
    """Gives, on demand, the RDF triples an entity was built from.

    The subgraph is computed only when asked for: a documentation can hold
    thousands of entities and most of them are never inspected, so nothing is
    precomputed.
    """

    def __init__(self, build: Optional[Callable[[Any], Graph]] = None):
        """Wrap the callable that builds the subgraph; None means no provenance."""
        self._build = build

    def for_instance(self, instance) -> Graph:
        """Return the subgraph that produced `instance`, empty when unknown."""
        return self._build(instance) if self._build else Graph()


@dataclass
class Artefact:
    """A semantic artefact after extraction: its entities, its RDF graph and its provenance.

    `entities` is the Reader's instance cache shared by reference, not a copy:
    consumers must treat it as read-only. `read_as` names the format the artefact
    was read as ("owl", "skos", "rdf"): the viewer layer uses it to pick the right
    viewer, so that the reader never has to know the viewers. None means unknown.
    """

    entities: dict
    graph: Graph
    ontology_iri: Optional[URIRef] = None
    imported_uris: set = field(default_factory=set)
    warnings: list = field(default_factory=list)
    provenance: Provenance = field(default_factory=Provenance)
    read_as: Optional[str] = None

    def instances(self, class_name: Optional[str] = None) -> list:
        """Return the extracted instances, optionally only those of one model class.

        `class_name` is the exact name of a model class ("Concept", "Relation"):
        subclasses are not matched, so the result is the same grouping the viewers
        use. Literals are not entities and are never returned. An unknown name
        gives an empty list.
        """
        found = []
        for key, group in self.entities.items():
            if isinstance(key, str) and key.startswith(_LITERAL_PREFIX):
                continue
            for instance in (group if isinstance(group, set) else [group]):
                if class_name is None or type(instance).__name__ == class_name:
                    found.append(instance)
        return found

    def get_instance(self, iri: str) -> Optional[set]:
        """Return the instances registered under an IRI, or None when it is unknown.

        More than one instance comes back for a punned IRI (same IRI used as a
        class and as an individual). The lookup scans the keys because they are
        rdflib terms, which do not compare equal to a plain string.
        """
        for key, group in self.entities.items():
            if str(key) == iri:
                return group
        return None

    def main_graph(self) -> Graph:
        """Return the triples of the loaded artefact only, as a plain Graph view.

        Imported and partially imported ontologies are left out: this is what
        exports and content negotiation must return. Without modules it is the
        loaded graph itself.
        """
        if isinstance(self.graph, ProvenanceGraph):
            return self.graph.graph(self.ontology_iri)
        return self.graph
