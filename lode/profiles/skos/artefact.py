"""SkosVocabulary: the Artefact class of the skos profile."""
from lode.artefact import Artefact


class SkosVocabulary(Artefact):
    """A SKOS vocabulary: an Artefact read with the skos profile.

    The class carries no code: the profile that names it (lode.profiles.skos) supplies the
    reader, the viewer and the configuration. Read one with SkosVocabulary(source).
    """
