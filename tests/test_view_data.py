"""The contract between viewers and templates: its top level is fixed, and a template written from
it alone renders the three kinds of view."""
from pathlib import Path
from typing import Union, get_args, get_origin, get_type_hints, is_typeddict

import pytest
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from lode.viewer.view_data import ViewData

_EXAMPLES = Path(__file__).resolve().parent.parent / "docs" / "examples"


def test_top_level_keys():
    """Adding or removing a top-level key is a change of the contract, never an accident."""
    assert set(ViewData.__annotations__) == {"model", "toc", "entities", "focus", "error"}

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
            "deprecated": False, "imported": False, "visualizable": False, "parts": [], "nested": None}
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

WHOLE = {"model": _model(), "toc": _toc(), "entities": [_card({"broader": [_ANCHOR]})],
         "focus": None, "error": None}
WHOLE_WITHOUT_CARDS = {**WHOLE, "entities": []}
ONE = {"model": _model(), "toc": _toc(), "entities": [_card({"broader": [_PAGE, _EXTERNAL]})],
       "focus": "http://example.org/cat", "error": None}
ERROR = {"model": _model(), "toc": _toc(), "entities": [], "focus": "http://example.org/nope",
         "error": "Resource http://example.org/nope not found"}


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
    assert "<strong>Cat</strong>" in html
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

