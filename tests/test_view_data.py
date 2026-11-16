"""The contract between viewers and templates: its top level is fixed, and a template written from
it alone renders the three kinds of view."""
from pathlib import Path
from typing import Union, get_args, get_origin, get_type_hints, is_typeddict

import pytest
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from lode.viewer.view_data import ViewData
import lode
from lode.viewer import get_viewer
from lode.helpers.links import Links

_EXAMPLES = Path(__file__).resolve().parent.parent / "docs" / "examples"


def test_top_level_keys():
    """Adding or removing a top-level key is a change of the contract, never an accident."""
    assert set(ViewData.__annotations__) == {"model", "toc", "entities", "focus", "error", "types"}

"""A template written from the contract alone renders the three kinds of view."""
from pathlib import Path
from typing import Union, get_args, get_origin, get_type_hints, is_typeddict


def _check(hint, value, path):
    """Fail if `value` does not fit the type `hint`: a TypedDict has exactly its keys.

    The check goes down into lists and dictionaries, so a key that the contract does not
    declare, or one that is missing, is found wherever it sits.
    """
    if is_typeddict(hint):
        fields = get_type_hints(hint)
        assert set(value) == set(fields), f"{path}: keys {sorted(value)}, expected {sorted(fields)}"
        for key, sub in fields.items():
            _check(sub, value[key], f"{path}.{key}")
        return
    origin, args = get_origin(hint), get_args(hint)
    if origin is list:
        for i, item in enumerate(value):
            _check(args[0], item, f"{path}[{i}]")
    elif origin is dict:
        for key, item in value.items():
            _check(args[1], item, f"{path}[{key!r}]")
    elif origin is Union and type(None) in args and value is not None:
        _check(next(a for a in args if a is not type(None)), value, path)


# --- the examples: a vocabulary Animal <- Cat <- Kitten ---------------------------------
def _value(**fields):
    """A Value with every key present, the unsaid ones neutral."""
    base = {"text": None, "iri": None, "href": None, "kind": None, "language": None, "type": None,
            "deprecated": False, "imported": False, "visualize": None, "parts": [], "nested": None}
    return {**base, **fields}


def _short(label):
    """The fields a navigation entry has."""
    return {"iri": f"http://example.org/{label.lower()}", "type": "Concept", "label": label,
            "anchor": f"id_{label.lower()}", "href": f"resources/{label.lower()}.html", "kind": "page"}


def _toc():
    """Two sections: the concepts with their tree, and an empty collections one."""
    kitten = {**_short("Kitten"), "children": []}
    cat = {**_short("Cat"), "children": [kitten]}
    animal = {**_short("Animal"), "children": [cat]}
    return [
        {"id": "concepts", "type": "Concept", "label": "Concepts",
         "entities": [_short("Animal"), _short("Cat"), _short("Kitten")], "tree": [animal]},
        {"id": "collections", "type": "Collection", "label": "Collections", "entities": [], "tree": []},
    ]


def _card(relations):
    """The card of Cat, with the given relations."""
    return {**_short("Cat"), "deprecated": False, "relations": relations, "statements": {},
            "characteristics": [], "provenance": [{"label": "TriG", "code": "ex:cat a skos:Concept ."}]}


def _model():
    """The header of the vocabulary."""
    return {"iri": "http://example.org/s#scheme", "label": "Animals", "href": "index.html",
            "metadata": {"title": [_value(text="Animals", language="en", type="Literal")]},
            "namespaces": [{"prefix": "ex", "uri": "http://example.org/"}],
            "serializations": [{"label": "Turtle", "fmt": "turtle", "ext": "ttl",
                                "mime": "text/turtle", "href": "index.ttl"}],
            "warnings": []}


_ANCHOR = _value(text="Animal", iri="http://example.org/animal", href="#id_animal", kind="anchor", type="Concept")
_PAGE = _value(text="Kitten", iri="http://example.org/kitten", href="resources/kitten.html", kind="page", type="Concept")
_EXTERNAL = _value(text="Elsewhere", iri="http://other.org/x", href="http://other.org/x", kind="external")

