"""Enrichment modules and their provenance (named graphs / quads).

What is tested
--------------
Each module (imported, closure, partial_import) loads external documents into the
graph of the documented ontology. With any module active the graph is a
ProvenanceGraph: every triple sits in the named graph of the document that asserts
it, and keeps that context through the URL cache, per-entity export and the
quad serializations (TriG, N-Quads, JSON-LD).

Sections
--------
1. Invariants common to all modules (parametrized over MODULES)
2. imported          owl:imports, depth 1
3. closure           transitive owl:imports
4. partial_import    only the home definition of each mentioned external term
5. URL cache         only the main document is cached; modules re-applied on a hit
6. Per-entity provenance (viewer)
7. HTTP API          the same guarantees end-to-end, through serialization

Fixtures
--------
Documents live in tests/data/provenance/ (one .ttl per ontology, each with a header
comment on its role) and are served at http://ex.org/<file name> by `offline_fetch`
(autouse), which replaces the Loader's HTTP method: everything runs offline.

The ProvenanceGraph container itself and the RDF helpers are tested in
test_rdf_helpers.py.

"""
from pathlib import Path
from urllib.parse import urldefrag

import pytest
from fastapi.testclient import TestClient
from rdflib import BNode, Dataset, Graph, Literal, Namespace, URIRef
from rdflib.compare import isomorphic
from rdflib.graph import DATASET_DEFAULT_GRAPH_ID
from rdflib.namespace import OWL, RDF, RDFS

import lode.helpers.spool as spool
import lode.reader.security as security
from lode import api
from lode.api import app
from lode.exceptions import ArtefactNotFoundError
from lode.reader.loader import Loader
from lode.reader.provenance_graph import ProvenanceGraph
from lode.viewer.base_viewer import (
    QUAD_SERIALIZATION_FORMATS, SERIALIZATION_FORMATS, BaseViewer, formats_for,
)

# ==========================================================================
# FIXTURES
# ==========================================================================

DATA = Path(__file__).parent / "data" / "provenance"
DOCS = {f"http://ex.org/{p.stem}": p.read_text(encoding="utf-8") for p in DATA.glob("*.ttl")}
assert "http://ex.org/main" in DOCS, f"fixture documents missing in {DATA}"
MAIN_TTL = DOCS["http://ex.org/main"]
MODULES = ["imported", "closure", "partial_import"]

# Ontology IRIs (= named graph names) and term namespaces
MAIN, IMP, DEEP = URIRef("http://ex.org/main"), URIRef("http://ex.org/imp"), URIRef("http://ex.org/deep")
HOME, VER = URIRef("http://ex.org/home"), URIRef("http://ex.org/ver/1.0")   # VER: versioned IRI
M, I, D = Namespace("http://ex.org/main#"), Namespace("http://ex.org/imp#"), Namespace("http://ex.org/deep#")
H, V, X = Namespace("http://ex.org/home#"), Namespace("http://ex.org/ver#"), Namespace("http://ex.org/missing#")

PREFIXES = """
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
"""


@pytest.fixture(autouse=True)
def offline_fetch(monkeypatch):
    """Serve DOCS instead of the network ("missing" is absent, so its fetch fails).
    Returns the list of fetched URLs, in order."""
    calls = []

    def fake(self, url):
        calls.append(url)
        key = urldefrag(url)[0].rstrip("/")
        if key not in DOCS:
            raise ArtefactNotFoundError("not found", context={"url": url})
        self.graph = Graph().parse(data=DOCS[key], format="turtle")

    monkeypatch.setattr(Loader, "_load_from_url_with_content_negotiation", fake)
    return calls


@pytest.fixture
def main_path():
    """main.ttl as a local file (same code path as an upload in the spool)."""
    return str(DATA / "main.ttl")


def load(main_path, flag):
    return Loader(main_path, **{flag: True}).get_graph()


