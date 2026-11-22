"""The public facade: lode.read and lode.build_site."""
import pytest

import lode
from lode import profiles
from lode.exceptions import ArtefactValidationError
from lode.models import Concept
from lode.profiles.skos.artefact import SkosVocabulary

SKOS = """
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix ex: <http://example.org/> .
ex:scheme a skos:ConceptScheme ; skos:hasTopConcept ex:animal .
ex:animal a skos:Concept ; skos:prefLabel "animal"@en ; skos:inScheme ex:scheme .
ex:cat a skos:Concept ; skos:prefLabel "cat"@en ; skos:broader ex:animal ; skos:inScheme ex:scheme .
"""


@pytest.fixture
def vocabulary(tmp_path):
    """A small SKOS vocabulary on disk."""
    path = tmp_path / "vocabulary.ttl"
    path.write_text(SKOS, encoding="utf-8")
    return path


def test_a_format_class_reads_its_format(vocabulary):
    artefact = SkosVocabulary(str(vocabulary))
    assert artefact.read_as == "skos"


def test_skos_is_not_enabled_yet(vocabulary):
    """SKOS is not ready for release: lode.read refuses it, the class still reads it."""
    with pytest.raises(ArtefactValidationError):
        lode.read(str(vocabulary), "skos")


def test_instances_of_a_class(vocabulary):
    artefact = SkosVocabulary(str(vocabulary))
    ids = {c.get_has_identifier() for c in artefact.get_entities(Concept)}
    assert ids == {"http://example.org/animal", "http://example.org/cat"}


def test_build_site_writes_the_site(vocabulary, tmp_path):
    out = tmp_path / "site"
    lode.build_site(SkosVocabulary(str(vocabulary)), out)
    assert (out / "index.html").exists()
    assert (out / "index.ttl").exists()


def test_unknown_format_is_rejected(vocabulary):
    with pytest.raises(ArtefactValidationError):
        lode.read(str(vocabulary), "nonsense")


def test_format_classes_come_from_the_package_root():
    from lode import OwlOntology, SkosVocabulary as FromRoot

    assert OwlOntology is profiles.get("owl").artefact_class()
    assert FromRoot is SkosVocabulary


def test_unknown_names_of_the_package_root_are_attribute_errors():
    with pytest.raises(AttributeError):
        lode.NotAFormat
    assert not hasattr(lode, "__wrapped__")
