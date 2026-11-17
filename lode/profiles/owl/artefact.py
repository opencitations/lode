"""OwlOntology: the Artefact class of the owl profile."""
from lode.artefact import Artefact


class OwlOntology(Artefact):
    """An OWL ontology: an Artefact read with the owl profile.

    The class carries no code: the profile that names it (lode.profiles.owl) supplies the
    logic, the viewer and the configuration. Read one with OwlOntology(source).
    """