def doc(name) -> Graph:
    """A fixture document as parsed by itself (the expected content of its graph)."""
    return Graph().parse(data=DOCS[f"http://ex.org/{name}"], format="turtle")


def write_ttl(tmp_path, name, body):
    """Extra main document for a single test."""
    p = tmp_path / name
    p.write_text(PREFIXES + body, encoding="utf-8")
    return str(p)


def graphs(ds) -> set:
    """Names of the named graphs that hold at least one triple (default graph excluded)."""
    return {c for *_, c in ds.quads()} - {DATASET_DEFAULT_GRAPH_ID}


def contexts(ds, triple) -> set:
    """Named graphs holding `triple` (default graph excluded)."""
    return {c for *_, c in ds.quads((*triple, None))} - {DATASET_DEFAULT_GRAPH_ID}


def ground(g) -> set:
    """Triples without blank nodes (comparable across separate parses)."""
    return {t for t in g if not any(isinstance(x, BNode) for x in t)}


# ==========================================================================
# 1. INVARIANTS COMMON TO ALL MODULES
# ==========================================================================

class TestModuleInvariants:
    """Whatever the module: named graphs only, main graph untouched, nothing unnamed."""

    def test_no_modules_plain_graph_no_fetch(self, main_path, offline_fetch):
        g = Loader(main_path).get_graph()
        assert type(g) is Graph
        assert offline_fetch == []

    @pytest.mark.parametrize("flag", MODULES)
    def test_returns_provenance_graph_named_after_main_ontology(self, main_path, flag):
        loader = Loader(main_path, **{flag: True})
        assert isinstance(loader.get_graph(), ProvenanceGraph)
        assert loader.ontology_iri == MAIN

    @pytest.mark.parametrize("flag", MODULES)
    def test_default_graph_stays_empty(self, main_path, flag):
        assert len(load(main_path, flag).default_graph) == 0

    @pytest.mark.parametrize("flag", MODULES)
    def test_every_triple_has_a_named_graph(self, main_path, flag):
        ds = load(main_path, flag)
        for t in ds:
            assert contexts(ds, t), t

    @pytest.mark.parametrize("flag", MODULES)
    def test_main_graph_is_exactly_the_main_document(self, main_path, flag):
        """Modules never write into the documented ontology's graph."""
        assert isomorphic(load(main_path, flag).graph(MAIN), doc("main"))

    @pytest.mark.parametrize("flag", MODULES)
    def test_quad_serializations_round_trip(self, main_path, flag):
        ds = load(main_path, flag)
        for fmt in ("trig", "nquads"):
            back = Dataset(default_union=True)
            back.parse(data=ds.serialize(format=fmt), format=fmt)
            assert graphs(back) == graphs(ds), fmt
            for c in graphs(ds):
                assert isomorphic(back.graph(c), ds.graph(c)), (fmt, c)


# ==========================================================================
# 2. IMPORTED (owl:imports, depth 1)
# ==========================================================================

class TestImported:
    """Each directly imported ontology in its own named graph, verbatim."""

    @pytest.fixture
    def ds(self, main_path):
        return load(main_path, "imported")

    def test_graphs_are_main_and_direct_imports(self, ds):
        assert graphs(ds) == {MAIN, IMP}

    def test_imported_graph_is_exactly_its_document(self, ds):
        assert isomorphic(ds.graph(IMP), doc("imp"))

    def test_depth_one_only(self, ds):
        assert (D.D, None, None) not in ds

    def test_redefinitions_stay_in_the_importing_graph(self, ds):
        """imp redefines home#T: with formal imports that triple is kept, in imp's graph."""
        assert contexts(ds, (H.T, RDFS.comment, Literal("T redefined by imp"))) == {IMP}

    def test_imports_are_fetched_via_url_from_a_local_file(self, main_path, offline_fetch):
        load(main_path, "imported")
        assert offline_fetch == ["http://ex.org/imp"]


# ==========================================================================
# 3. CLOSURE (transitive owl:imports)
# ==========================================================================

