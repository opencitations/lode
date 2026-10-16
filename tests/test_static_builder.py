"""Static-build integrity tests over the SPAR corpus (ontologies_spar.json).

Covers the features added to builder.py / base_viewer.py:
  - internal/external classification (_is_internal / _has_local_triples)
  - per-prefix folder layout (_rel_slug), no local-name collisions
  - file generation filter: entities with local triples get HTML + serializations
  - INVARIANT: every generated HTML resource has its .ttl/.rdf/.n3 siblings
  - internal links resolve to existing files (no 404 in the static tree)
"""
import json
import re
from pathlib import Path

import pytest
from rdflib import Graph

from lode.reader import Reader
from lode.exceptions import ArtefactValidationError
from lode.builder import build_html, _rel_slug, _prefix_map
from rdflib import URIRef

ONTOLOGIES_PATH = Path(__file__).parent / "ontologies_spar.json"
URIS = [e["uri"] for e in json.loads(ONTOLOGIES_PATH.read_text(encoding="utf-8"))["uris"]]

from lode.viewer.base_viewer import SERIALIZATION_FORMATS

_EXTS = [f["ext"] for f in SERIALIZATION_FORMATS]


def _load(uri):
    r = Reader()
    r.load_instances(uri, "owl")
    return r.get_viewer(), r


@pytest.fixture(scope="module", params=URIS, ids=lambda u: u.rstrip("/").split("/")[-1])
def built(request, tmp_path_factory):
    """Load one ontology and build it into a temp dir. Reused by all tests."""
    uri = request.param
    try:
        viewer, reader = _load(uri)
    except Exception as e:
        pytest.skip(f"load failed for {uri}: {e}")
    out = tmp_path_factory.mktemp("docs")
    build_html(viewer, out, reader=reader)
    return {"uri": uri, "viewer": viewer, "reader": reader, "out": out}


# --- build structure ---

def test_index_and_ontology_serializations(built):
    out = built["out"]
    assert (out / "index.html").exists()
    for ext in _EXTS:
        assert (out / f"index.{ext}").exists(), f"missing index.{ext}"


def test_resources_folder_created(built):
    assert (built["out"] / "resources").exists()


def test_index_export_base(built):
    """Index header must export the whole graph (index.*), not a single resource."""
    html = (built["out"] / "index.html").read_text(encoding="utf-8")
    assert "index.ttl" in html


def test_renamed_artefact(built, tmp_path):
    """A renamed artefact renames root page and RDF; resource pages link back to it."""
    out = tmp_path / "site"
    build_html(built["viewer"], out, reader=built["reader"], artefact_name="home")
    assert (out / "home.html").exists() and (out / "home.ttl").exists()
    assert not (out / "index.html").exists()
    page = next((out / "resources").rglob("*.html"))
    assert "../../home.html" in page.read_text(encoding="utf-8")


@pytest.mark.parametrize("bad", ["../x", "a/b", "..", "x.html "])
def test_artefact_name_rejected(bad, tmp_path):
    """Names with path parts or odd characters are rejected before any file is written."""
    with pytest.raises(ArtefactValidationError):
        build_html(None, tmp_path / "s", artefact_name=bad)


# --- INVARIANT: every HTML resource has all three serializations ---

def test_every_html_resource_has_all_formats(built):
    res = built["out"] / "resources"
    html_files = list(res.rglob("*.html"))
    assert html_files, f"no resource pages generated for {built['uri']}"
    missing = []
    for html in html_files:
        for ext in _EXTS:
            sibling = html.with_suffix(f".{ext}")
            if not sibling.exists():
                missing.append(str(sibling.relative_to(built["out"])))
    assert not missing, "missing serializations:\n" + "\n".join(missing)


def test_serializations_parse(built):
    """Every generated .ttl must be valid Turtle (non-empty, reparseable)."""
    for ttl in (built["out"] / "resources").rglob("*.ttl"):
        Graph().parse(str(ttl), format="turtle")


# --- internal/external classification ---

