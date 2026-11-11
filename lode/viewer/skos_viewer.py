"""Viewer for SKOS artefacts."""
from lode.viewer.base_viewer import BaseViewer


class SkosViewer(BaseViewer):
    """SKOS viewer.

    Display names, table of contents and card come from config/skos_viewer.yaml.
    Entities are formatted by BaseViewer, so SKOS produces the same data structure
    as OWL and the card (a separate template) reads the same keys.
    """

    CONFIG_NAME = "skos"
