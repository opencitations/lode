"""Viewer layer: renders the model as view data for the HTML templates."""

from .base_viewer import BaseViewer
from .owl_viewer import OwlViewer
from .rdf_viewer import RdfViewer
from .skos_viewer import SkosViewer

__all__ = [
    'BaseViewer',
    'OwlViewer',
    'RdfViewer',
    'SkosViewer',
]


def get_viewer(read_as: str, reader):
    """Return the viewer that matches the artefact format (owl, rdf/rdfs, skos).

    An unknown format falls back to the generic BaseViewer.
    """
    key = read_as.lower()
    if key == 'owl':
        return OwlViewer(reader)
    if key in ('rdf', 'rdfs'):
        return RdfViewer(reader)
    if key == 'skos':
        return SkosViewer(reader)
    return BaseViewer(reader)