def test_local_triples_implies_internal(built):
    """The real invariant: a ToC entity that is subject of triples is internal."""
    viewer = built["viewer"]
    checked = 0
    for i in viewer.get_toc_instances():
        uri = i.get_has_identifier()
        if uri and viewer._has_local_triples(uri):
            assert viewer._is_internal(uri), f"has triples but external: {uri}"
            checked += 1
    assert checked, f"no internal entities for {built['uri']}"

def test_object_only_has_no_page(built):
    """A resource neither native to the ontology nor subject of any local triple
    (i.e. it appears only as an object) must not get its own page. Same
    materialization criterion as the builder, so test and builder cannot diverge."""
    viewer = built["viewer"]
    res = built["out"] / "resources"
    graph = viewer.reader._graph
    ontology_ns = viewer._get_ontology_ns()

    for i in viewer.get_toc_instances():
        uri = i.get_has_identifier()
        if not uri:
            continue
        materialized = str(uri).startswith(ontology_ns) or viewer._has_local_triples(uri)
        if not materialized:
            slug = _rel_slug(uri, graph)
            assert not (res / f"{slug}.html").exists(), f"page for non-materialized: {uri}"

# --- slug: no collisions across generated pages ---

def test_no_slug_collisions(built):
    """Every generated HTML path is unique (per-prefix layout guarantees it)."""
    res = built["out"] / "resources"
    paths = [p.relative_to(res).as_posix() for p in res.rglob("*.html")]
    assert len(paths) == len(set(paths)), "duplicate resource paths generated"


# --- link integrity: no broken internal links in the static tree ---

def test_internal_links_resolve(built):
    """Every relative .html link in a generated page must point to an existing file."""
    out = built["out"]
    broken = []
    for html in (out / "resources").rglob("*.html"):
        text = html.read_text(encoding="utf-8")
        for href in re.findall(r'href=["\']?([^"\'>\s]+\.html)', text):
            if href.startswith("http") or href.startswith("#"):
                continue
            target = (html.parent / href).resolve()
            if not target.exists():
                broken.append(f"{html.name} -> {href}")
    assert not broken, "broken internal links:\n" + "\n".join(broken)


# --- warnings report ---

_WARN_TTL = """
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix : <http://ex.org/> .
<http://ex.org/> a owl:Ontology .
:A a owl:Class ; rdfs:subClassOf [ a owl:Restriction ; owl:onProperty :p ;
    owl:someValuesFrom :B ; owl:allValuesFrom :B ] .
"""


def _build_warn_ttl(tmp_path, warnings):
    """Load the malformed-restriction ontology and build it into tmp_path/out."""
    src = tmp_path / "w.ttl"
    src.write_text(_WARN_TTL, encoding="utf-8")
    reader = Reader()
    reader.load_instances(str(src), "owl", warnings=warnings)
    out = tmp_path / "out"
    build_html(reader.get_viewer(), out, reader=reader)
    return out


def test_report_written_with_warnings(tmp_path):
    """The report lists the warning code."""
    out = _build_warn_ttl(tmp_path, warnings=True)
    assert "malformed_restriction" in (out / "report.txt").read_text(encoding="utf-8")


def test_format_warnings_uses_display_names(tmp_path):
    """Viewer swaps model class names for display names, but leaves IRIs alone."""
    src = tmp_path / "h.ttl"
    src.write_text("""
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix : <http://ex.org/Attribute/> .
<http://ex.org/> a owl:Ontology .
:p a owl:ObjectProperty ; rdfs:subPropertyOf :q .
:q a owl:DatatypeProperty .
""", encoding="utf-8")
    reader = Reader()
    reader.load_instances(str(src), "owl", warnings=True)
    msg = reader.get_viewer().format_warnings(reader.get_warnings())[0]["message"]
    assert "Object Property http://ex.org/Attribute/p" in msg
    assert "Data Property http://ex.org/Attribute/q" in msg


def test_no_report_without_warnings_flag(tmp_path):
    """No report.txt when warnings were not requested."""
    assert not (_build_warn_ttl(tmp_path, warnings=False) / "report.txt").exists()