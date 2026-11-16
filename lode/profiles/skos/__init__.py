"""SKOS profile: concept schemes read with reader.yaml and shown by SkosViewer."""
from lode.profiles import Profile, register

register(Profile(
    name="skos",
    package=__name__,
    logic="lode.profiles.skos.logic:SkosLogic",
    viewer="lode.profiles.skos.viewer:SkosViewer",
))