class TestClosure:
    """The whole import tree, one named graph per document."""

    @pytest.fixture
    def ds(self, main_path):
        return load(main_path, "closure")

    def test_graphs_are_the_whole_import_tree(self, ds):
        assert graphs(ds) == {MAIN, IMP, DEEP}

    @pytest.mark.parametrize("name,ctx", [("imp", IMP), ("deep", DEEP)])
    def test_each_imported_graph_is_exactly_its_document(self, ds, name, ctx):
        assert isomorphic(ds.graph(ctx), doc(name))

    def test_document_without_ontology_falls_back_to_its_url(self, ds):
        assert contexts(ds, (D.D, RDF.type, OWL.Class)) == {DEEP}

    def test_local_file_without_ontology_uses_file_uri(self):
        """Known and accepted: without owl:Ontology the main context is the file path."""
        p = DATA / "anon.ttl"
        loader = Loader(str(p), closure=True)
        assert loader.ontology_iri == URIRef(p.resolve().as_uri())
        assert contexts(loader.get_graph(), (URIRef("http://ex.org/anon#A"), RDF.type, OWL.Class)) \
            == {loader.ontology_iri}


# ==========================================================================
# 4. PARTIAL IMPORT (home definitions of mentioned external terms)
# ==========================================================================

class TestPartialImport:
    """External term = documented ontology (priority) + its home graph only."""

    @pytest.fixture
    def ds(self, main_path):
        return load(main_path, "partial_import")

    # -- which graphs, which content -------------------------------------

    def test_graphs_are_main_and_homes_only(self, ds):
        """imp is formally imported but is nobody's home: no graph for it; missing is
        unreachable: no graph either."""
        assert graphs(ds) == {MAIN, HOME, VER}

    @pytest.mark.parametrize("name,ctx", [("home", HOME), ("ver", VER)])
    def test_home_graphs_hold_only_triples_of_their_document(self, ds, name, ctx):
        assert ground(ds.graph(ctx)) <= ground(doc(name))

    def test_external_ontology_headers_not_copied(self, ds):
        for onto in (HOME, VER, IMP):
            assert (onto, RDF.type, OWL.Ontology) not in ds
        assert set(ds.subjects(RDF.type, OWL.Ontology)) == {MAIN}

    # -- the definition of a term ----------------------------------------

    def test_home_definition_in_home_graph(self, ds):
        assert contexts(ds, (H.T, RDF.type, OWL.Class)) == {HOME}
        assert contexts(ds, (H.T, RDFS.comment, Literal("T defined by home"))) == {HOME}

    def test_documented_ontology_has_priority(self, ds):
        """main restates the label of home#T: main's label wins, home's is not copied."""
        assert set(ds.objects(H.T, RDFS.label)) == {Literal("T from main", lang="en")}
        assert contexts(ds, (H.T, RDFS.label, Literal("T from main", lang="en"))) == {MAIN}

    def test_third_party_redefinition_is_not_copied(self, ds):
        """imp redefines home#T, but imp is not home#T's home."""
        assert (H.T, RDFS.comment, Literal("T redefined by imp")) not in ds
        assert (H.T, OWL.equivalentClass, I.I) not in ds

    def test_blank_nodes_follow_parent_context(self, ds):
        (restr,) = [o for o in ds.objects(H.T, RDFS.subClassOf) if isinstance(o, BNode)]
        assert contexts(ds, (H.T, RDFS.subClassOf, restr)) == {HOME}
        for t in ds.triples((restr, None, None)):
            assert contexts(ds, t) == {HOME}
        assert set(ds.predicates(restr)) == {RDF.type, OWL.onProperty, OWL.someValuesFrom}

    # -- finding the home -------------------------------------------------

    def test_home_by_dereferenced_document_when_iri_differs(self, ds):
        """ver declares a versioned ontology IRI (.../ver/1.0) != the term namespace."""
        assert contexts(ds, (V.V, RDF.type, OWL.Class)) == {VER}

    def test_unreachable_home_gets_no_external_definition(self, ds, offline_fetch):
        """missing is not served: imp's redefinition of missing#X must not fill the gap."""
        assert "http://ex.org/missing" in offline_fetch
        assert set(ds.predicate_objects(X.X)) == set()

    # -- fetching ---------------------------------------------------------

    def test_home_document_fetched_once(self, main_path, offline_fetch):
        load(main_path, "partial_import")
        assert offline_fetch.count("http://ex.org/home") == 1

    def test_vocabulary_without_ontology_fetched_once(self, tmp_path, offline_fetch, monkeypatch):
        """A slash vocabulary without owl:Ontology (e.g. DC Terms) dereferences every term
        to the same document: one download for all its terms."""
        voc = PREFIXES + """
<http://ex.org/voc/a> rdfs:label "a" .
<http://ex.org/voc/b> rdfs:label "b" .
"""
        monkeypatch.setitem(DOCS, "http://ex.org/voc/a", voc)
        monkeypatch.setitem(DOCS, "http://ex.org/voc/b", voc)
        path = write_ttl(tmp_path, "m.ttl", """
<http://ex.org/m2> a owl:Ontology .
<http://ex.org/m2#X> rdfs:seeAlso <http://ex.org/voc/a>, <http://ex.org/voc/b> .
""")
        ds = Loader(path, partial_import=True).get_graph()
        assert len([u for u in offline_fetch if u.startswith("http://ex.org/voc/")]) == 1
        assert (URIRef("http://ex.org/voc/b"), RDFS.label, Literal("b")) in ds

    def test_failed_namespace_not_retried_per_term(self, tmp_path, offline_fetch):
        """A namespace that fails once (HTML, 404...) is not retried term by term."""
        path = write_ttl(tmp_path, "m.ttl", """
<http://ex.org/m3> a owl:Ontology .
<http://ex.org/m3#X> rdfs:seeAlso <http://ex.org/dead/a>, <http://ex.org/dead/b>, <http://ex.org/dead/c> .
""")
        Loader(path, partial_import=True)
        assert len([u for u in offline_fetch if u.startswith("http://ex.org/dead/")]) == 1


