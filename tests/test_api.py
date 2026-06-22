# tests/test_api.py
"""
Integration tests for the /extract web layer:
content negotiation (Accept + ?format), full vs subgraph serialization,
upload/URL reader cache.

fabio ontology is loaded ONCE per session and reused everywhere (patched into the
URL path, serialized to a temp file for the upload path), so the default
suite makes a single network call.
"""
import re
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from lode.api import app, _load_url
from lode.reader import Reader

# raise_server_exceptions=False -> custom exception handlers render error.html
client = TestClient(app, raise_server_exceptions=False)

# Reference ontology for the deterministic suite
FABIO_URL = "https://w3id.org/spar/fabio"
FABIO_NS = "http://purl.org/spar/fabio/"


# --- Fixtures ----------------------------------------------------------------
@pytest.fixture(scope="session")
def fabio_reader():
    """Load fabio once (network). Swap FABIO_URL for a local file to go offline."""
    r = Reader()
    r.load_instances(FABIO_URL, "owl")
    return r


@pytest.fixture(scope="session")
def fabio_ttl(fabio_reader, tmp_path_factory):
    p = tmp_path_factory.mktemp("fix") / "fabio.ttl"
    p.write_text(fabio_reader._graph.serialize(format="turtle"), encoding="utf-8")
    return p

@pytest.fixture
def patched_url(fabio_reader):
    """GET-url tests reuse the cached fabio reader instead of hitting the net."""
    with patch("lode.api._load_url", return_value=fabio_reader) as m:
        yield m

# --- POST (file) -------------------------------------------------------------
def test_post_file_html(fabio_ttl):
    with open(fabio_ttl, "rb") as f:
        resp = client.post(
            "/extract",
            data={"read_as": "owl"},
            files={"file": ("fabio.ttl", f, "text/turtle")},
        )
    assert resp.status_code == 200
    assert "Abstract" in resp.text
    # token cablato nei link di navigazione
    assert "upload_id" in resp.text


def test_upload_then_navigate(fabio_ttl):
    """End-to-end: upload caches the Reader, navigation via token works
    without the original file (and without network)."""
    with open(fabio_ttl, "rb") as f:
        resp = client.post(
            "/extract",
            data={"read_as": "owl"},
            files={"file": ("fabio.ttl", f, "text/turtle")},
        )
    token = re.search(r"upload_id=([0-9a-f]{32})", resp.text)
    assert token, "no upload_id token in the rendered page"

    resp2 = client.get(
        "/extract",
        params={"read_as": "owl", "upload_id": token.group(1),
                "resource": FABIO_NS + "Abstract"},
    )
    assert resp2.status_code == 200
    assert "Abstract" in resp2.text


# --- GET content negotiation -------------------------------------------------
def test_get_turtle_full(patched_url):
    resp = client.get("/extract",
                      params={"read_as": "owl", "url": FABIO_URL, "format": "ttl"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/turtle")
    assert "fabio" in resp.text.lower()

@pytest.mark.parametrize("accept,ctype", [
    ("text/turtle", "text/turtle"),
    ("application/rdf+xml", "application/rdf+xml"),
    ("text/n3", "text/n3"),
])
def test_get_accept_negotiation(patched_url, accept, ctype):
    resp = client.get("/extract",
                      params={"read_as": "owl", "url": FABIO_URL},
                      headers={"Accept": accept})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith(ctype)


def test_get_subgraph_only(patched_url):
    resp = client.get("/extract", params={
        "read_as": "owl", "url": FABIO_URL, "format": "ttl",
        "resource": FABIO_NS + "Abstract"})
    assert resp.status_code == 200
    assert "Abstract" in resp.text
    # subgraph: non deve contenere entità scorrelate
    assert "AcademicProceedings" not in resp.text


def test_disposition_filename(patched_url):
    resp = client.get("/extract", params={
        "read_as": "owl", "url": FABIO_URL, "format": "ttl",
        "resource": FABIO_NS + "Abstract"})
    cd = resp.headers["content-disposition"]
    assert "inline" in cd
    assert "Abstract.ttl" in cd


def test_get_single_resource_html(patched_url):
    resp = client.get("/extract", params={
        "read_as": "owl", "url": FABIO_URL, "resource": FABIO_NS + "Abstract"})
    assert resp.status_code == 200
    assert "Abstract" in resp.text

def test_format_wins_over_accept(patched_url):
    # format=ttl deve vincere anche se Accept chiede rdf+xml
    resp = client.get("/extract",
                      params={"read_as": "owl", "url": FABIO_URL, "format": "ttl"},
                      headers={"Accept": "application/rdf+xml"})
    assert resp.headers["content-type"].startswith("text/turtle")

# --- URL cache ---------------------------------------------------------------
def test_url_cache_single_load():
    """Same url+params -> Reader parsed once, served from lru_cache after."""
    _load_url.cache_clear()
    with patch.object(Reader, "load_instances") as m:
        _load_url("u", "owl", None, None, False)
        _load_url("u", "owl", None, None, False)
    assert m.call_count == 1
    _load_url.cache_clear()