"""OWL profile: ontologies read with reader.yaml and shown by OwlViewer."""
from lode.profiles import Profile, register

register(Profile(
    name="owl",
    package=__name__,
    logic="lode.profiles.owl.logic:OwlLogic",
    viewer="lode.profiles.owl.viewer:OwlViewer",
    post_checks="lode.profiles.owl.checks:run_post_checks",
))