# ==========================================================================
# 5. URL CACHE
# ==========================================================================

class TestCacheRoundTrip:
    """The URL cache stores only the main document; modules are re-applied on a hit."""

    @pytest.mark.parametrize("flag", MODULES)
    def test_reloading_main_graph_reproduces_same_quads(self, main_path, tmp_path, flag):
        fresh = Loader(main_path, **{flag: True})
        cached = tmp_path / "cached.ttl"
        cached.write_text(fresh.get_graph().graph(fresh.ontology_iri).serialize(format="turtle"),
                          encoding="utf-8")
        again = Loader(str(cached), **{flag: True}).get_graph()
        assert graphs(again) == graphs(fresh.get_graph())
        for c in graphs(again):
            assert isomorphic(again.graph(c), fresh.get_graph().graph(c)), c

    def test_caching_the_union_breaks_provenance(self, main_path, tmp_path):
        """Regression guard: caching the union would put imported triples in the main graph."""
        fresh = load(main_path, "imported")
        cached = tmp_path / "union.ttl"
        cached.write_text(fresh.serialize(format="turtle"), encoding="utf-8")
        again = Loader(str(cached), imported=True).get_graph()
        assert MAIN in contexts(again, (I.I, RDF.type, OWL.Class))


# ==========================================================================
# 6. PER-ENTITY PROVENANCE (viewer)
# ==========================================================================

class FakeReader:
    """Minimal reader for BaseViewer: only the graph and an empty instance cache."""

    def __init__(self, graph):
        self._graph = graph
        self._instance_cache = {}


def entity_provenance(ds, subject):
    """What an entity card exports: its triples, placed back in their origin graphs."""
    sub = Graph()
    for t in ds.triples((subject, None, None)):
        sub.add(t)
    return BaseViewer(FakeReader(ds))._with_provenance(sub)


