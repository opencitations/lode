"""Offline regressions for datatype facets in the reader and generated HTML."""
from html.parser import HTMLParser

import pytest
from rdflib import Graph, Namespace
from rdflib.compare import isomorphic
from rdflib.namespace import XSD

from lode.builder import build_html
from lode.models import Datatype, DatatypeRestriction
from lode.reader import Reader
from lode.viewer import get_viewer


EX = Namespace("http://example.org/ranges#")
CASES = [
    ("actOrder", "integer", "[ xsd:minInclusive 1 ] [ xsd:maxInclusive 3 ]",
     "integer[>= 1, <= 3]"),
    ("stageOrder", "integer", "[ xsd:minInclusive 1 ] [ xsd:maxInclusive 17 ]",
     "integer[>= 1, <= 17]"),
    ("fitScore", "integer", "[ xsd:minInclusive -1 ] [ xsd:maxInclusive 4 ]",
     "integer[>= -1, <= 4]"),
    ("reversed", "integer", "[ xsd:maxInclusive 4 ] [ xsd:minInclusive -1 ]",
     "integer[<= 4, >= -1]"),
    ("exclusive", "decimal", "[ xsd:minExclusive 0.5 ] [ xsd:maxExclusive 9.5 ]",
     "decimal[> 0.5, < 9.5]"),
    ("zero", "integer", "[ xsd:minInclusive 0 ]", "integer[>= 0]"),
    ("pattern", "string", '[ xsd:pattern "[0-9]+" ] [ xsd:minLength 1 ]',
     "string[pattern [0-9]+, minLength 1]"),
]


@pytest.fixture
def range_reader(tmp_path):
    declarations = "\n".join(
        f"ex:{name} a owl:DatatypeProperty ; rdfs:range [ a rdfs:Datatype ; "
        f"owl:onDatatype xsd:{datatype} ; owl:withRestrictions ( {facets} ) ] ."
        for name, datatype, facets, _ in CASES
    )
    path = tmp_path / "ranges.ttl"
    path.write_text("""
        @prefix ex: <http://example.org/ranges#> .
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
        <http://example.org/ranges> a owl:Ontology .
    """ + declarations, encoding="utf-8")
    reader = Reader()
    reader.load_instances(str(path), "owl")
    return reader


@pytest.mark.parametrize("name,datatype,expected",
                         [(name, datatype, expected) for name, datatype, _, expected in CASES],
                         ids=[case[0] for case in CASES])
def test_range_preserves_datatype_and_every_facet(range_reader, name, datatype,
                                                expected):
    viewer = get_viewer(range_reader.get_artefact())
    data = viewer.get_view_data(str(EX[name]))
    rendered = data["entities"][0]["relations"]["range"][0]

    assert rendered["text"] == expected
    assert rendered["parts"][0]["link"] == str(XSD[datatype])

    restrictions = {
        instance for instances in range_reader._instance_cache.values()
        for instance in instances if isinstance(instance, DatatypeRestriction)
    }
    assert len(restrictions) == len(CASES)
    for restriction in restrictions:
        assert isinstance(restriction.get_applies_on_concept(), Datatype)


class _RestrictionText(HTMLParser):
    """Read visible restriction blocks without matching the hidden RDF snippets."""

    def __init__(self, html):
        super().__init__()
        self.depth = 0
        self.blocks = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == "div":
            if self.depth:
                self.depth += 1
            elif "restriction-block" in dict(attrs).get("class", "").split():
                self.depth = 1
                self.blocks.append("")

    def handle_endtag(self, tag):
        if tag == "div" and self.depth:
            self.depth -= 1

    def handle_data(self, text):
        if self.depth:
            self.blocks[-1] += text


def test_static_index_and_resource_pages_show_complete_ranges(range_reader, tmp_path):
    out = tmp_path / "site"
    build_html(get_viewer(range_reader.get_artefact()), out)

    def compact(text):
        return "".join(text.split())

    index = _RestrictionText((out / "index.html").read_text(encoding="utf-8"))
    for name, _, _, expected in CASES:
        page = out / "resources" / "ex" / f"{name}.html"
        resource = _RestrictionText(page.read_text(encoding="utf-8"))
        assert compact(expected) in [compact(block) for block in index.blocks]
        assert compact(expected) in [compact(block) for block in resource.blocks]

    assert isomorphic(Graph().parse(out / "index.ttl"), range_reader.get_main_graph())
