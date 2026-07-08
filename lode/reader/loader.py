"""
Reader - Caricamento e validazione file RDF
"""
import requests
import os
from rdflib import Graph
from typing import Dict, Optional
from urllib.parse import urlparse, urljoin 

import lode.reader.modules as modules
from lode.reader import security
from lode.exceptions import ArtefactLoadError, ArtefactNotFoundError, ArtefactValidationError


class Loader:
    """Gestisce il caricamento di file RDF"""

    def __init__(self, file_path: Optional[str] = None, imported=None, closure=None):
        
        self.graph = Graph()
        self._imported = imported
        self._closure = closure

        if file_path:
            self.load(file_path)

    # ----------------------------------------------------------
    #  MAIN LOAD METHOD
    # ----------------------------------------------------------
    def load(self, source: str) -> None:
        """Loads RDF from local file or from URL with content negotiation"""

        if self._is_url(source):
            self._load_from_url_with_content_negotiation(source)

        # ADD  BY VALE TO FIX WINDOWS LOCAL BUG - COMMENTED FOR PRODUCTION
        # elif os.path.isfile(source):
        #     self._load_from_local_file(source)    
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
            self._load_from_local_file(source)

        if len(self.graph) == 0:
            raise ArtefactLoadError(
                "Parsed graph is empty (wrong URL or not an RDF resource)",
                context={"source": source}
            )
        
        self._apply_modules()
    
    # ----------------------------------------------------------
    #  MODULES MAIN HANDLER
    # ----------------------------------------------------------

    def _apply_modules(self) -> None:

        if self._imported and self._closure:
            self.graph = modules.apply_closure(self.graph)
        if self._imported:
            self.graph = modules.apply_imported(self.graph)
        elif self._closure:
            self.graph = modules.apply_closure(self.graph)

    ## ----------------------------------------------------------
    #  CONTENT NEGOTIATION FOR URLS
    # ----------------------------------------------------------
    def _load_from_url_with_content_negotiation(self, url: str) -> None:
        """RDF graph loading with content-negotiation for semantic artefact loaded from URL"""

        security.check_url_safe(url)  # SECURITY: url validation (anti-SSRF), before downlaod 

        headers = {
            "Accept": (
                "text/turtle, application/rdf+xml, application/ld+json, "
                "application/n-triples, application/n-quads, */*;q=0.1"
            )
        }

        response = None
        try:
            # SECURITY: fetch with per-hop URL validation (anti-SSRF); manual redirects, no auto-follow into unchecked hosts
            response = self._fetch_following_redirects(url, headers)

            # Error: Cannot Load RDF
            if response.status_code != 200:
                raise ArtefactNotFoundError(
                    "Cannot load provided Semantic Artefact",
                    context={"url": url, "http_status": response.status_code}
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
            guessed_format = self._guess_format_from_content_type(content_type)

            self.graph = Graph()

            if guessed_format:
                try:
                    self.graph.parse(data=content, format=guessed_format)
                    return
                except Exception:
                    pass  # fallback below

            for fmt in ["xml", "turtle", "json-ld", "nt", "n3"]:
                try:
                    self.graph.parse(data=content, format=fmt)
                    return
                except Exception:
                    continue

            # Error: Unrecognised RDF format
            raise ArtefactLoadError(  # (5)
                "Could not parse RDF after content negotiation",
                context={"url": url, "formats_tried": ["xml", "turtle", "json-ld", "nt", "n3"]}
            )

        # Error (Fallback): Cannot Load RDF
        except requests.RequestException as e:
            raise ArtefactNotFoundError(
                "Network error fetching artefact",
                context={"url": url, "original_error": str(e)}
            )

    # ----------------------------------------------------------
    #  LOCAL FILE LOADING
    # ----------------------------------------------------------
    def _load_from_local_file(self, path: str) -> None: 

        with open(path, "rb") as f:
            raw = f.read()

        for fmt in ['xml', 'turtle', 'n3', 'nt', 'json-ld']:
            try:
                self.graph = Graph()
                self.graph.parse(data=raw, format=fmt)
                return
            except Exception:
                continue
    
        raise ArtefactLoadError( 
            "Could not parse RDF with any known format",
            context={"path": path}
        )

    # ----------------------------------------------------------
    #  HELPERS
    # ----------------------------------------------------------
    def _is_url(self, s: str) -> bool:
        try:
            return urlparse(s).scheme in ("http", "https")
        except Exception:
            return False

    def _guess_format_from_content_type(self, content_type: str) -> Optional[str]:
        if "text/turtle" in content_type or "application/x-turtle" in content_type:
            return "turtle"
        if "application/rdf+xml" in content_type:
            return "xml"
        if "application/ld+json" in content_type or "json" in content_type:
            return "json-ld"
        if "application/n-triples" in content_type:
            return "nt"
        return None

    def get_graph(self) -> Graph:
        return self.graph
    
    def _fetch_following_redirects(self, url: str, headers: dict, max_redirects: int = security.MAX_REDIRECTS):
        """Follow URLs redirects manually, validating each hop via security.check_url_safe. Returns final response.

        The default hop limit comes from security.MAX_REDIRECTS (env LODE_MAX_REDIRECTS)."""
        current = url
        for _ in range(max_redirects):
            security.check_url_safe(current)
            response = requests.get(current, headers=headers, timeout=10,
                                    stream=True, allow_redirects=False)
            # Validate the IP we ACTUALLY connected to, before reading anything:
            # defeats DNS rebinding between check_url_safe above and this connect.
            self._verify_peer_ip(response)
            if response.status_code in (301, 302, 303, 307, 308):
                location = response.headers.get("Location")
                response.close()
                if not location:
                    raise ArtefactLoadError("Redirect without Location", context={"url": current})
                current = urljoin(current, location)
                continue
            return response
        raise ArtefactLoadError("Too many redirects", context={"url": url})

    def _verify_peer_ip(self, response) -> None:
        """Re-check the SSRF policy against the socket's real peer IP. If it
        cannot be determined (e.g. mocked in tests) fall back to the per-hop
        check_url_safe already done before connecting."""
        ip = self._peer_ip(response)
        if ip is None:
            return
        try:
            security.check_ip_safe(ip)
        except ArtefactValidationError:
            response.close()
            raise

    @staticmethod
    def _peer_ip(response):
        """Best-effort extraction of the connected peer IP from a streamed
        requests response (reaches into urllib3 internals, hence defensive)."""
        try:
            return response.raw._connection.sock.getpeername()[0]
        except Exception:
            return None


