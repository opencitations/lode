"""Loading and validation of one RDF document, from a local file or from a URL.

Every security check on remote content (SSRF, size, text-only, XXE) runs here,
before the RDF parser sees any byte. The functions keep no state: naming the artefact
and loading the documents it imports belong to lode.reader.pipeline.
"""
import os
from typing import Optional
from urllib.parse import urlparse, urljoin

import requests
from rdflib import Graph

from lode import security
from lode.exceptions import (ArtefactLoadError, ArtefactNotFoundError,
                             ArtefactUnavailableError, ArtefactValidationError)
from lode.helpers.rdf import PARSE_FORMATS, parse_any


# ==========================================================================
# 1. ENTRY POINT
# ==========================================================================
def load_document(source: str) -> Graph:
    """Load one RDF document from a local file or an http(s) URL and return its graph.

    A URL goes through content negotiation and every security check. A value carrying
    another scheme (file:, ftp:, ...) is refused: it must not be silently treated as a
    local path, while bare local paths (no scheme) stay allowed for the CLI. Raises
    ArtefactLoadError when the document parses to an empty graph.
    """
    if _is_url(source):
        graph = _load_from_url_with_content_negotiation(source)

    elif os.path.isfile(source):
        graph = _load_from_local_file(source)
    else:
        # A value carrying a URL scheme that is not http(s) (file:, ftp:, ...)
        # must not be silently treated as a local path. Bare local paths
        # (no scheme) are still allowed here for the CLI.
        scheme = urlparse(source).scheme
        if scheme:
            raise ArtefactValidationError(
                "URL scheme not allowed; use http(s)://host",
                context={"scheme": scheme},
            )
        graph = _load_from_local_file(source)

    if len(graph) == 0:
        raise ArtefactLoadError(
            "Parsed graph is empty (wrong URL or not an RDF resource)",
            context={"source": source}
        )
    return graph


# ==========================================================================
# 2. URL
# ==========================================================================
def _load_from_url_with_content_negotiation(url: str) -> Graph:
    """RDF graph loading with content-negotiation for semantic artefact loaded from URL"""

    security.check_url_safe(url)  # SECURITY: url validation (anti-SSRF), before downlaod

    headers = {
        "Accept": (
            "text/turtle, application/rdf+xml, application/ld+json, "
            "application/n-triples, application/n-quads, */*;q=0.1"
        ),
        # Sent on every redirect hop too, since this dict is reused there.
        "User-Agent": security.USER_AGENT,
    }

    response = None
    try:
        # SECURITY: fetch with per-hop URL validation (anti-SSRF); manual redirects, no auto-follow into unchecked hosts
        response = _fetch_following_redirects(url, headers)

        # Error: Cannot Load RDF. A 5xx says the host is broken right now,
        # not that the artefact is missing: telling the two apart is the
        # difference between "check your URL" and "try again later".
        if response.status_code != 200:
            if response.status_code >= 500:
                raise ArtefactUnavailableError(
                    "The remote server is not responding, please try again later",
                    context={"url": url, "http_status": response.status_code}
                )
            raise ArtefactNotFoundError(
                "Cannot load provided Semantic Artefact",
                context={"url": url, "http_status": response.status_code}
            )

        # Reject HTML/XHTML pages before downloading: servers answer with a
        # human-readable page when no RDF serialization is available.
        content_type = response.headers.get("Content-Type", "").lower()
        mime = content_type.split(";")[0].strip()
        if mime in ("text/html", "application/xhtml+xml"):
            response.close()
            raise ArtefactLoadError(
                "Resource is an HTML page, not an RDF serialization",
                context={"url": url, "content_type": mime},
            )

        # SECURITY: reject by declared Content-Length before downloading the body
        declared = response.headers.get("Content-Length")
        if declared and declared.isdigit():
            security.check_size(int(declared))

        # SECURITY: stop if file > 10MB even without Content-Length
        raw = b""
        for chunk in response.iter_content(8192): # 8kb at the time in iteration
            raw += chunk
            if len(raw) > security.MAX_BYTES:
                security.check_size(len(raw))

        # SECURITY: checks the file is text not binary
        security.check_is_text(raw)

        # Proceed with encoding
        content = raw.decode("utf-8")

        # SECURITY: block XXE / entity-expansion on remote artefacts and owl:imports
        security.check_safe_xml(content)

        content_type = response.headers.get("Content-Type", "").lower()

        # Format guessed from HTTP Content-Type (content negotiation handler)
        graph = parse_any(content, preferred=_guess_format_from_content_type(content_type))
        if graph is None:
            raise ArtefactLoadError("Could not parse RDF after content negotiation",
                                    context={"url": url, "formats_tried": list(PARSE_FORMATS)})
        return graph

    # Error (Fallback): Cannot Load RDF
    except requests.RequestException as e:
        raise ArtefactNotFoundError(
            "Network error fetching artefact",
            context={"url": url, "original_error": str(e)}
        )


