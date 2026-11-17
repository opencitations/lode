"""Viewer layer: renders the model as view data for the HTML templates."""

from lode import profiles
from .base_viewer import BaseViewer


def get_viewer(artefact):
    """Return the viewer of the profile the artefact was read as.

    The profile comes from `artefact.read_as`. An unknown or missing format falls
    back to the generic BaseViewer.
    """
    profile = profiles.find(artefact.read_as)
    if profile is None:
        return BaseViewer(artefact)
    return profiles.resolve(profile.viewer)(artefact)
