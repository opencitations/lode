"""Enrichment modules and their provenance (named graphs / quads).

What is tested
--------------
Each module (imported, closure, partial_import) loads external documents into the
graph of the documented ontology. With any module active the graph is a
ProvenanceGraph: every triple sits in the named graph of the document that asserts
it, and keeps that context through the URL cache and the per-entity provenance
(quads: TriG, N-Quads, JSON-LD). Exports and content negotiation, instead, return
only the triples of the loaded artefact, with or without modules.

Sections
--------
1. Invariants common to all modules (parametrized over MODULES)
2. imported          owl:imports, depth 1
3. closure           transitive owl:imports
4. partial_import    only the home definition of each mentioned external term
5. URL cache         only the main document is cached; modules re-applied on a hit
6. Per-entity provenance (viewer)
7. HTTP API          exports are triples of the loaded artefact only, end-to-end

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
from lode.reader.reader import Reader
from lode.viewer.base_viewer import QUAD_SERIALIZATION_FORMATS, BaseViewer

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

    # -- priority of documented ontology over imported ontos --------------
    
    def test_both_definitions_kept_with_provenance(self, ds):
        """main restates the label of home#T: both labels kept, each in its own graph."""
        assert contexts(ds, (H.T, RDFS.label, Literal("T from main", lang="en"))) == {MAIN}
        assert contexts(ds, (H.T, RDFS.label, Literal("T from home", lang="en"))) == {HOME}

    def test_documented_values_come_first(self, main_path):
        """The Reader puts main's label of home#T before home's."""
        from lode.reader.reader import Reader
        reader = Reader()
        reader.load_instances(graph_path=main_path, read_as="owl", partial_import=True)
        for inst in reader._instance_cache[H.T]:
            labels = [l.get_has_value() for l in inst.get_has_label()]
            if labels:
                assert labels[0] == "T from main", labels

    # -- finding the home -------------------------------------------------

    def test_home_by_dereferenced_document_when_iri_differs(self, ds):
        """ver declares a versioned ontology IRI (.../ver/1.0) != the term namespace."""
        assert contexts(ds, (V.V, RDF.type, OWL.Class)) == {VER}

    def test_unreachable_home_gets_no_external_definition(self, ds, offline_fetch):
        """missing is not served: only main's own triple, imp's redefinition must not fill the gap."""
        assert "http://ex.org/missing" in offline_fetch
        assert set(ds.predicate_objects(X.X)) == {(RDFS.comment, Literal("X described by main"))}
        assert contexts(ds, (X.X, RDFS.comment, Literal("X described by main"))) == {MAIN}

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
<http://ex.org/voc/a> rdfs:comment "a described by m2" .
<http://ex.org/voc/b> rdfs:comment "b described by m2" .
""")
        ds = Loader(path, partial_import=True).get_graph()
        assert len([u for u in offline_fetch if u.startswith("http://ex.org/voc/")]) == 1
        assert (URIRef("http://ex.org/voc/b"), RDFS.label, Literal("b")) in ds

    def test_failed_namespace_not_retried_per_term(self, tmp_path, offline_fetch):
        """A namespace that fails once (HTML, 404...) is not retried term by term."""
        path = write_ttl(tmp_path, "m.ttl", """
<http://ex.org/m3> a owl:Ontology .
<http://ex.org/m3#X> rdfs:seeAlso <http://ex.org/dead/a>, <http://ex.org/dead/b>, <http://ex.org/dead/c> .
<http://ex.org/dead/a> rdfs:comment "a" .
<http://ex.org/dead/b> rdfs:comment "b" .
<http://ex.org/dead/c> rdfs:comment "c" .
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

    def __init__(self, graph, ontology_iri=None):
        self._graph = graph
        self._instance_cache = {}
        self._ontology_iri = ontology_iri


def entity_provenance(ds, subject):
    """What an entity card shows as provenance: its triples, placed in their origin graphs."""
    sub = Graph()
    for t in ds.triples((subject, None, None)):
        sub.add(t)
    return BaseViewer(FakeReader(ds))._with_provenance(sub)