class TestEntityProvenance:
    """Formats offered, and each triple of an entity in the graph(s) it comes from."""

    def test_formats_without_modules_are_triple_formats(self):
        assert formats_for(Graph()) is SERIALIZATION_FORMATS

    def test_formats_with_modules_are_quad_formats(self):
        assert formats_for(ProvenanceGraph()) is QUAD_SERIALIZATION_FORMATS
        assert "xml" not in {f["fmt"] for f in QUAD_SERIALIZATION_FORMATS}

    def test_without_modules_provenance_is_unchanged(self):
        g = Graph()
        g.add((M.A, RDF.type, OWL.Class))
        sub = Graph()
        sub.add((M.A, RDF.type, OWL.Class))
        assert BaseViewer(FakeReader(g))._with_provenance(sub) is sub

    def test_partial_import_term_spans_main_and_home(self, main_path):
        """home#T: label from main, definition from home, nothing from imp."""
        ds = load(main_path, "partial_import")
        out = entity_provenance(ds, H.T)
        assert isinstance(out, ProvenanceGraph)
        assert graphs(out) == {MAIN, HOME}
        for t in out:
            assert contexts(out, t) == contexts(ds, t)

    def test_imported_term_spans_main_and_imported_graph(self, main_path):
        """With formal imports, imp's redefinition of home#T is part of the provenance."""
        out = entity_provenance(load(main_path, "imported"), H.T)
        assert graphs(out) == {MAIN, IMP}

    def test_shared_triple_listed_once_per_source(self):
        ds = ProvenanceGraph()
        t = (M.A, RDF.type, OWL.Class)
        ds.graph(MAIN).add(t)
        ds.graph(IMP).add(t)
        out = entity_provenance(ds, M.A)
        assert contexts(out, t) == {MAIN, IMP}
        nq = out.serialize(format="nquads")
        assert nq.count(f"<{MAIN}>") == 1 and nq.count(f"<{IMP}>") == 1

    @pytest.mark.parametrize("flag", MODULES)
    def test_no_blank_graph_names(self, main_path, flag):
        trig = entity_provenance(load(main_path, flag), H.T).serialize(format="trig")
        for line in trig.splitlines():
            if line.rstrip().endswith("{"):
                assert line.startswith("<"), line


# ==========================================================================
# 7. HTTP API (end-to-end)
# ==========================================================================
#
# Uploads go through the spool (spool.save) and are requested with
# GET /extract?upload_id=..., the same path as _resolve_reader. Quad serializations
# are parsed back into a Dataset (default_union=True, so objects()/subjects()/`in`
# see the named graphs) to check that contexts survive serialization.

RDFLIB_FMT = {"trig": "trig", "nq": "nquads", "jsonld": "json-ld"}


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture
def served_main(monkeypatch):
    """main.ttl is already served at http://ex.org/main: only disable anti-SSRF for ex.org."""
    monkeypatch.setattr(security, "check_url_safe", lambda url: None)
    return "http://ex.org/main"


def upload(content: str) -> str:
    return spool.save(content.encode("utf-8"))


def _flags(flags) -> dict:
    return {k: "true" for k, v in flags.items() if v}


def get(client, token, fmt, resource=None, **flags):
    """GET /extract on an upload, with an explicit ?format=."""
    params = {"read_as": "owl", "upload_id": token, "format": fmt, **_flags(flags)}
    if resource:
        params["resource"] = str(resource)
    return client.get("/extract", params=params)


def get_accept(client, token, accept, resource=None, **flags):
    """GET /extract on an upload, negotiating the format with the Accept header only."""
    params = {"read_as": "owl", "upload_id": token, **_flags(flags)}
    if resource:
        params["resource"] = str(resource)
    return client.get("/extract", params=params, headers={"Accept": accept})


