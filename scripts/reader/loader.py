"""
Reader - Caricamento e validazione file RDF
"""
import requests
from rdflib import Graph
from typing import Dict, Optional
from urllib.parse import urlparse


class Loader:
    """Gestisce il caricamento di file RDF"""

    def __init__(self, file_path: Optional[str] = None):
        self.graph = Graph()

        if file_path:
            result = self.load(file_path)
            print(result["message"])

            if not result["success"]:
                raise Exception(result["message"])

    # ----------------------------------------------------------
    #  MAIN LOAD METHOD
    # ----------------------------------------------------------
    def load(self, source: str) -> Dict[str, any]:
        """Carica RDF da file locale o URL con content negotiation"""

        if self._is_url(source):
            return self._load_from_url_with_content_negotiation(source)
        else:
            return self._load_from_local_file(source)

    # ----------------------------------------------------------
    #  CONTENT NEGOTIATION FOR URLS
    # ----------------------------------------------------------
    def _load_from_url_with_content_negotiation(self, url: str) -> Dict[str, any]:
        """Caricamento con content-negotiation per URL"""

        headers = {
            "Accept": (
                "text/turtle, application/rdf+xml, application/ld+json, "
                "application/n-triples, application/n-quads, */*;q=0.1"
            )
        }

        try:
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code != 200:
                return {
                    "success": False,
                    "message": f"HTTP {response.status_code} loading {url}"
                }

            content = response.text
            content_type = response.headers.get("Content-Type", "").lower()

            # Format guessed from HTTP Content-Type
            guessed_format = self._guess_format_from_content_type(content_type)

            self.graph = Graph()

            # If we recognise the Content-Type → parse directly
            if guessed_format:
                try:
                    self.graph.parse(data=content, format=guessed_format)
                    return {
                        "success": True,
                        "message": f"{len(self.graph)} triples loaded (via HTTP; format: {guessed_format})"
                    }
                except:
                    pass  # fallback below

            # Otherwise, try all formats
            for fmt in ["xml", "application/rdf+xml", "turtle", "json-ld", "nt", "n3"]:
                try:
                    self.graph.parse(data=content, format=fmt)
                    return {
                        "success": True,
                        "message": f"{len(self.graph)} triples loaded (via HTTP; fallback format: {fmt})"
                    }
                except:
                    continue

            return {
                "success": False,
                "message": f"Could not parse RDF from {url} even after content negotiation"
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Error fetching {url}: {str(e)}"
            }

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
    


