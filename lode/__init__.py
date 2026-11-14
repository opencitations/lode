"""LODE: Live OWL Documentation Environment, maintained by OpenCitations.

Typical use as a library:

    import lode
    from lode.models import Concept

    artefact = lode.read("vocabulary.ttl", "skos")
    for concept in artefact.instances(Concept):

        print(concept.get_has_identifier())

    lode.build_site(artefact, "site")
"""
from lode.core import build_site, read, view

__all__ = ["read", "build_site", "view"]