def get_url(client, url, fmt=None, resource=None, cache=False, **flags):
    """GET /extract?url=... (URL path, with the spool cache)."""
    params = {"read_as": "owl", "url": url, "cache": "true" if cache else "false", **_flags(flags)}
    if fmt:
        params["format"] = fmt
    if resource:
        params["resource"] = str(resource)
    return client.get("/extract", params=params)


def as_dataset(resp, fmt) -> Dataset:
    assert resp.status_code == 200, resp.text[:500]
    assert "text/html" not in resp.headers.get("content-type", ""), f"{fmt}: got HTML instead of RDF"
    ds = Dataset(default_union=True)
    ds.parse(data=resp.text, format=RDFLIB_FMT[fmt])
    return ds


def default_graph_is_empty(ds) -> bool:
    return len(ds.graph(DATASET_DEFAULT_GRAPH_ID)) == 0


def filename(resp) -> str:
    cd = resp.headers["content-disposition"]
    assert cd.startswith("inline;"), cd
    return cd.split('filename="', 1)[1].rstrip('"')


class TestUploadWithoutModules:
    """No modules: plain graph, no quad formats."""

    @pytest.mark.parametrize("fmt", ["trig", "nq"])
    def test_quad_formats_rejected(self, client, fmt):
        assert get(client, upload(MAIN_TTL), fmt).status_code == 406

    @pytest.mark.parametrize("fmt", ["ttl", "nt", "rdf", "jsonld"])
    def test_triple_formats_available(self, client, fmt):
        assert get(client, upload(MAIN_TTL), fmt).status_code == 200

    def test_html_offers_triple_formats_only(self, client):
        html = client.post("/extract", data={"read_as": "owl"},
                           files={"file": ("main.ttl", MAIN_TTL, "text/turtle")}).text
        assert "N-Triples" in html
        assert "TriG" not in html and "N-Quads" not in html


class TestUploadImportedClosure:
    """Formal imports through the API: graphs survive serialization."""

    def test_html_offers_quad_formats(self, client):
        html = client.post("/extract", data={"read_as": "owl", "imported": "true"},
                           files={"file": ("main.ttl", MAIN_TTL, "text/turtle")}).text
        assert "TriG" in html and "N-Quads" in html
        assert "N-Triples" not in html and "RDF/XML" not in html

    @pytest.mark.parametrize("fmt", ["trig", "nq", "jsonld"])
    def test_imported_graphs_survive_serialization(self, client, fmt):
        ds = as_dataset(get(client, upload(MAIN_TTL), fmt, imported=True), fmt)
        assert graphs(ds) == {MAIN, IMP}
        assert default_graph_is_empty(ds)
        assert contexts(ds, (I.I, RDF.type, OWL.Class)) == {IMP}
        assert (D.D, None, None) not in ds

    def test_upload_context_is_declared_ontology_not_spool_path(self, client):
        ds = as_dataset(get(client, upload(MAIN_TTL), "trig", imported=True), "trig")
        assert not any(str(g).startswith("file:") for g in graphs(ds))

    def test_closure_fallback_context_is_url(self, client):
        ds = as_dataset(get(client, upload(MAIN_TTL), "nq", closure=True), "nq")
        assert graphs(ds) == {MAIN, IMP, DEEP}
        assert contexts(ds, (D.D, RDF.type, OWL.Class)) == {DEEP}

    def test_imported_redefinition_stays_in_imported_graph(self, client):
        ds = as_dataset(get(client, upload(MAIN_TTL), "trig", imported=True), "trig")
        assert contexts(ds, (H.T, RDFS.comment, Literal("T redefined by imp"))) == {IMP}


