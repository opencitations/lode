"""The ConfigManager merges base.yaml with the reader.yaml of a profile and parses the mapper.

The reader never reads YAML itself: it asks the manager what a predicate means. These tests
pin the merge rules documented in docs/extending.md and the parsed form the reader receives.
"""
import pytest
from rdflib.namespace import OWL, RDFS

from lode import profiles
from lode.models import Concept
from lode.reader.config_manager import ConfigManager


@pytest.fixture(scope="module")
def owl_manager():
    """The manager of the OWL profile (parsing the YAML once is enough: tests only read it)."""
    return ConfigManager(profiles.get("owl"))


@pytest.fixture(scope="module")
def skos_manager():
    """The manager of the SKOS profile."""
    return ConfigManager(profiles.get("skos"))


# ==========================================================================
# 1. MERGE RULES
# ==========================================================================

def test_merge_recurses_into_dicts_and_replaces_the_rest(owl_manager):
    """Nested dicts are merged key by key; lists and scalars of the override replace the base."""
    base = {"a": {"x": 1, "y": 2}, "list": [1, 2], "scalar": "base", "only_base": True}
    override = {"a": {"y": 20, "z": 30}, "list": [3], "scalar": "override"}
    assert owl_manager._deep_merge(base, override) == {
        "a": {"x": 1, "y": 20, "z": 30}, "list": [3], "scalar": "override", "only_base": True}


def test_merge_ignores_name_and_inherits(owl_manager):
    """`name` and `inherits` describe the file, not the configuration."""
    merged = owl_manager._deep_merge({"k": 1}, {"name": "owl", "inherits": "base", "k": 2})
    assert merged == {"k": 2}


def test_merge_does_not_change_its_inputs(owl_manager):
    """The base stays usable after a merge: the result is a copy."""
    base = {"a": {"x": 1}}
    owl_manager._deep_merge(base, {"a": {"x": 2}})
    assert base == {"a": {"x": 1}}


def test_a_profile_adds_to_the_shared_base(owl_manager, skos_manager):
    """Both formats start from the shared mapper; SWRL belongs to OWL only."""
    for manager in (owl_manager, skos_manager):
        assert "rdfs:subClassOf" in manager.config["mapper"]
    assert "swrl:Imp" in owl_manager.config["enricher"]
    assert "swrl:Imp" not in skos_manager.config["enricher"]


# ==========================================================================
# 2. THE PARSED MAPPER
# ==========================================================================

def test_uri_prefixes_are_expanded(owl_manager):
    """`owl:Class` becomes the URIRef of the OWL term; a name with no prefix is kept as it is."""
    assert owl_manager._parse_uri("owl:Class") == OWL.Class
    assert str(owl_manager._parse_uri("plainname")) == "plainname"


def test_an_unknown_model_class_fails_loudly(owl_manager):
    """A typo in the YAML must not be silently ignored."""
    with pytest.raises(KeyError):
        owl_manager._parse_class("NoSuchClass")


def test_a_predicate_entry_comes_with_model_classes_resolved(owl_manager):
    """The reader sees classes, not names: `set_is_sub_concept_of` is filled with Concept objects."""
    entry = owl_manager.get_property_mapping()[RDFS.subClassOf]
    (setter_name, target), = entry["setters"][0].items()
    assert setter_name == "set_is_sub_concept_of"
    assert target is Concept
    assert isinstance(entry["inferred_class"], type)


def test_an_entry_can_name_a_handler(owl_manager):
    """`rdfs:domain` is handled by a method of the reader class, besides its setter."""
    assert owl_manager.config["mapper"]["rdfs:domain"]["handler"] == "handle_domain"


def test_every_mapped_class_and_predicate_is_parsed(owl_manager):
    """Parsing the whole mapper succeeds for both formats and gives something to read."""
    for fmt in profiles.names():
        manager = ConfigManager(profiles.get(fmt))
        assert manager.get_type_mapping() and manager.get_property_mapping()
