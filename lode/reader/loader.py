"""
Reader - Caricamento e validazione file RDF
"""
import requests
from rdflib import Graph
from typing import Dict, Optional
from urllib.parse import urlparse

import lode.reader.modules as modules
from lode.exceptions import ArtefactLoadError, ArtefactNotFoundError


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
        else:
            self._load_from_local_file(source)
        
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

    # ----------------------------------------------------------
    #  CONTENT NEGOTIATION FOR URLS
    # ----------------------------------------------------------
    def _load_from_url_with_content_negotiation(self, url: str) -> None:
        """RDF graph loading with content-negotiation for semantic artefact loaded from URL"""

        headers = {
            "Accept": (
                "text/turtle, application/rdf+xml, application/ld+json, "
                "application/n-triples, application/n-quads, */*;q=0.1"
            )
        }

        try:
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code != 200:
                raise ArtefactNotFoundError(
                    "Cannot load provided Semantic Artefact",
                    context={"url": url, "http_status": response.status_code}
                )

            content = response.text
            content_type = response.headers.get("Content-Type", "").lower()

            # Format guessed from HTTP Content-Type
            guessed_format = self._guess_format_from_content_type(content_type)

            self.graph = Graph()

            # If it recognises the Content-Type → parse directly
            if guessed_format:
                try:
                    self.graph.parse(data=content, format=guessed_format)
                    return 
                except:
                    pass  # fallback below

            # Otherwise, try all formats
            for fmt in ["xml", "application/rdf+xml", "turtle", "json-ld", "nt", "n3"]:
                try:
                    self.graph.parse(data=content, format=fmt)
                    return
                except:
                    continue

            raise ArtefactLoadError(
                "Could not parse RDF after content negotiation",
                context={"url": url, "formats_tried": ["xml", "turtle", "json-ld", "nt", "n3"]}
            )

        except requests.RequestException as e:
            raise ArtefactNotFoundError(
                "Network error fetching artefact",
                context={"url": url, "original_error": str(e)}
            )

    # ----------------------------------------------------------
    #  LOCAL FILE LOADING
    # ----------------------------------------------------------
    def _load_from_local_file(self, path: str) -> Dict[str, any]:
        formats = ['xml', 'turtle', 'n3', 'nt', 'json-ld']

        for fmt in formats:
            try:
                self.graph = Graph()
                self.graph.parse(path, format=fmt)
                return {
                    "success": True,
                    "message": f"{len(self.graph)} triples loaded (format: {fmt})"
                }
            except Exception:
                continue

        return {
            "success": False,
            "message": f"Could not load {path} with any known RDF format"
        }

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
    


