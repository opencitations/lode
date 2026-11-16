"""Viewer layer: renders the model as view data for the HTML templates."""

from .base_viewer import BaseViewer
from .owl_viewer import OwlViewer
from .rdf_viewer import RdfViewer
from .skos_viewer import SkosViewer
from lode import profiles


def get_viewer(artefact):
    """Return the viewer of the profile the artefact was read as.

    The profile comes from `artefact.read_as`. An unknown or missing format falls
    back to the generic BaseViewer.
    """
    name = (artefact.read_as or '').lower()
    if name not in profiles.PROFILES:
        return BaseViewer(artefact)
    return profiles.resolve(profiles.get(name).viewer)(artefact)
