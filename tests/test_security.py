"""
Systematic tests for LODE security layer.

Covers:
  - security.check_url_safe   (scheme + SSRF on private/loopback/link-local/reserved IPs)
  - security.check_size       (MAX_BYTES limit)
  - security.check_is_text    (UTF-8 + no NUL byte)
  - security.check_extension  (RDF extension whitelist)
  - Loader._fetch_following_redirects (manual redirects, per-hop validation)
  - Loader._load_from_local_file       (parse + ArtefactLoadError)
  - Loader.load                        (empty-graph guard)

Network and DNS are mocked, so the suite runs offline.

Run:  uv run pytest tests/test_security.py -v
"""
import asyncio
import io
import socket
import pytest

from lode.reader import security
from lode.reader.loader import Loader
from lode.exceptions import ArtefactValidationError, ArtefactLoadError


# ----------------------------------------------------------------------
#  Helpers / fakes
# ----------------------------------------------------------------------
class FakeResponse:
    """Minimal stand-in for requests.Response (stream=True)."""
    def __init__(self, status_code=200, headers=None, body=b"", url="http://1.2.3.4/x"):
        self.status_code = status_code
        self.headers = headers or {}
        self.url = url
        self._body = body
        self.closed = False

    def iter_content(self, chunk_size):
        for i in range(0, len(self._body), chunk_size):
            yield self._body[i:i + chunk_size]

    def close(self):
        self.closed = True


def make_fake_get(responses):
    """Returns a fake requests.get that pops responses in order and records requested URLs."""
    queue = list(responses)
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        resp = queue.pop(0)
        resp.url = url  # reflect the actually-requested URL
        return resp

    fake_get.calls = calls
    return fake_get


# ----------------------------------------------------------------------
#  check_url_safe
# ----------------------------------------------------------------------
class TestCheckUrlSafe:

    @pytest.mark.parametrize("url", [
        "http://93.184.216.34/onto.ttl",     # public IP literal -> no real DNS
        "https://8.8.8.8/onto.ttl",
    ])
    def test_public_http_passes(self, url):
        security.check_url_safe(url)  # must not raise

    @pytest.mark.parametrize("url", [
        "file:///etc/passwd",
        "ftp://example.org/x",
        "gopher://example.org/x",
        "://example.org/x",
    ])
    def test_non_http_scheme_rejected(self, url):
        with pytest.raises(ArtefactValidationError):
            security.check_url_safe(url)

    @pytest.mark.parametrize("url", [
        "http://127.0.0.1/x",        # loopback
        "http://10.0.0.5/x",         # private
        "http://192.168.1.10/x",     # private
        "http://172.16.0.1/x",       # private
        "http://169.254.169.254/x",  # link-local (cloud metadata)
    ])
    def test_internal_addresses_rejected(self, url):
        with pytest.raises(ArtefactValidationError):
            security.check_url_safe(url)

    def test_no_host_rejected(self):
        with pytest.raises(ArtefactValidationError):
            security.check_url_safe("http://")

    def test_unresolvable_host_rejected(self, monkeypatch):
        def boom(host, port, *a, **k):
            raise socket.gaierror("name resolution failed")
        monkeypatch.setattr("lode.reader.security.socket.getaddrinfo", boom)
        with pytest.raises(ArtefactValidationError):
            security.check_url_safe("http://does-not-exist.invalid/x")

    def test_hostname_resolving_to_private_rejected(self, monkeypatch):
        # public-looking hostname that resolves to an internal IP (DNS-based SSRF)
        monkeypatch.setattr(
            "lode.reader.security.socket.getaddrinfo",
            lambda host, port, *a, **k: [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.1.2.3", 0))
            ],
        )
        with pytest.raises(ArtefactValidationError):
            security.check_url_safe("http://sneaky.example.org/x")


# ----------------------------------------------------------------------
#  check_size
# ----------------------------------------------------------------------
class TestCheckSize:

    def test_small_passes(self):
        security.check_size(10)  # must not raise

    def test_over_limit_rejected(self):
        with pytest.raises(ArtefactValidationError):
            security.check_size(security.MAX_BYTES + 1)


