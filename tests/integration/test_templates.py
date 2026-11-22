"""Contract-based templates: each partial is rendered on its own, with StrictUndefined.

A key read outside the contract makes the render fail, so the templates cannot
drift from docs/usage/viewer_contract.md.
"""
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined
import lode 
from lode import SkosVocabulary
from lode.viewer import get_viewer

_TEMPLATES = Path(__file__).resolve().parents[2] / "lode" / "templates"
_TYPES = {"Concept": {"singular": "Concept", "plural": "Concepts", "abbreviation": "c"}}


def _value(**fields) -> dict:
    """A contract Value with every key present, overridden by `fields`."""
    base = {"text": "", "iri": None, "href": None, "kind": None, "language": None, "type": None,
            "deprecated": False, "imported": False, "visualize": None, "parts": [], "nested": None}
    return {**base, **fields}


def _render(v: dict) -> str:
    """Render the `value` macro for one Value, like a page that imports it with context."""
    env = Environment(loader=FileSystemLoader(str(_TEMPLATES)), undefined=StrictUndefined, autoescape=True)
    template = env.from_string('{% from "_value.html" import value with context %}{{ value(v) }}')
    return template.render(v=v, types=_TYPES)


def test_an_internal_link_stays_in_the_page():
    """An anchor link has no target and carries the type badge."""
    html = _render(_value(text="Cat", iri="http://e.org/cat", href="#id_cat", kind="anchor", type="Concept"))
    assert 'href="#id_cat"' in html and "_blank" not in html
    assert 'title="Concept"' in html


def test_an_external_link_opens_elsewhere():
    """An external link opens in a new tab and is marked."""
    html = _render(_value(text="x", iri="http://o.org/x", href="http://o.org/x", kind="external"))
    assert 'target="_blank"' in html and "external-ref" in html


def test_a_deprecated_value_is_struck_through():
    """The deprecated flag reaches the markup."""
    assert "text-decoration-line-through" in _render(_value(text="old", deprecated=True))


def test_a_literal_shows_its_language():
    """A string is left to the markdown renderer and keeps its language badge."""
    html = _render(_value(text="a *cat*", type="str", language="en"))
    assert 'data-md="a *cat*"' in html and ">en</sup>" in html


def test_a_class_expression_renders_its_parts():
    """Each part of an expression is rendered, links included."""
    parts = [_value(text="knows some "), _value(text="Cat", iri="http://e.org/cat", href="#id_cat", kind="anchor")]
    html = _render(_value(text="knows some Cat", parts=parts))
    assert 'class="restriction-block"' in html


def test_a_nested_statement_lists_its_pairs():
    """The main pair and the siblings of an annotated statement are all shown."""
    pair = lambda p, t: {"predicate": p, "value": _value(text=t)}
    nested = {"main": pair("source", "doc"), "siblings": [pair("note", "n1")]}
    html = _render(_value(nested=nested))
    assert "source:" in html and "note:" in html

def _entity(label: str, href=None) -> dict:
    """A contract TocEntry; `href` is None for an entity that is not published."""
    return {"iri": f"http://e.org/{label}", "type": "Concept", "label": label,
            "anchor": f"id_{label}", "href": href, "kind": "anchor" if href else None}


def _toc() -> list:
    """One section with a published entity and one without a page."""
    return [{"id": "concepts", "type": "Concept", "label": "Concepts",
             "entries": [_entity("cat", "#id_cat"), _entity("dog")], "tree": []}]


def _render_toc(call: str) -> str:
    """Render a macro of _toc.html: `call` is the Jinja expression, e.g. "sidebar(toc)"."""
    env = Environment(loader=FileSystemLoader(str(_TEMPLATES)), undefined=StrictUndefined, autoescape=True)
    template = env.from_string('{% from "_toc.html" import sidebar, contents %}{{ ' + call + ' }}')
    return template.render(toc=_toc(), namespaces=[{"prefix": "ex", "uri": "http://e.org/"}])


def test_the_sidebar_lists_every_entity():
    """A section shows its label and size; an entity with a link is a link."""
    html = _render_toc("sidebar(toc)")
    assert 'href="#concepts"' in html and ">2</span>" in html
    assert '<a href="#id_cat"' in html


def test_an_entity_without_a_page_is_plain_text():
    """No href, no anchor: the label is shown but not linked."""
    html = _render_toc("sidebar(toc)")
    assert "dog" in html and 'title="http://e.org/dog"' not in html


def test_the_contents_counts_namespaces():
    """The table of contents ends with the namespace declarations, when there are any."""
    html = _render_toc("contents(toc, namespaces)")
    assert 'href="#concepts"' in html and 'href="#namespaces"' in html
    assert "Table of Contents" not in _render_toc("contents([], namespaces)")

