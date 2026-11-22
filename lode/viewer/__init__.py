"""Viewer layer: renders the model as view data for the HTML templates."""

from .base_viewer import BaseViewer


def get_viewer(artefact):
    """Return the viewer of the artefact's profile.

    An artefact without a profile (one built by hand with Artefact.from_parts) gets the
    generic BaseViewer.
    """
    profile = artefact.profile
    return profile.make_viewer(artefact) if profile else BaseViewer(artefact)
