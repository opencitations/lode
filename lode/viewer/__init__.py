"""Viewer layer: renders the model as view data for the HTML templates."""

from .base_viewer import BaseViewer
from .owl_viewer import OwlViewer
from .rdf_viewer import RdfViewer
from .skos_viewer import SkosViewer

_VIEWERS = {
    'owl': OwlViewer,
    'rdf': RdfViewer,
    'skos': SkosViewer,
}


def get_viewer(artefact):
    """Return the viewer that matches the format the artefact was read as.

    The format comes from `artefact.read_as`. An unknown or missing format falls
    back to the generic BaseViewer.
    """
    return _VIEWERS.get((artefact.read_as or '').lower(), BaseViewer)(artefact)