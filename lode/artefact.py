"""Artefact: a semantic artefact read from a source, with everything extracted from it.

The Artefact is the hand-over between the reader and everything else: `lode.reader.read_into`
writes its fields once, and the viewers, the static builder and the API read only from it.
This keeps the Reader/Model/Viewer layers independent.
"""
from typing import Any, Callable, Optional

from rdflib import Graph, URIRef

from lode import profiles
from lode.helpers.rdf import iri_namespace
from lode.profiles import Profile
from lode.provenance_graph import ProvenanceGraph

# Prefix of the literal entries in the reader's entity cache. Literals are values,
# not entities, and must never be listed as such.
_LITERAL_PREFIX = "LITERAL::"


def _no_provenance(entity) -> Graph:
    """Return an empty subgraph: the provenance of an artefact built without a reader."""
    return Graph()


class Artefact:
    """A semantic artefact after extraction: its entities, its RDF graph and its provenance.

    `profile` is the format it was read as (None for an artefact built by hand). The reader
    sets the rest: `entities` is the entity cache shared by reference with `reader`, not a
    copy, and consumers must treat it as read-only; `reader` is the reader of the format after
    extraction, kept for inspection and never used by the viewers; `provenance` is a callable
    that returns the subgraph an entity was built from, computed only when asked for because
    most entities are never inspected. The annotations below are the contract with the
    reader, which writes these fields by name.
    """

    profile: Optional[Profile]
    entities: dict
    graph: Graph
    artefact_iri: Optional[URIRef]
    imported_uris: set
    warnings: list
    provenance: Callable[[Any], Graph]
    reader: Optional[Any]

    def __init__(self, source: str, *, imported: Optional[bool] = None,
                 closure: Optional[bool] = None, partial_import: Optional[bool] = None,
                 warnings: bool = False, source_name: Optional[str] = None):
        """Read `source` with the format of this class and keep what the extraction produces.

        Called on a format class (OwlOntology, SkosVocabulary or a plugin's own), never on
        Artefact itself: the class is how the format is chosen, and a caller that only has
        the name of a format uses lode.read(source, read_as). `source` is a local path or a
        public http(s) URL; the other arguments are those of `lode.reader.read_into`.
        Blocking: it may fetch remote documents.
        """
        profile = profiles.of(type(self))
        if profile is None:
            raise TypeError(f"{type(self).__name__} has no format: read with a format class "
                            "such as OwlOntology, or with lode.read(source, read_as)")
        # Local import on purpose: the reader pulls in the models and the reader of every
        # format, which `import lode` and the viewers do not need. It imports nothing from
        # this module, so there is no cycle.
        from lode.reader import read_into

        self._blank(profile)
        read_into(self, source, imported=imported, closure=closure,
                  partial_import=partial_import, warnings=warnings, source_name=source_name)

    @classmethod
    def from_parts(cls, entities: dict, graph: Graph, artefact_iri: Optional[URIRef] = None,
                   imported_uris: Optional[set] = None, warnings: Optional[list] = None,
                   profile: Optional[Profile] = None) -> "Artefact":
        """Build an artefact from data already in memory, without reading anything.

        For tests and for callers that have the graph and the entities by other means; the
        fields not given stay empty. Without `profile`, a format class gets its own.
        """
        artefact = cls.__new__(cls)
        artefact._blank(profile if profile is not None else profiles.of(cls))
        artefact.entities = entities
        artefact.graph = graph
        artefact.artefact_iri = artefact_iri
        artefact.imported_uris = imported_uris if imported_uris is not None else set()
        artefact.warnings = warnings if warnings is not None else []
        return artefact

    def _blank(self, profile: Optional[Profile]) -> None:
        """Give every field its empty value, so that the reader only has to overwrite them."""
        self.profile = profile
        self.entities = {}
        self.graph = Graph()
        self.artefact_iri = None
        self.imported_uris = set()
        self.warnings = []
        self.provenance = _no_provenance
        self.reader = None
        self._all = None
        self._viewer = None

    @property
    def read_as(self) -> Optional[str]:
        """Return the name of the format the artefact was read as, or None when unknown."""
        return self.profile.name if self.profile else None

    @property
    def artefact_base_iri(self) -> Optional[URIRef]:
        """Return the namespace of the artefact IRI, derived on demand, or None without an IRI."""
        return URIRef(iri_namespace(self.artefact_iri)) if self.artefact_iri else None

    @property
    def viewer(self):
        """Return the viewer of this artefact's format, created on first use and then reused.

        Its profile gives it its configuration, so the page data, the exports and the
        templates all come from here; an artefact without a profile gets the generic viewer.
        """
        if self._viewer is None:
            # Local import: the viewers pull in the YAML configuration, which reading does
            # not need. The viewer package imports nothing from this module, so no cycle.
            from lode.viewer import get_viewer

            self._viewer = get_viewer(self)
        return self._viewer

    def get_entities(self, cls: Optional[type] = None) -> list:
        """Return the extracted entities, optionally only those of one model class.

        `cls` is a model class (Concept, Relation): its subclasses are included, as
        with isinstance, so Resource gives every entity. Literals are not entities
        and are never returned. Passing anything that is not a class, such as the
        class name, raises TypeError. The full list is built once and reused, because
        a static build asks for it on every page: `entities` must not change after the
        artefact is built.
        """
        if self._all is None:
            self._all = [
                entity
                for key, group in self.entities.items()
                if not (isinstance(key, str) and key.startswith(_LITERAL_PREFIX))
                for entity in (group if isinstance(group, set) else [group])
            ]
        if cls is None:
            return list(self._all)
        return [i for i in self._all if isinstance(i, cls)]

    def get_entities_by_iri(self, iri: str) -> Optional[set]:
        """Return the entities registered under an IRI, or None when it is unknown.

        More than one entity comes back for a punned IRI (same IRI used as a
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
            return self.graph.graph(self.artefact_iri)
        return self.graph

    def with_provenance(self, sub: Graph) -> ProvenanceGraph:
        """Return `sub` as quads, each triple in the named graph(s) it comes from.

        With modules active the graphs are the ones of the source ontologies;
        without, every triple goes in the graph of the loaded artefact. It lives
        here and not in a viewer because it only needs the graph: the viewer just
        asks for the result.
        """
        ds = self.graph
        out = ProvenanceGraph()
        for prefix, ns in ds.namespaces():
            out.bind(prefix, ns)
        if isinstance(ds, ProvenanceGraph):
            for s, p, o in sub:
                for *_, c in ds.quads((s, p, o, None)):
                    out.graph(c).add((s, p, o))
        else:
            main = out.graph(self.artefact_iri)
            for t in sub:
                main.add(t)
        return out
