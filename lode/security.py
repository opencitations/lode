"""
lode.security - Security controls for untrusted input.

Single place for the defenses applied to user-supplied artefacts (file
uploads) and to artefacts fetched from URLs (the GET endpoint and
`owl:imports`/closure):

  * size limit (anti-DoS / memory exhaustion)
  * rejection of binary / non-text files (RDF is always text)
  * extension allowlist
  * XML hardening against XXE and entity-expansion (billion laughs)
  * anti-SSRF protection on remote fetches (blocks internal/private hosts)

Every function that fails raises a LODEError subclass with `http_status` set,
so the API can map the error to the correct status code.
"""
from __future__ import annotations

import ipaddress
import os
import re
import socket
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests

from lode.exceptions import (
    ArtefactLoadError,
    UnsafeURLError,
    UnsupportedMediaError,
    UploadTooLargeError,
    UploadValidationError,
)

# ----------------------------------------------------------------------------
#  CONFIGURATION (override via environment variables)
# ----------------------------------------------------------------------------
def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


# Maximum size of an upload (default 10 MB).
MAX_UPLOAD_BYTES = _env_int("LODE_MAX_UPLOAD_MB", 10) * 1024 * 1024
# Maximum size of an artefact fetched from a URL/import (default 20 MB).
MAX_REMOTE_BYTES = _env_int("LODE_MAX_REMOTE_MB", 20) * 1024 * 1024
# Maximum number of redirects followed during a remote fetch.
MAX_REDIRECTS = _env_int("LODE_MAX_REDIRECTS", 5)
# Maximum number of <!ENTITY> declarations tolerated inside a DOCTYPE.
MAX_ENTITY_DECLARATIONS = _env_int("LODE_MAX_XML_ENTITIES", 100)

# When enabled, the API may show the full traceback (development only).
DEBUG = os.getenv("LODE_DEBUG", "").strip().lower() in ("1", "true", "yes", "on")

# Extensions accepted for uploads (a "soft" check: the extension is spoofable,
# the real defense is the binary rejection + the rdflib parsing).
ALLOWED_EXTENSIONS = {
    ".rdf", ".owl", ".ttl", ".n3", ".nt", ".nq",
    ".xml", ".jsonld", ".json", ".trig", ".trix",
}

# Control characters that are legitimate in a text file.
_ALLOWED_CONTROL = {"\t", "\n", "\r", "\f", "\v"}

# Magic-byte signatures of common binary/archive/executable formats: if an
# upload starts with one of these it is rejected up front with a clear message.
_BINARY_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"%PDF", "PDF"),
    (b"PK\x03\x04", "ZIP/Office"),
    (b"PK\x05\x06", "ZIP"),
    (b"PK\x07\x08", "ZIP"),
    (b"\x1f\x8b", "gzip"),
    (b"BZh", "bzip2"),
    (b"\xfd7zXZ\x00", "xz"),
    (b"7z\xbc\xaf\x27\x1c", "7-Zip"),
    (b"Rar!\x1a\x07", "RAR"),
    (b"\x89PNG\r\n\x1a\n", "PNG"),
    (b"\xff\xd8\xff", "JPEG"),
    (b"GIF87a", "GIF"),
    (b"GIF89a", "GIF"),
    (b"\x7fELF", "ELF executable"),
    (b"MZ", "Windows executable"),
    (b"\xca\xfe\xba\xbe", "Mach-O/Java class"),
    (b"\xcf\xfa\xed\xfe", "Mach-O"),
    (b"\xce\xfa\xed\xfe", "Mach-O"),
    (b"\xfe\xed\xfa\xce", "Mach-O"),
    (b"\xfe\xed\xfa\xcf", "Mach-O"),
    (b"\x00\x00\x01\x00", "icon/binary"),
    (b"%!PS", "PostScript"),
    (b"SQLite format 3\x00", "SQLite database"),
)

# A general entity reference (e.g. &lol1;), excluding numeric char-refs (&#65;).
_ENTITY_REF_RE = re.compile(r"&(?!#)[A-Za-z_][\w.\-]*;")