_TYPES = {"Concept": {"singular": "Concept", "plural": "Concepts", "abbreviation": "c"}}
WHOLE = {"model": _model(), "toc": _toc(), "entities": [_card({"broader": [_ANCHOR]})],
         "focus": None, "error": None, "types": _TYPES}
WHOLE_WITHOUT_CARDS = {**WHOLE, "entities": []}
ONE = {"model": _model(), "toc": _toc(), "entities": [_card({"broader": [_PAGE, _EXTERNAL]})],
       "focus": "http://example.org/cat", "error": None, "types": _TYPES}
ERROR = {"model": _model(), "toc": _toc(), "entities": [], "focus": "http://example.org/nope",
         "error": "Resource http://example.org/nope not found", "types": _TYPES}

@pytest.fixture
def render():
    """Render the example template: any key outside the contract is an error."""
    env = Environment(loader=FileSystemLoader(str(_EXAMPLES)), undefined=StrictUndefined, autoescape=True)

    def run(data):
        _check(ViewData, data, "ViewData")
        return env.get_template("minimal.html").render(**data)

    return run


def test_the_whole_artefact(render):
    """Header, navigation with its tree, a card, and the way to download it."""
    html = render(WHOLE)
    assert "Animals" in html and "Concepts (3)" in html
    assert 'href="resources/kitten.html"' in html          # a navigation entry, from the tree
    assert 'id="id_cat"' in html and 'href="#id_animal"' in html
    assert 'href="index.ttl"' in html


def test_the_whole_artefact_without_cards(render):
    """A viewer that shows each entity on its own page gives no cards: the page is still complete."""
    html = render(WHOLE_WITHOUT_CARDS)
    assert "Concepts (3)" in html and "<article" not in html


def test_one_resource(render):
    """The current entry is marked, links tell their kind, and there is a way back."""
    html = render(ONE)
    assert "<h2>Cat" in html
    assert 'href="resources/kitten.html"' in html
    assert 'href="http://other.org/x"' in html and 'target="_blank"' in html
    assert 'href="index.html"' in html                     # model.href: back to everything


def test_an_error(render):
    """The message is shown and there is no card."""
    html = render(ERROR)
    assert "not found" in html and "<article" not in html


def test_a_key_outside_the_contract_is_refused(render):
    """The check is real: an extra key in the data is found."""
    with pytest.raises(AssertionError, match="keys"):
        render({**WHOLE, "sections": []})

_SOURCES = {
    "owl": ("""
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix ex: <http://example.org/o#> .
<http://example.org/o> a owl:Ontology ; rdfs:label "Pets"@en .
ex:Animal a owl:Class ; rdfs:label "Animal"@en .
ex:Cat a owl:Class ; rdfs:label "Cat"@en ;
    rdfs:subClassOf ex:Animal , [ a owl:Restriction ; owl:onProperty ex:eats ; owl:someValuesFrom ex:Animal ] .
ex:eats a owl:ObjectProperty ; rdfs:label "eats"@en .
ex:felix a owl:NamedIndividual , ex:Cat ; rdfs:label "Felix"@en .
""", "http://example.org/o#Cat"),
    "skos": ("""
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix ex: <http://example.org/s#> .
ex:scheme a skos:ConceptScheme ; skos:prefLabel "Animals"@en .
ex:animal a skos:Concept ; skos:prefLabel "Animal"@en ; skos:inScheme ex:scheme ; skos:topConceptOf ex:scheme .
ex:cat a skos:Concept ; skos:prefLabel "Cat"@en ; skos:definition "A small feline"@en ;
    skos:broader ex:animal ; skos:inScheme ex:scheme .
ex:kitten a skos:Concept ; skos:prefLabel "Kitten"@en ; skos:broader ex:cat ; skos:inScheme ex:scheme .
""", "http://example.org/s#cat")
}


