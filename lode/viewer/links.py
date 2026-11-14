"""Where the things a page links to live: what a viewer cannot know by itself."""
from typing import Optional


class Links:
    """Tell a viewer the addresses of resources, exports and the whole artefact.

    The web service and the static site each know where these live (a query string, a relative
    path); the viewer does not. This base class answers "nowhere": every method returns None, which
    is what a library user without a site gets. A caller subclasses it and answers.
    """

    def resource(self, iri: str) -> Optional[str]:
        """Return the address of the page of a resource of this documentation, or None when it has no page here: the viewer then links to the IRI itself."""
        return None

    def export(self, ext: str, iri: Optional[str] = None) -> Optional[str]:
        """Return where to download the artefact, or the resource `iri`, in the format with extension `ext`."""
        return None

    def home(self) -> Optional[str]:
        """Return the address of the page of the whole artefact, or None."""
        return None
