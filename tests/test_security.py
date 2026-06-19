"""Tests for the lode.security module (upload hardening + anti-SSRF)."""
import asyncio
import io

import pytest

from lode import security
from lode.exceptions import (
    UnsafeURLError,
    UnsupportedMediaError,
    UploadTooLargeError,
    UploadValidationError,
)

VALID_TTL = b"""@prefix ex: <http://example.org/> .
ex:Foo a ex:Bar .
"""

# Legitimate RDF/XML with internal entities (Protege pattern) -> must pass.
VALID_RDFXML_WITH_ENTITIES = b"""<?xml version="1.0"?>
<!DOCTYPE rdf:RDF [
  <!ENTITY owl "http://www.w3.org/2002/07/owl#" >
  <!ENTITY xsd "http://www.w3.org/2001/XMLSchema#" >
]>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
         xmlns:owl="&owl;">
  <owl:Ontology rdf:about="http://example.org/o"/>
</rdf:RDF>
"""


# ----------------------------------------------------------------------------
#  Binary rejection
# ----------------------------------------------------------------------------
@pytest.mark.parametrize("blob", [
    b"%PDF-1.7\n...",                       # PDF
    b"PK\x03\x04rest-of-zip",               # ZIP/Office
    b"\x1f\x8b\x08compressed",              # gzip
    b"\x7fELF\x02\x01\x01",                 # ELF
    b"\x89PNG\r\n\x1a\n",                   # PNG
    b"MZ\x90\x00",                          # Windows exe
])
def test_binary_magic_bytes_rejected(blob):
    with pytest.raises(UploadValidationError):
        security.assert_not_binary(blob)


def test_null_bytes_rejected():
    with pytest.raises(UploadValidationError):
        security.assert_not_binary(b"some text \x00\x00 with nulls")


def test_invalid_utf8_rejected():
    with pytest.raises(UploadValidationError):
        security.assert_not_binary(b"\xff\xfe\x00\x80\x81\x82 not utf8")


def test_empty_file_rejected():
    with pytest.raises(UploadValidationError):
        security.assert_not_binary(b"")


def test_valid_text_accepted():
    text = security.assert_not_binary(VALID_TTL)
    assert "ex:Foo" in text


# ----------------------------------------------------------------------------
#  Extensions
# ----------------------------------------------------------------------------
@pytest.mark.parametrize("name", ["onto.ttl", "x.rdf", "y.OWL", "data.jsonld"])
def test_allowed_extension_ok(name):
    security.assert_allowed_extension(name)  # does not raise


@pytest.mark.parametrize("name", ["malware.exe", "doc.pdf", "archive.zip", "image.png"])
def test_disallowed_extension_rejected(name):
    with pytest.raises(UnsupportedMediaError):
        security.assert_allowed_extension(name)


# ----------------------------------------------------------------------------
#  Hardening XML (XXE / billion laughs)
# ----------------------------------------------------------------------------
def test_xml_external_entity_rejected():
    payload = (
        '<?xml version="1.0"?>\n'
        '<!DOCTYPE foo [ <!ENTITY xxe SYSTEM "file:///etc/passwd"> ]>\n'
        '<foo>&xxe;</foo>'
    )
    with pytest.raises(UploadValidationError):
        security.assert_safe_xml(payload)


def test_xml_parameter_entity_rejected():
    payload = (
        '<?xml version="1.0"?>\n'
        '<!DOCTYPE foo [ <!ENTITY % pe SYSTEM "http://evil/x"> %pe; ]>\n'
        '<foo/>'
    )
    with pytest.raises(UploadValidationError):
        security.assert_safe_xml(payload)


def test_billion_laughs_rejected():
    payload = (
        '<?xml version="1.0"?>\n'
        '<!DOCTYPE lolz [\n'
        '  <!ENTITY lol "lol">\n'
        '  <!ENTITY lol2 "&lol;&lol;&lol;">\n'
        '  <!ENTITY lol3 "&lol2;&lol2;&lol2;">\n'
        ']>\n'
        '<lolz>&lol3;</lolz>'
    )
    with pytest.raises(UploadValidationError):
        security.assert_safe_xml(payload)


def test_simple_internal_entities_allowed():
    # Simple internal entities (namespaces) must not be blocked.
    security.assert_safe_xml(VALID_RDFXML_WITH_ENTITIES.decode("utf-8"))


def test_xml_without_doctype_allowed():
    security.assert_safe_xml('<?xml version="1.0"?><rdf:RDF/>')


# ----------------------------------------------------------------------------
#  validate_upload_bytes (orchestrator)
# ----------------------------------------------------------------------------
def test_validate_upload_bytes_ok():
    assert security.validate_upload_bytes(VALID_TTL, "onto.ttl")


def test_validate_upload_bytes_bad_extension():
    with pytest.raises(UnsupportedMediaError):
        security.validate_upload_bytes(VALID_TTL, "onto.exe")


# ----------------------------------------------------------------------------
#  Size limit (read_upload_capped)
# ----------------------------------------------------------------------------
class _FakeUpload:
    """Mimics starlette.UploadFile: exposes an async read(size)."""
    def __init__(self, data: bytes):
        self._buf = io.BytesIO(data)

    async def read(self, size: int = -1) -> bytes:
        return self._buf.read(size)


def test_read_upload_capped_within_limit():
    data = b"x" * 1000
    out = asyncio.run(security.read_upload_capped(_FakeUpload(data), max_bytes=2000))
    assert out == data


def test_read_upload_capped_too_large():
    data = b"x" * 5000
    with pytest.raises(UploadTooLargeError):
        asyncio.run(security.read_upload_capped(_FakeUpload(data), max_bytes=1000))


# ----------------------------------------------------------------------------
#  Anti-SSRF
# ----------------------------------------------------------------------------
@pytest.mark.parametrize("url", [
    "http://127.0.0.1/x",
    "http://localhost/x",            # resolves to loopback
    "http://169.254.169.254/latest", # cloud metadata (link-local)
    "http://10.0.0.5/x",
    "http://192.168.1.1/x",
    "http://[::1]/x",
])
def test_ssrf_internal_url_rejected(url):
    with pytest.raises(UnsafeURLError):
        security.assert_safe_url(url)


@pytest.mark.parametrize("url", [
    "file:///etc/passwd",
    "ftp://example.org/x",
    "gopher://example.org/x",
])
def test_ssrf_bad_scheme_rejected(url):
    with pytest.raises(UnsafeURLError):
        security.assert_safe_url(url)


def test_ssrf_public_url_allowed(monkeypatch):
    # Force DNS resolution to a public IP so the test does not depend on network.
    def fake_getaddrinfo(host, port, *args, **kwargs):
        return [(2, 1, 6, "", ("93.184.216.34", port))]  # example.org
    monkeypatch.setattr(security.socket, "getaddrinfo", fake_getaddrinfo)
    security.assert_safe_url("https://example.org/onto.ttl")  # does not raise
