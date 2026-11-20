"""LODE: Live OWL Documentation Environment, maintained by OpenCitations.

Typical use as a library:

    import lode
    from lode import SkosVocabulary
    from lode.models import Concept

    vocabulary = SkosVocabulary("vocabulary.ttl")
    for concept in vocabulary.get_entities(Concept):
        print(concept.get_has_identifier())

    lode.build_site(vocabulary, "site")

The classes of the formats (OwlOntology, SkosVocabulary and those of installed plugins) are
found on first use, so importing `lode` does not import rdflib or the readers.
"""
from lode.core import build_site, read

__all__ = ["read", "build_site", "OwlOntology", "SkosVocabulary"]


def __getattr__(name: str):
    """Return the Artefact class called `name`, found in the profile registry (PEP 562).

    Lets `from lode import OwlOntology` work without the package root importing any profile.
    Private and dunder names are refused at once: tools probe them (`__path__`, `__wrapped__`)
    and must not trigger the import of every format.
    """
    if not name.startswith("_"):
        from lode.profiles import artefact_class_named

        cls = artefact_class_named(name)
        if cls is not None:
            return cls
    raise AttributeError(f"module 'lode' has no attribute {name!r}")