class TestUploadPartialImport:
    """partial_import through the API: same boundary as TestPartialImport."""

    @pytest.fixture
    def ds(self, client):
        return as_dataset(get(client, upload(MAIN_TTL), "trig", partial_import=True), "trig")

    def test_graphs_are_main_and_homes_only(self, ds):
        assert graphs(ds) == {MAIN, HOME, VER}

    def test_documented_ontology_has_priority(self, ds):
        assert set(ds.objects(H.T, RDFS.label)) == {Literal("T from main", lang="en")}
        assert contexts(ds, (H.T, RDFS.label, Literal("T from main", lang="en"))) == {MAIN}

    def test_home_definition_in_home_graph(self, ds):
        assert contexts(ds, (H.T, RDFS.comment, Literal("T defined by home"))) == {HOME}

    def test_third_party_redefinition_absent(self, ds):
        assert (H.T, RDFS.comment, Literal("T redefined by imp")) not in ds
        assert (H.T, OWL.equivalentClass, I.I) not in ds

    def test_restriction_blank_nodes_in_home_graph(self, ds):
        (restr,) = [o for o in ds.objects(H.T, RDFS.subClassOf) if isinstance(o, BNode)]
        for t in ds.triples((restr, None, None)):
            assert contexts(ds, t) == {HOME}

    def test_versioned_home_found_via_dereferenced_document(self, ds):
        assert contexts(ds, (V.V, RDF.type, OWL.Class)) == {VER}

    def test_unreachable_home_gives_no_external_definition(self, ds):
        assert set(ds.predicate_objects(X.X)) == set()

    def test_external_ontology_headers_absent(self, ds):
        assert set(ds.subjects(RDF.type, OWL.Ontology)) == {MAIN}

    @pytest.mark.parametrize("fmt", ["trig", "nq", "jsonld"])
    def test_resource_export_has_origin_graphs(self, client, fmt):
        ds = as_dataset(get(client, upload(MAIN_TTL), fmt, resource=H.T, partial_import=True), fmt)
        assert graphs(ds) == {MAIN, HOME}
        assert default_graph_is_empty(ds)
        assert contexts(ds, (H.T, RDF.type, OWL.Class)) == {HOME}


class TestDownloadAccept:
    """Accept is a preference: an unavailable format falls back to HTML
    (406 only for an explicit ?format=)."""

    @pytest.mark.parametrize("mime,fmt", [("application/trig", "trig"),
                                          ("application/n-quads", "nq"),
                                          ("application/ld+json", "jsonld")])
    def test_quad_mime_with_modules(self, client, mime, fmt):
        resp = get_accept(client, upload(MAIN_TTL), mime, imported=True)
        assert resp.headers["content-type"].startswith(mime)
        assert graphs(as_dataset(resp, fmt)) == {MAIN, IMP}

    def test_first_available_mime_wins(self, client):
        resp = get_accept(client, upload(MAIN_TTL), "application/n-quads;q=0.9, text/html;q=0.8",
                          imported=True)
        assert resp.headers["content-type"].startswith("application/n-quads")

    def test_resource_export_via_accept(self, client):
        resp = get_accept(client, upload(MAIN_TTL), "application/trig", resource=H.T, partial_import=True)
        assert graphs(as_dataset(resp, "trig")) == {MAIN, HOME}

    def test_quad_mime_without_modules_falls_back_to_html(self, client):
        resp = get_accept(client, upload(MAIN_TTL), "application/trig")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")

    def test_triple_mime_without_modules(self, client):
        resp = get_accept(client, upload(MAIN_TTL), "text/turtle")
        assert resp.headers["content-type"].startswith("text/turtle")
        assert len(Graph().parse(data=resp.text, format="turtle")) > 0

    def test_triple_mime_with_modules_falls_back_to_html(self, client):
        """Current behaviour: with modules, Turtle is not offered. Update this test if the
        union is ever served as Turtle alongside the quad formats."""
        resp = get_accept(client, upload(MAIN_TTL), "text/turtle", imported=True)
        assert resp.headers["content-type"].startswith("text/html")

    def test_browser_accept_gets_html(self, client):
        resp = get_accept(client, upload(MAIN_TTL), "text/html,application/xhtml+xml,*/*;q=0.8",
                          imported=True)
        assert resp.headers["content-type"].startswith("text/html")