# ----------------------------------------------------------------------
#  check_is_text
# ----------------------------------------------------------------------
class TestCheckIsText:

    def test_valid_utf8_passes(self):
        security.check_is_text("@prefix ex: <http://e.org/> . ex:A a ex:B .".encode("utf-8"))

    def test_unicode_labels_pass(self):
        security.check_is_text("rdfs:label \"Citazione bibliografica\"@it".encode("utf-8"))

    def test_nul_byte_rejected(self):
        with pytest.raises(ArtefactValidationError):
            security.check_is_text(b"valid text\x00then binary")

    def test_invalid_utf8_rejected(self):
        with pytest.raises(ArtefactValidationError):
            security.check_is_text(b"\xff\xfe\xfa\x9c")


# ----------------------------------------------------------------------
#  check_extension
# ----------------------------------------------------------------------
class TestCheckExtension:

    @pytest.mark.parametrize("name", [
        "fabio.ttl", "fabio.rdf", "fabio.owl", "fabio.n3", "fabio.nt",
        "fabio.jsonld", "fabio.xml",
    ])
    def test_allowed_extensions_pass(self, name):
        security.check_extension(name)  # must not raise

    @pytest.mark.parametrize("name", [
        "malware.exe", "archive.zip", "image.png", "noextension", "script.sh",
    ])
    def test_disallowed_extensions_rejected(self, name):
        with pytest.raises(ArtefactValidationError):
            security.check_extension(name)


# ----------------------------------------------------------------------
#  Loader._fetch_following_redirects
# ----------------------------------------------------------------------
class TestFetchFollowingRedirects:

    def _loader(self):
        return Loader()  # bare instance, no file loaded

    def test_direct_200_returns_response(self, monkeypatch):
        resp = FakeResponse(status_code=200)
        fake = make_fake_get([resp])
        monkeypatch.setattr("lode.reader.loader.requests.get", fake)

        out = self._loader()._fetch_following_redirects(
            "http://93.184.216.34/onto.ttl", headers={})
        assert out is resp
        assert len(fake.calls) == 1

    def test_single_redirect_followed(self, monkeypatch):
        r1 = FakeResponse(status_code=303, headers={"Location": "http://8.8.8.8/final.ttl"})
        r2 = FakeResponse(status_code=200)
        fake = make_fake_get([r1, r2])
        monkeypatch.setattr("lode.reader.loader.requests.get", fake)

        out = self._loader()._fetch_following_redirects(
            "http://93.184.216.34/onto.ttl", headers={})
        assert out is r2
        assert fake.calls == ["http://93.184.216.34/onto.ttl", "http://8.8.8.8/final.ttl"]
        assert r1.closed is True  # intermediate response closed

    def test_redirect_to_private_blocked(self, monkeypatch):
        # SSRF via redirect: first hop public, redirect Location points to metadata IP
        r1 = FakeResponse(status_code=302, headers={"Location": "http://169.254.169.254/latest/"})
        fake = make_fake_get([r1])
        monkeypatch.setattr("lode.reader.loader.requests.get", fake)

        with pytest.raises(ArtefactValidationError):
            self._loader()._fetch_following_redirects(
                "http://93.184.216.34/onto.ttl", headers={})
        assert r1.closed is True
        assert len(fake.calls) == 1  # second hop never fetched

    def test_redirect_without_location_raises(self, monkeypatch):
        r1 = FakeResponse(status_code=303, headers={})  # no Location
        fake = make_fake_get([r1])
        monkeypatch.setattr("lode.reader.loader.requests.get", fake)

        with pytest.raises(ArtefactLoadError):
            self._loader()._fetch_following_redirects(
                "http://93.184.216.34/onto.ttl", headers={})

    def test_too_many_redirects_raises(self, monkeypatch):
        redirects = [
            FakeResponse(status_code=302, headers={"Location": "http://8.8.8.8/r"})
            for _ in range(6)
        ]
        fake = make_fake_get(redirects)
        monkeypatch.setattr("lode.reader.loader.requests.get", fake)

        with pytest.raises(ArtefactLoadError):
            self._loader()._fetch_following_redirects(
                "http://93.184.216.34/onto.ttl", headers={}, max_redirects=5)
        assert len(fake.calls) == 5  # capped

    def test_relative_location_resolved(self, monkeypatch):
        r1 = FakeResponse(status_code=303, headers={"Location": "other.ttl"})  # relative
        r2 = FakeResponse(status_code=200)
        fake = make_fake_get([r1, r2])
        monkeypatch.setattr("lode.reader.loader.requests.get", fake)

        out = self._loader()._fetch_following_redirects(
            "http://93.184.216.34/dir/onto.ttl", headers={})
        assert out is r2
        assert fake.calls[1] == "http://93.184.216.34/dir/other.ttl"