# ----------------------------------------------------------------------------
#  CAPPED UPLOAD READ
# ----------------------------------------------------------------------------
async def read_upload_capped(upload, max_bytes: int = MAX_UPLOAD_BYTES) -> bytes:
    """Read an `UploadFile` in chunks, stopping as soon as it exceeds `max_bytes`.

    Prevents `await file.read()` from loading an arbitrarily large file into
    memory (a DoS vector).
    """
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise UploadTooLargeError(
                f"File too large: the limit is {max_bytes // (1024 * 1024)} MB.",
                context={"max_bytes": max_bytes},
            )
        chunks.append(chunk)
    return b"".join(chunks)


# ----------------------------------------------------------------------------
#  TEXT DECODING / DETECTION
# ----------------------------------------------------------------------------
def decode_text(data: bytes) -> str:
    """Decode bytes to text, handling BOMs. Raises if it is not valid text."""
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        encoding = "utf-16"
    elif data.startswith(b"\xef\xbb\xbf"):
        encoding = "utf-8-sig"
    else:
        encoding = "utf-8"
    try:
        return data.decode(encoding)
    except (UnicodeDecodeError, LookupError):
        raise UploadValidationError(
            "The file is not valid text (UTF-8/UTF-16): it looks like a binary file.",
        )


def looks_like_text(text: str) -> bool:
    """Heuristic: True if a sample of the text has no NUL and few
    non-printable control characters."""
    sample = text[:8192]
    if not sample:
        return True
    if "\x00" in sample:
        return False
    control = sum(
        1 for ch in sample if ord(ch) < 32 and ch not in _ALLOWED_CONTROL
    )
    return (control / len(sample)) <= 0.05


def assert_not_binary(data: bytes) -> str:
    """Reject binary files and return the decoded text.

    1) known magic-byte signature -> reject immediately
    2) not decodable               -> reject
    3) too many control chars / NUL -> reject
    """
    if not data:
        raise UploadValidationError("Empty file.")

    head = data[:64]
    for signature, label in _BINARY_SIGNATURES:
        if head.startswith(signature):
            raise UploadValidationError(
                f"Binary file not allowed (detected: {label}). "
                "Only text-based RDF artefacts are accepted."
            )

    text = decode_text(data)
    if not looks_like_text(text):
        raise UploadValidationError(
            "The file contains binary data / control characters: it is not a "
            "valid text-based RDF artefact."
        )
    return text


# ----------------------------------------------------------------------------
#  EXTENSION
# ----------------------------------------------------------------------------
def assert_allowed_extension(filename: Optional[str]) -> None:
    """Check that the file extension is in the allowlist."""
    if not filename:
        return  # no filename: rely on binary rejection + parsing instead
    _, _, ext = filename.lower().rpartition(".")
    ext = "." + ext if ext else ""
    if ext not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise UnsupportedMediaError(
            f"Extension not allowed ({ext or 'missing'}). "
            f"Accepted formats: {allowed}.",
            context={"filename": filename},
        )


# ----------------------------------------------------------------------------
#  XML HARDENING (XXE / billion laughs)
# ----------------------------------------------------------------------------
def assert_safe_xml(text: str) -> None:
    """Block dangerous XML documents while keeping simple internal entities.

    Legitimate RDF/XML (e.g. Protege exports) often uses a DOCTYPE with internal
    entities to abbreviate namespaces, so we cannot forbid every DTD. Instead we
    forbid the patterns that are actually exploitable:

      * EXTERNAL DTD/entities (SYSTEM/PUBLIC)   -> XXE, file read, SSRF
      * PARAMETER entities (<!ENTITY % ...>)    -> advanced XXE
      * entities referencing other entities      -> billion laughs
      * too many entity declarations             -> abuse / expansion
    """
    lowered = text.lower()
    idx = lowered.find("<!doctype")
    if idx == -1:
        return  # no DOCTYPE => no DTD surface

    # Isolate the DOCTYPE internal subset (between '[' and ']') if present.
    end = text.find(">", idx)
    bracket = text.find("[", idx)
    if bracket != -1:
        close = text.find("]", bracket)
        subset = text[bracket : close + 1 if close != -1 else len(text)]
    else:
        subset = text[idx : end + 1 if end != -1 else len(text)]
    subset_lower = subset.lower()

    if "system" in subset_lower or "public" in subset_lower:
        raise UploadValidationError(
            "XML document with an external DTD/entity is not allowed (XXE risk)."
        )

    if "<!entity %" in subset_lower or re.search(r"<!entity\s+%", subset_lower):
        raise UploadValidationError(
            "XML document with a parameter entity is not allowed (XXE risk)."
        )

    entity_decls = re.findall(
        r"<!entity\s+[^>]*>", subset, flags=re.IGNORECASE | re.DOTALL
    )
    if len(entity_decls) > MAX_ENTITY_DECLARATIONS:
        raise UploadValidationError(
            "Too many XML entity declarations (possible entity-expansion attack)."
        )

    for decl in entity_decls:
        # The entity value must not reference other entities (billion laughs).
        value_match = re.search(r"""=?\s*(['"])(.*?)\1""", decl, flags=re.DOTALL)
        value = value_match.group(2) if value_match else decl
        if _ENTITY_REF_RE.search(value):
            raise UploadValidationError(
                "Nested XML entities are not allowed (possible billion laughs)."
            )


