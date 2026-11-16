"""The contract between a viewer and a template: the data a viewer hands over, and nothing else.

A viewer returns a plain dictionary (`ViewData`); a template only reads it. The classes below
describe that dictionary and are not used at runtime. They are the reference for whoever
writes a template, and tests check that the viewers keep to them.

Rules that hold everywhere:
  - every key listed is always present: an empty list, an empty dictionary or None says "nothing",
    never a missing key;
  - labels are already in the requested language, with the fallback applied;
  - lists keep a meaningful order (entities by label, relations in display order);
  - nothing here depends on how the data will be drawn: there is no HTML, no CSS class.
"""
from typing import Dict, List, Optional, TypedDict


class Namespace(TypedDict):
    """A prefix declared by the artefact."""

    prefix: str
    uri: str


class Serialization(TypedDict):
    """A format the whole artefact, or one resource, can be exported to."""

    label: str                   # "Turtle"
    fmt: str                     # the rdflib format name, "turtle"
    ext: str                     # file extension, "ttl"
    mime: str                    # media type, "text/turtle"
    href: Optional[str]          # where to download it; None when it cannot be offered

class ReaderWarning(TypedDict):
    """A problem the reader found while reading the source."""

    code: str
    message: str                 # already worded with the display names of the viewer


class NestedPair(TypedDict):
    """One predicate and its value, inside an annotation on an annotation."""

    predicate: str
    value: "Value"


class Nested(TypedDict):
    """The annotations carried by a value that is itself a statement."""

    main: NestedPair
    siblings: List[NestedPair]


class Value(TypedDict):
    """One value shown on a card or in the header: text, possibly a link, possibly structured."""

    text: Optional[str]          # what is displayed
    iri: Optional[str]           # the resource the value stands for, if it is one
    href: Optional[str]          # where a click goes; None when the value is not a link
    kind: Optional[str]          # "anchor" (same page), "page" (a page of this documentation),
    #                              "external" (outside it); None when there is no link
    language: Optional[str]      # language tag of a literal
    type: Optional[str]          # model class name: "Literal", "Concept", "PropertyChain", ...
    deprecated: bool
    imported: bool               # defined in an imported module, not in this artefact
    visualize: Optional[str]     # header only: the address that opens LODE on this ontology; None otherwise
    parts: List["Value"]         # components of a class expression or of a property chain; [] otherwise
    nested: Optional[Nested]


class Provenance(TypedDict):
    """The triples an entity was built from, serialized in one format."""

    label: str                   # the format, "TriG"
    code: str                    # the serialization


class Entity(TypedDict):
    """One entity with all its data: the content of a card."""

    iri: str
    type: str                    # model class name: "Concept", "Relation", ...
    label: Optional[str]
    anchor: str                  # a stable HTML id for this entity
    href: Optional[str]          # the page of this entity; None when it has none
    kind: Optional[str]          # as in Value
    deprecated: bool
    relations: Dict[str, List[Value]]    # display name -> values
    statements: Dict[str, List[Value]]   # predicate label -> values
    characteristics: List[str]           # for example ["is symmetric"]
    provenance: List[Provenance]         # [] when unknown


class TocEntity(TypedDict):
    """One entity reduced to what a list needs: no relations, no statements."""

    iri: str
    type: str
    label: Optional[str]
    anchor: str
    href: Optional[str]
    kind: Optional[str]

class TocSection(TypedDict):
    """The entities of one class, as a section of the table of contents."""

    id: str                      # a stable HTML id for the section
    type: str                    # model class name
    label: str                   # display name of the group, "Classes"
    entities: List[TocEntity]

class Model(TypedDict):
    """The documented artefact: its header, and what concerns it as a whole."""

    iri: Optional[str]           # None when the source declares no ontology or concept scheme
    label: Optional[str]
    metadata: Dict[str, List[Value]]     # display name -> values: title, description, version, ...
    namespaces: List[Namespace]
    serializations: List[Serialization]
    warnings: List[ReaderWarning]        # [] unless the artefact was read asking for them
    href: Optional[str]          # the page of the whole artefact; where "back to everything" goes

class TypeLabel(TypedDict):
    """How a type is called and abbreviated."""

    singular: str                # "Class"
    plural: str                  # "Classes"
    abbreviation: str            # "c": the short badge shown next to a name

class ViewData(TypedDict):
    """What a viewer hands to a template. Every key is always present."""

    model: Model
    toc: List[TocSection]        # the navigation of the whole artefact, for the sidebar and the contents list; [] on the page of one resource
    types: Dict[str, TypeLabel]  # how each type is called, by the class name that `type` carries
    entities: List[Entity]       # what the main part shows: all the cards, one, or none
    focus: Optional[str]         # the IRI that was asked for; None for the whole artefact
    error: Optional[str]         # a message when the request cannot be answered; None otherwise

def new_value(**fields) -> Value:
    """Return a Value with every key present, overridden by `fields`.

    The viewers start from this and fill in what they know, so that no Value ever lacks a key
    a template reads (a template never has to ask whether a key exists).
    """
    value: Value = {"text": None, "iri": None, "href": None, "kind": None, "language": None,
                    "type": None, "deprecated": False, "imported": False, "visualize": None,
                    "parts": [], "nested": None}
    value.update(fields)
    return value