def _card(**fields) -> dict:
    """A contract Card with every key present, overridden by `fields`."""
    base = {"iri": "http://e.org/cat", "type": "Concept", "label": "Cat", "anchor": "id_cat",
            "href": "resources/cat.html", "kind": "page", "deprecated": False, "relations": {},
            "statements": {}, "characteristics": [], "provenance": []}
    return {**base, **fields}


def _render_card(entity: dict, focus=None) -> str:
    """Render the `card` macro of _card.html over the example toc."""
    env = Environment(loader=FileSystemLoader(str(_TEMPLATES)), undefined=StrictUndefined, autoescape=True)
    template = env.from_string('{% from "_card.html" import card with context %}{{ card(e, toc, focus) }}')
    return template.render(e=entity, toc=_toc(), focus=focus, types=_TYPES)


def test_a_card_shows_its_header():
    """Anchor, label, type badge, deprecation and the way back to the section."""
    html = _render_card(_card(deprecated=True))
    assert 'id="id_cat"' in html and "Cat" in html and 'title="Concept"' in html
    assert "DEPRECATED" in html and 'href="#concepts"' in html


def test_a_card_of_a_single_resource_has_no_way_back():
    """The back links make sense only in the page of the whole artefact."""
    assert "back to" not in _render_card(_card(), focus="http://e.org/cat")


def test_a_card_puts_the_comment_first_and_hides_the_identifier():
    """Comment goes in the description; the identifier is not shown at all."""
    relations = {"Comment": [_value(text="A cat.")], "Identifier": [_value(text="secret-id")],
                 "broader": [_value(text="Animal", href="#id_animal", kind="anchor")]}
    html = _render_card(_card(relations=relations))
    assert "A cat." in html and "secret-id" not in html
    assert html.index("A cat.") < html.index('href="#id_animal"')


def test_a_card_shows_characteristics_statements_and_provenance():
    """The three optional blocks appear only when the entity has them."""
    bare = _render_card(_card())
    assert "Characteristics" not in bare and "statement" not in bare and "provenance" not in bare
    full = _render_card(_card(characteristics=["is symmetric"], statements={"note": [_value(text="n1")]},
                              provenance=[{"label": "Turtle", "code": "ex:cat a ex:Cat ."}]))
    assert "is symmetric" in full and "note" in full and "ex:cat a ex:Cat ." in full

_SKOS = """
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
<http://example.org/s#scheme> a skos:ConceptScheme ; skos:prefLabel "Animals"@en .
<http://example.org/s#animal> a skos:Concept ; skos:prefLabel "Animal"@en ;
    skos:inScheme <http://example.org/s#scheme> .
<http://example.org/s#cat> a skos:Concept ; skos:prefLabel "Cat"@en ; skos:broader <http://example.org/s#animal> ;
    skos:inScheme <http://example.org/s#scheme> .
"""
_CAT = "http://example.org/s#cat"


def _viewer(tmp_path):
    """A viewer over the small SKOS artefact above."""
    path = tmp_path / "source.ttl"
    path.write_text(_SKOS, encoding="utf-8")
    return get_viewer(SkosVocabulary(str(path)))


def _render_page(data: dict) -> str:
    """Render page.html like an adapter does: StrictUndefined, and a url_for global for the assets."""
    env = Environment(loader=FileSystemLoader(str(_TEMPLATES)), undefined=StrictUndefined, autoescape=True)
    env.globals["url_for"] = lambda name, path="": f"static/{path}"
    return env.get_template("page.html").render(**data)


def test_the_page_has_a_card_for_every_entity(tmp_path):
    """The whole artefact: each entity once, each section, the namespaces."""
    data = _viewer(tmp_path).view()
    html = _render_page(data)
    assert data["cards"]
    for entity in data["cards"]:
        assert html.count(f'id="{entity["anchor"]}"') == 1
    for section in data["toc"]:
        assert f'id="{section["id"]}"' in html


def test_the_page_of_a_resource_shows_only_that_resource(tmp_path):
    """A focused page has its card and a way back, and no table of contents of its own."""
    data = _viewer(tmp_path).view(resource_uri=_CAT)
    data["model"]["href"] = "index.html"
    html = _render_page(data)
    assert len(data["cards"]) == 1 and 'href="index.html"' in html
    assert 'id="toc"' not in html


def test_the_page_shows_an_error(tmp_path):
    """A resource that does not exist is reported, not hidden."""
    data = _viewer(tmp_path).view(resource_uri="http://example.org/s#nope")
    assert data["error"] in _render_page(data)