@pytest.fixture(params=sorted(_SOURCES))
def viewer_and_iri(request, tmp_path):
    """A viewer over a small artefact of each format, and the IRI of one of its entities."""
    text, iri = _SOURCES[request.param]
    path = tmp_path / "source.ttl"
    path.write_text(text, encoding="utf-8")
    return get_viewer(lode.read(str(path), request.param)), iri


def test_the_viewer_produces_the_contract(viewer_and_iri):
    """The whole artefact and one resource both have exactly the keys the contract declares."""
    viewer, iri = viewer_and_iri
    _check(ViewData, viewer.view(), "ViewData")
    _check(ViewData, viewer.view(resource_uri=iri), "ViewData")


def test_a_real_page_renders_with_the_example_template(viewer_and_iri, render):
    """The template written from the contract alone shows what the viewer produced."""
    viewer, iri = viewer_and_iri
    assert "Cat" in render(viewer.view(resource_uri=iri))

def test_the_page_of_one_resource_has_no_navigation(viewer_and_iri):
    """A page about one resource carries only its card: the navigation belongs to the whole artefact.

    Otherwise every page of a static site would list every other page.
    """
    viewer, iri = viewer_and_iri
    assert viewer.view()["toc"]
    assert viewer.view(resource_uri=iri)["toc"] == []

def test_focus_and_error(viewer_and_iri):
    """`focus` is what was asked for; an unknown resource gives a message and no card."""
    viewer, iri = viewer_and_iri
    assert viewer.view()["focus"] is None
    assert viewer.view(resource_uri=iri)["focus"] == iri
    missing = viewer.view(resource_uri="http://example.org/nope")
    assert missing["error"] and missing["entities"] == []

class _TestLinks(Links):
    """Addresses that say what they stand for, so a test can tell where each came from."""

    def resource(self, iri):
        return f"page:{iri}"

    def export(self, ext, iri=None):
        return f"export:{ext}:{iri or 'all'}"

    def home(self):
        return "home"

    def visualize(self, iri): 
        return f"visualize:{iri}"


def _records(node):
    """Every dictionary of the data that has both an `href` and a `kind`: a link."""
    if isinstance(node, dict):
        if "href" in node and "kind" in node:
            yield node
        for value in node.values():
            yield from _records(value)
    elif isinstance(node, list):
        for item in node:
            yield from _records(item)


def test_every_link_follows_the_rules(viewer_and_iri):
    """Whatever the view, a link is an anchor, a page, an external address, or plain text."""
    viewer, iri = viewer_and_iri
    for data in (viewer.view(links=_TestLinks()), viewer.view(resource_uri=iri, links=_TestLinks())):
        for link in _records(data):
            if link["kind"] is None:
                assert link["href"] is None
            elif link["kind"] == "anchor":
                assert link["href"].startswith("#")
            elif link["kind"] == "page":
                assert link["href"].startswith("page:")
            else:
                assert link["kind"] == "external" and link["href"] == link["iri"]


def test_the_whole_artefact_links_its_cards_by_anchor(viewer_and_iri):
    """An entry of the toc whose card is on the page points to that card."""
    viewer, _ = viewer_and_iri
    data = viewer.view(links=_TestLinks())
    anchors = {e["iri"]: e["anchor"] for e in data["entities"]}
    assert anchors
    for section in data["toc"]:
        for entry in section["entities"]:
            if entry["iri"] in anchors:
                assert (entry["kind"], entry["href"]) == ("anchor", "#" + anchors[entry["iri"]])


def test_the_model_and_its_exports(viewer_and_iri):
    """The model points home, and each serialization to the artefact or to the resource in focus."""
    viewer, iri = viewer_and_iri
    whole = viewer.view(links=_TestLinks())["model"]
    one = viewer.view(resource_uri=iri, links=_TestLinks())["model"]
    assert whole["href"] == "home"
    assert all(s["href"] == f"export:{s['ext']}:all" for s in whole["serializations"])
    assert all(s["href"] == f"export:{s['ext']}:{iri}" for s in one["serializations"])


def test_without_links_nothing_points_to_a_page(viewer_and_iri):
    """With no resolver a link to this documentation is plain text; external ones still work."""
    viewer, iri = viewer_and_iri
    for link in _records(viewer.view(resource_uri=iri)):
        assert link["kind"] != "page"
    assert viewer.view()["model"]["href"] is None


