"""OWL profile: ontologies read with reader.yaml and shown by OwlViewer."""
from lode.profiles import Profile, register

register(Profile(
    name="owl",
    package=__name__,
    logic=".logic:OwlLogic",
    viewer=".viewer:OwlViewer",
    artefact=".artefact:OwlOntology",
    post_checks=".checks:run_post_checks",
))
