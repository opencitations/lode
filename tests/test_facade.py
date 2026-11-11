"""The public facade: lode.read and lode.build_site."""
import pytest

import lode
from lode.artefact import Artefact

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


def test_read_returns_an_artefact(vocabulary):
    artefact = lode.read(str(vocabulary), "skos")
    assert isinstance(artefact, Artefact)
    assert artefact.read_as == "skos"


def test_instances_of_a_class(vocabulary):
    artefact = lode.read(str(vocabulary), "skos")
    ids = {c.get_has_identifier() for c in artefact.instances("Concept")}
    assert ids == {"http://example.org/animal", "http://example.org/cat"}


def test_build_site_writes_the_site(vocabulary, tmp_path):
    out = tmp_path / "site"
    lode.build_site(lode.read(str(vocabulary), "skos"), out)
    assert (out / "index.html").exists()
    assert (out / "index.ttl").exists()


def test_unknown_format_is_rejected(vocabulary):
    with pytest.raises(ValueError):
        lode.read(str(vocabulary), "nonsense")
