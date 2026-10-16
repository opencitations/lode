"""Viewer for OWL artefacts."""
from lode.viewer.base_viewer import BaseViewer


class OwlViewer(BaseViewer):
    """OWL viewer: display names, table of contents and card come from config/owl_viewer.yaml."""

    CONFIG_NAME = "owl"