# ----------------------------------------------------------------------------
#  FULL UPLOAD VALIDATION
# ----------------------------------------------------------------------------
def validate_upload_bytes(data: bytes, filename: Optional[str] = None) -> str:
    """Run every upload check and return the decoded text.

    Raises an UploadValidationError subclass on the first failed check.
    """
    assert_allowed_extension(filename)
    text = assert_not_binary(data)
    assert_safe_xml(text)
    return text


# ----------------------------------------------------------------------------
#  ANTI-SSRF
# ----------------------------------------------------------------------------
def _ip_is_blocked(ip: ipaddress._BaseAddress) -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local      # includes 169.254.169.254 (cloud metadata)
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def assert_safe_url(url: str) -> None:
    """Raise UnsafeURLError if the URL points to a non-public destination.

    Resolves the hostname and rejects if *any* resolved address is internal
    (private, loopback, link-local, reserved, multicast).
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise UnsafeURLError(
            f"URL scheme not allowed: {parsed.scheme or '(empty)'}.",
            context={"url": url},
        )

    host = parsed.hostname
    if not host:
        raise UnsafeURLError("URL without a valid host.", context={"url": url})

    # If the host is already a literal IP, check it directly.
    try:
        literal = ipaddress.ip_address(host)
        if _ip_is_blocked(literal):
            raise UnsafeURLError(
                "URL to an internal/private address is not allowed.",
                context={"url": url, "ip": str(literal)},
            )
        return
    except ValueError:
        pass  # not a literal IP: resolve via DNS

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise UnsafeURLError(
            f"Could not resolve host: {host}.",
            context={"url": url, "error": str(exc)},
        )

    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if _ip_is_blocked(ip):
            raise UnsafeURLError(
                "URL to an internal/private address is not allowed.",
                context={"url": url, "ip": str(ip)},
            )


def safe_get(
    url: str,
    headers: Optional[dict] = None,
    timeout: int = 10,
    max_redirects: int = MAX_REDIRECTS,
    max_bytes: int = MAX_REMOTE_BYTES,
) -> requests.Response:
    """`requests.get` with anti-SSRF protection and a size cap.

    Follows redirects manually, re-validating *every hop* (a redirect to an
    internal host would otherwise be followed by requests), and aborts the
    download if it exceeds `max_bytes`.
    """
    current = url
    for _ in range(max_redirects + 1):
        assert_safe_url(current)
        resp = requests.get(
            current,
            headers=headers,
            timeout=timeout,
            allow_redirects=False,
            stream=True,
        )
        if resp.status_code in (301, 302, 303, 307, 308):
            location = resp.headers.get("Location")
            resp.close()
            if not location:
                raise UnsafeURLError(
                    "Redirect without a Location header.", context={"url": current}
                )
            current = urljoin(current, location)
            continue

        # Final response: read with a size limit.
        content = bytearray()
        for chunk in resp.iter_content(8192):
            content += chunk
            if len(content) > max_bytes:
                resp.close()
                raise ArtefactLoadError(
                    f"Remote artefact too large "
                    f"(> {max_bytes // (1024 * 1024)} MB).",
                    context={"url": current},
                )
        resp._content = bytes(content)
        return resp

    raise UnsafeURLError("Too many redirects.", context={"url": url})
