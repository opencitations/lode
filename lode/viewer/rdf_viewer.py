"""Viewer for RDF/RDFS artefacts."""
from lode.viewer.base_viewer import BaseViewer


class RdfViewer(BaseViewer):
    """RDF / RDFS viewer: display names, table of contents and card come from config/rdf_viewer.yaml."""

    CONFIG_NAME = "rdf"
