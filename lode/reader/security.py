"""Security validation for incoming semantic artefacts."""
import os
import socket
import ipaddress
from urllib.parse import urlparse
from lode.exceptions import ArtefactValidationError

MAX_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTENSIONS = {".rdf", ".owl", ".ttl", ".n3", ".nt", ".jsonld", ".xml"}
ALLOWED_SCHEMES = {"http", "https"}


def check_size(num_bytes: int) -> None:
    if num_bytes > MAX_BYTES:
        raise ArtefactValidationError("File too large", context={"bytes": num_bytes, "max": MAX_BYTES})

def check_extension(name: str) -> None:
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
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise ArtefactValidationError("Blocked address", context={"host": host, "ip": str(ip)})

def check_is_text(data: bytes) -> None:
    """RDF serializations are text. Reject binary blobs."""
    if b"\x00" in data:
        raise ArtefactValidationError("Not a text/ASCII artefact (binary content)")
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        raise ArtefactValidationError("Not a text/ASCII artefact")