# ----------------------------------------------------------------------
#  Loader._load_from_local_file
# ----------------------------------------------------------------------
TURTLE_OK = """@prefix ex: <http://example.org/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
ex:A a rdfs:Class .
"""

class TestLoadLocalFile:

    def test_valid_turtle_parses(self, tmp_path):
        f = tmp_path / "ok.ttl"
        f.write_text(TURTLE_OK, encoding="utf-8")
        loader = Loader()
        loader._load_from_local_file(str(f))
        assert len(loader.graph) > 0

    def test_garbage_raises(self, tmp_path):
        f = tmp_path / "junk.ttl"
        f.write_text("this is definitely not RDF >>> ???", encoding="utf-8")
        loader = Loader()
        with pytest.raises(ArtefactLoadError):
            loader._load_from_local_file(str(f))

# magic bytes di formati binari reali
PNG  = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
ZIP  = b"PK\x03\x04\x14\x00\x00\x00"
ELF  = b"\x7fELF\x02\x01\x01\x00"
JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF"


class TestBinaryContentRejected:
    """Binari veri: NUL byte o UTF-8 invalido -> check_is_text li blocca."""

    @pytest.mark.parametrize("blob", [PNG, ZIP, ELF, JPEG])
    def test_binary_magic_rejected(self, blob):
        with pytest.raises(ArtefactValidationError):
            security.check_is_text(blob)

    def test_binary_with_rdf_name_caught_by_content(self):
        # il filename PASSA l'extension check, ma il contenuto binario viene preso da check_is_text
        security.check_extension("image.rdf")          # ok sul nome
        with pytest.raises(ArtefactValidationError):
            security.check_is_text(PNG)                 # bloccato sul contenuto


class TestExtensionBypass:

    @pytest.mark.parametrize("name", ["rat.rdf.exe", "rat.ttl.sh", "rat.owl.bat"])
    def test_trailing_dangerous_extension_rejected(self, name):
        # l'estensione VERA (ultima) e' pericolosa -> rifiutato
        with pytest.raises(ArtefactValidationError):
            security.check_extension(name)

    @pytest.mark.parametrize("name", ["FaBiO.RDF", "onto.TTL", "x.OWL"])
    def test_uppercase_extension_accepted(self, name):
        security.check_extension(name)  # lowercased internamente

    def test_leading_double_extension_accepted_on_name(self):
        # rat.py.rdf: ultima estensione .rdf -> passa l'extension check.
        # NON e' un buco: e' il parser RDF il gate vero (vedi test sotto).
        security.check_extension("rat.py.rdf")


class TestDisguisedNonRdf:
    """File di testo validi ma NON RDF: passano is_text/extension, li ferma il parser."""

    def test_python_disguised_as_rdf_fails_to_parse(self, tmp_path):
        f = tmp_path / "rat.py.rdf"
        f.write_text("import os\nos.system('rm -rf /')\n", encoding="utf-8")
        # e' testo UTF-8 valido -> check_is_text passerebbe; l'estensione (.rdf) passa.
        # Ma non e' RDF -> nessun parser lo accetta -> ArtefactLoadError.
        # Il codice Python NON viene mai eseguito, solo scartato.
        with pytest.raises(ArtefactLoadError):
            Loader()._load_from_local_file(str(f))

    def test_empty_file_rejected_as_empty_graph(self, tmp_path):
        f = tmp_path / "empty.rdf"
        f.write_bytes(b"")
        with pytest.raises(ArtefactLoadError):
            Loader().load(str(f))


class TestUrlSizeGuards:
    """Protezione size sul path URL (streaming + Content-Length dichiarato)."""

    def test_streaming_size_guard(self, monkeypatch):
        monkeypatch.setattr(security, "MAX_BYTES", 16)
        resp = FakeResponse(status_code=200, headers={}, body=b"x" * 64)
        monkeypatch.setattr("lode.reader.loader.requests.get", make_fake_get([resp]))
        with pytest.raises(ArtefactValidationError):
            Loader()._load_from_url_with_content_negotiation("http://93.184.216.34/big.ttl")

    def test_declared_content_length_rejected(self, monkeypatch):
        monkeypatch.setattr(security, "MAX_BYTES", 16)
        resp = FakeResponse(status_code=200, headers={"Content-Length": "1000"}, body=b"x")
        monkeypatch.setattr("lode.reader.loader.requests.get", make_fake_get([resp]))
        with pytest.raises(ArtefactValidationError):
            Loader()._load_from_url_with_content_negotiation("http://8.8.8.8/big.ttl")

