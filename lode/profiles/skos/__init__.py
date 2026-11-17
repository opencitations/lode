"""SKOS profile: concept schemes read with reader.yaml and shown by SkosViewer."""
from lode.profiles import Profile, register

register(Profile(
    name="skos",
    package=__name__,
    logic=".logic:SkosLogic",
    viewer=".viewer:SkosViewer",
    artefact=".artefact:SkosVocabulary",
))