class TestDownloadFilename:
    """Content-Disposition file name: resource -> local name; graph -> last URL segment,
    or 'graph' for uploads."""

    @pytest.mark.parametrize("fmt", ["trig", "nq", "jsonld"])
    def test_upload_whole_graph(self, client, fmt):
        assert filename(get(client, upload(MAIN_TTL), fmt, imported=True)) == f"graph.{fmt}"

    @pytest.mark.parametrize("fmt", ["trig", "nq"])
    def test_resource_uses_local_name(self, client, fmt):
        resp = get(client, upload(MAIN_TTL), fmt, resource=H.T, partial_import=True)
        assert filename(resp) == f"T.{fmt}"

    def test_url_whole_graph_uses_last_segment(self, client, served_main):
        assert filename(get_url(client, served_main, "trig", imported=True)) == "main.trig"

    def test_url_trailing_slash(self, client, served_main):
        assert filename(get_url(client, served_main + "/", "trig", imported=True)) == "main.trig"

    def test_triple_format_without_modules(self, client):
        assert filename(get(client, upload(MAIN_TTL), "ttl")) == "graph.ttl"


class TestDownloadUrl:
    """?url= path: fetch of the main document plus the spool cache."""

    def test_imported_graphs(self, client, served_main):
        ds = as_dataset(get_url(client, served_main, "trig", imported=True), "trig")
        assert graphs(ds) == {MAIN, IMP}
        assert contexts(ds, (I.I, RDF.type, OWL.Class)) == {IMP}

    def test_partial_import_homes(self, client, served_main):
        ds = as_dataset(get_url(client, served_main, "nq", partial_import=True), "nq")
        assert graphs(ds) == {MAIN, HOME, VER}
        assert (H.T, RDFS.comment, Literal("T redefined by imp")) not in ds

    def test_quad_format_without_modules_is_406(self, client, served_main):
        assert get_url(client, served_main, "trig").status_code == 406

    @pytest.mark.parametrize("flag", MODULES)
    def test_cache_stores_main_document_only(self, client, served_main, flag):
        """Regression: the cache held the enriched union, and on a hit the imported
        triples ended up in the main graph."""
        get_url(client, served_main, "trig", cache=False, **{flag: True})
        token = api._url_token(served_main, "owl", *(True if f == flag else None for f in MODULES))
        cached = Graph().parse(spool.get_path(token), format="turtle")
        assert isomorphic(cached, Graph().parse(data=MAIN_TTL, format="turtle"))

    @pytest.mark.parametrize("flag", MODULES)
    def test_cache_hit_preserves_provenance(self, client, served_main, flag):
        fresh = as_dataset(get_url(client, served_main, "trig", cache=False, **{flag: True}), "trig")
        hit = as_dataset(get_url(client, served_main, "trig", cache=True, **{flag: True}), "trig")
        assert graphs(hit) == graphs(fresh)
        for g in graphs(fresh):
            assert isomorphic(hit.graph(g), fresh.graph(g)), g


class TestUploadEdgeCases:
    def test_upload_without_ontology_uses_spool_path(self, client):
        """Known and accepted: without owl:Ontology the context is the spool path."""
        ds = as_dataset(get(client, upload(DOCS["http://ex.org/anon"]), "trig", imported=True), "trig")
        local = {g for g in graphs(ds) if str(g).startswith("file:")}
        assert len(local) == 1
        assert contexts(ds, (URIRef("http://ex.org/anon#A"), RDF.type, OWL.Class)) == local

    @pytest.mark.parametrize("flag", MODULES)
    def test_same_upload_reloaded_gives_same_quads(self, client, flag):
        token = upload(MAIN_TTL)
        a = as_dataset(get(client, token, "trig", **{flag: True}), "trig")
        b = as_dataset(get(client, token, "trig", **{flag: True}), "trig")
        assert graphs(a) == graphs(b)
        for g in graphs(a):
            assert isomorphic(a.graph(g), b.graph(g)), g