# ----------------------------------------------------------------------
#  Loader.load - empty graph guard
# ----------------------------------------------------------------------
class TestEmptyGraphGuard:

    def test_empty_graph_rejected(self, tmp_path):
        # syntactically valid turtle with zero triples (only a prefix declaration)
        f = tmp_path / "empty.ttl"
        f.write_text("@prefix ex: <http://example.org/> .\n", encoding="utf-8")
        loader = Loader()
        with pytest.raises(ArtefactLoadError):
            loader.load(str(f))


# ----------------------------------------------------------------------
#  check_safe_xml  (XXE / billion laughs hardening)
# ----------------------------------------------------------------------
class TestCheckSafeXml:

    def test_external_entity_rejected(self):
        with pytest.raises(ArtefactValidationError):
            security.check_safe_xml(
                '<!DOCTYPE r [ <!ENTITY x SYSTEM "file:///etc/passwd"> ]><r>&x;</r>'
            )

    def test_external_dtd_public_rejected(self):
        with pytest.raises(ArtefactValidationError):
            security.check_safe_xml(
                '<!DOCTYPE r PUBLIC "-//x//EN" "http://evil/x.dtd"><r/>'
            )

    def test_parameter_entity_rejected(self):
        with pytest.raises(ArtefactValidationError):
            security.check_safe_xml('<!DOCTYPE r [ <!ENTITY % p "foo"> ]><r/>')

    def test_billion_laughs_rejected(self):
        payload = (
            '<!DOCTYPE lolz [\n'
            '  <!ENTITY lol "lol">\n'
            '  <!ENTITY lol2 "&lol;&lol;&lol;">\n'
            ']>\n<lolz>&lol2;</lolz>'
        )
        with pytest.raises(ArtefactValidationError):
            security.check_safe_xml(payload)

    def test_simple_internal_entities_allowed(self):
        # Protege-style namespace entities must NOT be blocked.
        security.check_safe_xml(
            '<!DOCTYPE rdf:RDF [ <!ENTITY owl "http://www.w3.org/2002/07/owl#" > ]>'
            '<rdf:RDF/>'
        )

    def test_no_doctype_allowed(self):
        security.check_safe_xml('<?xml version="1.0"?><rdf:RDF/>')

    def test_turtle_allowed(self):
        security.check_safe_xml('@prefix ex: <http://e/> . ex:a a ex:B .')


# ----------------------------------------------------------------------
#  read_upload_capped  (chunked upload read with size cap)
# ----------------------------------------------------------------------
class _FakeUpload:
    """Mimics starlette.UploadFile: exposes an async read(size)."""
    def __init__(self, data: bytes):
        self._buf = io.BytesIO(data)

    async def read(self, size: int = -1) -> bytes:
        return self._buf.read(size)


class TestReadUploadCapped:

    def test_within_limit_returns_all(self):
        data = b"x" * 1000
        out = asyncio.run(security.read_upload_capped(_FakeUpload(data), max_bytes=2000))
        assert out == data

    def test_over_limit_rejected(self):
        with pytest.raises(ArtefactValidationError):
            asyncio.run(security.read_upload_capped(_FakeUpload(b"x" * 5000), max_bytes=1000))


# ----------------------------------------------------------------------
#  check_extension - missing filename guard
# ----------------------------------------------------------------------
class TestCheckExtensionMissing:

    @pytest.mark.parametrize("name", [None, ""])
    def test_missing_filename_rejected(self, name):
        with pytest.raises(ArtefactValidationError):
            security.check_extension(name)


# ----------------------------------------------------------------------
#  check_url_safe - extra SSRF hardening (multicast / unspecified / IPv4-mapped)
# ----------------------------------------------------------------------
class TestSsrfHardening:

    @pytest.mark.parametrize("ip", [
        "224.0.0.1",            # multicast
        "0.0.0.0",              # unspecified
        "::ffff:127.0.0.1",     # IPv4-mapped IPv6 loopback
    ])
    def test_extra_internal_addresses_rejected(self, monkeypatch, ip):
        monkeypatch.setattr(
            "lode.reader.security.socket.getaddrinfo",
            lambda host, port, *a, **k: [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))
            ],
        )
        with pytest.raises(ArtefactValidationError):
            security.check_url_safe("http://whatever.example.org/x")