class TestEntityProvenance:
    """Formats offered, and each triple of an entity in the graph(s) it comes from."""

    def test_quad_formats_have_no_rdfxml(self):
        assert "xml" not in {f["fmt"] for f in QUAD_SERIALIZATION_FORMATS}

    def test_without_modules_provenance_is_a_quad_in_the_artefact_graph(self):
        g = Graph()
        g.add((M.A, RDF.type, OWL.Class))
        sub = Graph()
        sub.add((M.A, RDF.type, OWL.Class))
        out = BaseViewer(FakeReader(g, MAIN))._with_provenance(sub)
        assert isinstance(out, ProvenanceGraph)
        assert graphs(out) == {MAIN}

    def test_card_provenance_names_the_graph_without_modules(self, main_path):
        reader = Reader()
        reader.load_instances(main_path, "owl")
        viewer = reader.get_viewer()
        codes = [f["code"] for inst in reader._instance_cache[H.T]
                 for f in viewer._build_provenance_subgraph(inst) if f["label"] == "TriG"]
        assert codes and all(f"<{MAIN}>" in c for c in codes)

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
# Exports and content negotiation return the triples of the loaded artefact, with or
# without modules: imported documents show up only in the provenance of each card.
# Uploads go through the spool (spool.save) and are requested with
# GET /extract?upload_id=..., the same path as _resolve_reader.

TRIPLE_FORMATS = {"ttl": "turtle", "nt": "nt", "rdf": "xml", "jsonld": "json-ld"}
QUAD_EXTS = ["trig", "nq"]
ALL_FLAGS = [None, *MODULES]


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


def flags_of(flag) -> dict:
    """Request flags for one module, or none."""
    return {flag: True} if flag else {}


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


def as_graph(resp, fmt) -> Graph:
    """Parse an export response back into a plain Graph (a quad format would not parse here)."""
    assert resp.status_code == 200, resp.text[:500]
    assert "text/html" not in resp.headers.get("content-type", ""), f"{fmt}: got HTML instead of RDF"
    return Graph().parse(data=resp.text, format=TRIPLE_FORMATS[fmt])


def filename(resp) -> str:
    cd = resp.headers["content-disposition"]
    assert cd.startswith("inline;"), cd
    return cd.split('filename="', 1)[1].rstrip('"')


class TestExportIsLoadedArtefactOnly:
    """Whatever the modules, an export holds the triples of the loaded document and nothing else."""

    @pytest.mark.parametrize("flag", ALL_FLAGS)
    @pytest.mark.parametrize("fmt", list(TRIPLE_FORMATS))
    def test_whole_export_is_the_main_document(self, client, fmt, flag):
        g = as_graph(get(client, upload(MAIN_TTL), fmt, **flags_of(flag)), fmt)
        assert isomorphic(g, doc("main"))

    @pytest.mark.parametrize("flag", ALL_FLAGS)
    @pytest.mark.parametrize("fmt", QUAD_EXTS)
    def test_quad_formats_rejected(self, client, fmt, flag):
        assert get(client, upload(MAIN_TTL), fmt, **flags_of(flag)).status_code == 406

    def test_resource_export_has_main_triples_only(self, client):
        """home#T: the label restated by main is exported, the definition of home is not."""
        g = as_graph(get(client, upload(MAIN_TTL), "ttl", resource=H.T, partial_import=True), "ttl")
        assert ground(g) <= ground(doc("main"))
        assert (H.T, RDFS.label, Literal("T from main", lang="en")) in g
        assert (H.T, RDFS.comment, Literal("T defined by home")) not in g

    def test_documented_values_come_first(self, main_path):
        """The Reader puts main's label of home#T before home's."""
        reader = Reader()
        reader.load_instances(graph_path=main_path, read_as="owl", partial_import=True)
        for inst in reader._instance_cache[H.T]:
            labels = [l.get_has_value() for l in inst.get_has_label()]
            if labels:
                assert labels[0] == "T from main", labels


class TestHtmlOffers:
    """The page offers triples to export and quads as provenance, with or without modules."""

    @pytest.mark.parametrize("flag", ALL_FLAGS)
    def test_export_in_triples_provenance_in_quads(self, client, flag):
        html = client.post("/extract", data={"read_as": "owl", **_flags(flags_of(flag))},
                           files={"file": ("main.ttl", MAIN_TTL, "text/turtle")}).text
        assert "N-Triples" in html and "RDF/XML" in html
        assert "TriG" in html and "N-Quads" in html


