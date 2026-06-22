"""Security validation for incoming semantic artefacts."""
import os
import re
import socket
import ipaddress
from urllib.parse import urlparse
from lode.exceptions import ArtefactValidationError


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


MAX_BYTES = _env_int("LODE_MAX_UPLOAD_MB", 10) * 1024 * 1024  # 10 MB default
MAX_ENTITY_DECLARATIONS = _env_int("LODE_MAX_XML_ENTITIES", 100)
MAX_DTD_SUBSET = 50 * 1024  # bytes; a legitimate DOCTYPE internal subset is tiny
ALLOWED_EXTENSIONS = {".rdf", ".owl", ".ttl", ".n3", ".nt", ".jsonld", ".xml"}
ALLOWED_SCHEMES = {"http", "https"}

# Control characters that are legitimate in a text file.
_ALLOWED_CONTROL = {"\t", "\n", "\r", "\f", "\v"}

# Magic-byte signatures of common binary/archive/executable formats.
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
    (b"%!PS", "PostScript"),
    (b"SQLite format 3\x00", "SQLite database"),
)

# A general entity reference (e.g. &lol1;), excluding numeric char-refs (&#65;).
_ENTITY_REF_RE = re.compile(r"&(?!#)[A-Za-z_][\w.\-]*;")


def check_size(num_bytes: int) -> None:
    if num_bytes > MAX_BYTES:
        raise ArtefactValidationError("File too large", context={"bytes": num_bytes, "max": MAX_BYTES})

def check_extension(name: str) -> None:
    if not name:
        raise ArtefactValidationError("Missing filename", context={"name": name})
    ext = os.path.splitext(urlparse(name).path)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ArtefactValidationError("Extension not allowed", context={"ext": ext})

def check_url_safe(url: str) -> None:
    """Block non-http schemes and SSRF toward private/internal hosts."""
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise ArtefactValidationError("Scheme not allowed", context={"scheme": parsed.scheme})
    host = parsed.hostname
    if not host:
        raise ArtefactValidationError("Missing host", context={"url": url})
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        raise ArtefactValidationError("Cannot resolve host", context={"host": host})
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        # IPv4-mapped IPv6 (e.g. ::ffff:127.0.0.1) would bypass the v4 checks below.
        if getattr(ip, "ipv4_mapped", None):
            ip = ip.ipv4_mapped
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            raise ArtefactValidationError("Blocked address", context={"host": host, "ip": str(ip)})

def check_is_text(data: bytes) -> None:
    """RDF serializations are text. Reject binary blobs."""
    if not data:
        raise ArtefactValidationError("Empty artefact")
    # 1) known binary/archive/executable signature -> reject up front
    head = data[:64]
    for signature, label in _BINARY_SIGNATURES:
        if head.startswith(signature):
            raise ArtefactValidationError(
                "Not a text/ASCII artefact (binary content)", context={"detected": label}
            )
    # 2) NUL byte is a strong binary signal
    if b"\x00" in data:
        raise ArtefactValidationError("Not a text/ASCII artefact (binary content)")
    # 3) must be valid UTF-8 (handle a leading BOM)
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ArtefactValidationError("Not a text/ASCII artefact")
    # 4) too many non-printable control chars -> not a real RDF serialization
    sample = text[:8192]
    if sample:
        control = sum(1 for ch in sample if ord(ch) < 32 and ch not in _ALLOWED_CONTROL)
        if control / len(sample) > 0.05:
            raise ArtefactValidationError("Not a text/ASCII artefact (control characters)")

def check_safe_xml(text: str) -> None:
    """Block dangerous XML documents while keeping simple internal entities.

    Legitimate RDF/XML (e.g. Protege exports) often uses a DOCTYPE with internal
    entities to abbreviate namespaces, so we cannot forbid every DTD. We forbid
    only the exploitable patterns:

      * EXTERNAL DTD/entities (SYSTEM/PUBLIC)   -> XXE, file read, SSRF
      * PARAMETER entities (<!ENTITY % ...>)    -> advanced XXE
      * entities referencing other entities      -> billion laughs
      * too many entity declarations             -> abuse / expansion
    """
    lowered = text.lower()
    idx = lowered.find("<!doctype")
    if idx == -1:
        return  # no DOCTYPE => no DTD surface

    end = text.find(">", idx)
    bracket = text.find("[", idx)
    if bracket != -1:
        close = text.find("]", bracket)
        subset = text[bracket: close + 1 if close != -1 else len(text)]
    else:
        subset = text[idx: end + 1 if end != -1 else len(text)]

    # A real DOCTYPE internal subset is tiny. An oversized one is both suspicious
    # and a ReDoS vector for the scans below, so reject it outright.
    if len(subset) > MAX_DTD_SUBSET:
        raise ArtefactValidationError("DOCTYPE internal subset too large")

    subset_lower = subset.lower()
    if "system" in subset_lower or "public" in subset_lower:
        raise ArtefactValidationError("XML with external DTD/entity not allowed (XXE risk)")

    # Linear scan: '[^>]*>' matches up to each declaration's closing '>'. We avoid
    # '\s+[^>]*' (overlapping quantifiers -> polynomial backtracking / ReDoS) and
    # do the per-declaration analysis with plain string ops instead of regex.
    entity_decls = re.findall(r"<!entity\s[^>]*>", subset, flags=re.IGNORECASE)
    if len(entity_decls) > MAX_ENTITY_DECLARATIONS:
        raise ArtefactValidationError("Too many XML entity declarations (entity-expansion)")
    for decl in entity_decls:
        body = decl[len("<!entity"):].lstrip()
        if body.startswith("%"):  # parameter entity: <!ENTITY % name ...>
            raise ArtefactValidationError("XML parameter entity not allowed (XXE risk)")
        if _ENTITY_REF_RE.search(decl):  # value references another entity
            raise ArtefactValidationError("Nested XML entities not allowed (billion laughs)")

async def read_upload_capped(upload, max_bytes: int = MAX_BYTES) -> bytes:
    """Read an UploadFile in chunks, aborting as soon as it exceeds max_bytes.

    Avoids loading an arbitrarily large upload fully into memory before the size
    check (which `await file.read()` would do).
    """
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise ArtefactValidationError("File too large", context={"max": max_bytes})
        chunks.append(chunk)
    return b"".join(chunks)