def _fetch_following_redirects(url: str, headers: dict, max_redirects: int = security.MAX_REDIRECTS):
    """Follow URLs redirects manually, validating each hop via security.check_url_safe. Returns final response.

    The default hop limit comes from security.MAX_REDIRECTS (env LODE_MAX_REDIRECTS)."""
    current = url
    for _ in range(max_redirects):
        security.check_url_safe(current)
        response = requests.get(current, headers=headers, timeout=10,
                                stream=True, allow_redirects=False)
        # Validate the IP we ACTUALLY connected to, before reading anything:
        # defeats DNS rebinding between check_url_safe above and this connect.
        _verify_peer_ip(response)
        if response.status_code in (301, 302, 303, 307, 308):
            location = response.headers.get("Location")
            response.close()
            if not location:
                raise ArtefactLoadError("Redirect without Location", context={"url": current})
            current = urljoin(current, location)
            continue
        return response
    raise ArtefactLoadError("Too many redirects", context={"url": url})


def _verify_peer_ip(response) -> None:
    """Re-check the SSRF policy against the socket's real peer IP. If it
    cannot be determined (e.g. mocked in tests) fall back to the per-hop
    check_url_safe already done before connecting."""
    ip = _peer_ip(response)
    if ip is None:
        return
    try:
        security.check_ip_safe(ip)
    except ArtefactValidationError:
        response.close()
        raise


def _peer_ip(response):
    """Best-effort extraction of the connected peer IP from a streamed
    requests response (reaches into urllib3 internals, hence defensive)."""
    try:
        return response.raw._connection.sock.getpeername()[0]
    except Exception:
        return None


# ==========================================================================
# 3. LOCAL FILE
# ==========================================================================
def _load_from_local_file(path: str) -> Graph:
    """Parse a local file, trying every known RDF format.

    Raises ArtefactLoadError if no format can parse it. The caller is expected
    to have excluded URLs: this function opens `path` on the local disk.
    """
    with open(path, "rb") as f:
        raw = f.read()
    graph = parse_any(raw)
    if graph is None:
        raise ArtefactLoadError("Could not parse RDF with any known format",
                                context={"path": path, "formats_tried": list(PARSE_FORMATS)})
    return graph


# ==========================================================================
# 4. HELPERS
# ==========================================================================
def _is_url(s: str) -> bool:
    """Return True only for http(s) URLs; other schemes are not treated as URLs."""
    try:
        return urlparse(s).scheme in ("http", "https")
    except Exception:
        return False


def _guess_format_from_content_type(content_type: str) -> Optional[str]:
    """Map an HTTP Content-Type to an rdflib format name, or None when unknown.

    The result is only a hint: parse_any still falls back to the other formats.
    """
    if "text/turtle" in content_type or "application/x-turtle" in content_type:
        return "turtle"
    if "application/rdf+xml" in content_type:
        return "xml"
    if "application/ld+json" in content_type or "json" in content_type:
        return "json-ld"
    if "application/n-triples" in content_type:
        return "nt"
    return None