def test_the_library_shortcut(viewer_and_iri):
    """lode.view gives what the viewer gives."""
    viewer, iri = viewer_and_iri
    assert lode.view(viewer.artefact, resource=iri) == viewer.view(resource_uri=iri)

def test_types_name_every_section(viewer_and_iri):
    """Every type of the navigation can be named: the template never meets a type it cannot label."""
    viewer, _ = viewer_and_iri
    data = viewer.view()
    for section in data["toc"]:
        assert section["type"] in data["types"]
        assert data["types"][section["type"]]["abbreviation"]


def test_the_header_can_open_other_ontologies(viewer_and_iri):
    """`visualize` is filled only from the resolver, and only for header values that point to an ontology."""
    viewer, _ = viewer_and_iri
    for values in viewer.view(links=_TestLinks())["model"]["metadata"].values():
        for v in values:
            assert v["visualize"] in (None, f"visualize:{v['iri']}")
    for values in viewer.view()["model"]["metadata"].values():
        assert all(v["visualize"] is None for v in values)




#### links fallbacks

class _NoPages(Links):
    """A resolver that knows no page of the documentation."""

    def resource(self, iri):
        return None


def test_a_resource_without_a_page_is_a_link_to_the_outside(viewer_and_iri):
    """With no address for a resource, the link goes to its IRI and counts as external."""
    viewer, iri = viewer_and_iri
    for link in _records(viewer.view(resource_uri=iri, links=_NoPages())):
        assert link["kind"] != "page"
        if link["kind"] == "external":
            assert link["href"] == link["iri"]





#### LINKS 

"""The addresses the web service and the static site give to the viewer."""
from rdflib import Graph

from lode.api import _WebLinks
from lode.builder import _StaticLinks

_CAT = "http://example.org/o#Cat"
_QS = "read_as=skos&url=http%3A%2F%2Fx"

_GRAPH = Graph()
_GRAPH.bind("ex", "http://example.org/o#")
_KEPT = {_CAT, "http://example.org/o#"}      # a resource and a bare namespace


def test_web_links():
    links = _WebLinks(_QS)
    assert links.resource(_CAT) == f"/extract?{_QS}&resource=http%3A//example.org/o%23Cat"
    assert links.export("ttl") == f"/extract?{_QS}&format=ttl"
    assert links.export("ttl", _CAT) == f"/extract?{_QS}&resource=http%3A//example.org/o%23Cat&format=ttl"
    assert links.home() == f"/extract?{_QS}"


def test_static_links_from_the_index():
    links = _StaticLinks(_GRAPH, _KEPT, "pets")
    assert links.resource(_CAT) == "resources/ex/Cat.html"
    assert links.resource("http://example.org/o#Dog") is None      # it gets no page
    assert links.resource("http://example.org/o#") == "pets.html"   # a namespace: the whole artefact
    assert links.export("ttl") == "pets.ttl"
    assert links.export("ttl", _CAT) == "resources/ex/Cat.ttl"
    assert links.home() == "pets.html"


def test_static_links_from_the_page_of_a_resource():
    links = _StaticLinks(_GRAPH, _KEPT, "pets", focus=_CAT)
    assert links.resource(_CAT) == "../ex/Cat.html"
    assert links.export("ttl", _CAT) == "../ex/Cat.ttl"
    assert links.export("ttl") == "../../pets.ttl"
    assert links.home() == "../../pets.html"

def test_web_links_open_another_ontology():
    links = _WebLinks(_QS, read_as="owl", lang="it")
    assert links.visualize("http://x.org/onto") == "/extract?read_as=owl&url=http%3A%2F%2Fx.org%2Fonto&lang=it"
    assert _WebLinks(_QS).visualize("http://x.org/onto") is None


def test_a_static_site_cannot_open_another_ontology():
    assert _StaticLinks(_GRAPH, _KEPT, "pets").visualize("http://x.org/onto") is None