class TestDownloadAccept:
    """Accept is a preference: an unavailable format falls back to HTML
    (406 only for an explicit ?format=)."""

    @pytest.mark.parametrize("flag", ALL_FLAGS)
    @pytest.mark.parametrize("mime", ["application/trig", "application/n-quads"])
    def test_quad_mime_falls_back_to_html(self, client, mime, flag):
        resp = get_accept(client, upload(MAIN_TTL), mime, **flags_of(flag))
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")

    @pytest.mark.parametrize("flag", ALL_FLAGS)
    def test_triple_mime(self, client, flag):
        resp = get_accept(client, upload(MAIN_TTL), "text/turtle", **flags_of(flag))
        assert resp.headers["content-type"].startswith("text/turtle")
        assert isomorphic(as_graph(resp, "ttl"), doc("main"))

    def test_first_available_mime_wins(self, client):
        resp = get_accept(client, upload(MAIN_TTL), "application/n-quads;q=0.9, text/turtle;q=0.8",
                          imported=True)
        assert resp.headers["content-type"].startswith("text/turtle")

    def test_resource_export_via_accept(self, client):
        resp = get_accept(client, upload(MAIN_TTL), "text/turtle", resource=H.T, partial_import=True)
        assert (H.T, RDFS.comment, Literal("T defined by home")) not in as_graph(resp, "ttl")

    def test_browser_accept_gets_html(self, client):
        resp = get_accept(client, upload(MAIN_TTL), "text/html,application/xhtml+xml,*/*;q=0.8",
                          imported=True)
        assert resp.headers["content-type"].startswith("text/html")


class TestDownloadFilename:
    """Content-Disposition file name: resource -> local name; graph -> last URL segment,
    or 'graph' for uploads."""

    @pytest.mark.parametrize("fmt", ["ttl", "jsonld"])
    def test_upload_whole_graph(self, client, fmt):
        assert filename(get(client, upload(MAIN_TTL), fmt, imported=True)) == f"graph.{fmt}"

    def test_resource_uses_local_name(self, client):
        resp = get(client, upload(MAIN_TTL), "ttl", resource=H.T, partial_import=True)
        assert filename(resp) == "T.ttl"

    def test_url_whole_graph_uses_last_segment(self, client, served_main):
        assert filename(get_url(client, served_main, "ttl", imported=True)) == "main.ttl"

    def test_url_trailing_slash(self, client, served_main):
        assert filename(get_url(client, served_main + "/", "ttl", imported=True)) == "main.ttl"


class TestDownloadUrl:
    """?url= path: fetch of the main document plus the spool cache."""

    @pytest.mark.parametrize("flag", ALL_FLAGS)
    def test_export_is_the_main_document(self, client, served_main, flag):
        g = as_graph(get_url(client, served_main, "ttl", **flags_of(flag)), "ttl")
        assert isomorphic(g, doc("main"))

    @pytest.mark.parametrize("flag", ALL_FLAGS)
    def test_quad_format_is_406(self, client, served_main, flag):
        assert get_url(client, served_main, "trig", **flags_of(flag)).status_code == 406

    @pytest.mark.parametrize("flag", MODULES)
    def test_cache_stores_main_document_only(self, client, served_main, flag):
        """Regression: the cache held the enriched union, and on a hit the imported
        triples ended up in the main graph."""
        get_url(client, served_main, "ttl", cache=False, **{flag: True})
        token = api._url_token(served_main, "owl", *(True if f == flag else None for f in MODULES))
        cached = Graph().parse(spool.get_path(token), format="turtle")
        assert isomorphic(cached, doc("main"))

    @pytest.mark.parametrize("flag", MODULES)
    def test_cache_hit_gives_the_same_export(self, client, served_main, flag):
        fresh = as_graph(get_url(client, served_main, "ttl", cache=False, **{flag: True}), "ttl")
        hit = as_graph(get_url(client, served_main, "ttl", cache=True, **{flag: True}), "ttl")
        assert isomorphic(hit, fresh)

    def test_cache_hit_keeps_the_url_as_graph_name(self, monkeypatch):
        """Without a declared owl:Ontology the graph is named after the URL, not the spool copy."""
        monkeypatch.setattr(security, "check_url_safe", lambda url: None)
        url = "http://ex.org/anon"
        for use_cache in (False, True):
            reader = api._load_url(url, "owl", None, None, None, False, use_cache=use_cache)
            assert reader._ontology_iri == URIRef(url)


class TestSourceName:
    """`source_name` names the graph when the ontology declares no IRI."""

    def test_names_the_graph_without_declared_ontology(self, tmp_path):
        p = tmp_path / "x.ttl"
        p.write_text("<http://ex.org/a> a <http://ex.org/B> .", encoding="utf-8")
        assert Loader(str(p), source_name="http://ex.org/x.ttl").ontology_iri == URIRef("http://ex.org/x.ttl")

    def test_declared_ontology_wins(self, main_path):
        assert Loader(main_path, source_name="http://ex.org/other").ontology_iri == MAIN