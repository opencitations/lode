"""Every artefact format must be wired in all the places that need it.

A format is declared once, in the profile registry (lode.profiles); these tests fail
with a clear message when the enum, the enabled set, the YAML files or the paths a
profile points to drift from it.
"""
from pathlib import Path

import pytest
from rdflib import Graph

from lode import profiles
from lode.helpers.formats import ENABLED_FORMATS, ReadAsFormat
from lode.reader.config_manager import get_configuration
from lode.viewer.base_viewer import BaseViewer

LODE = Path(__file__).resolve().parent.parent / "lode"
FORMATS = sorted(profiles.PROFILES)


def test_read_as_enum_matches_registry():
    """The API and CLI accept exactly the registered profiles."""
    assert {f.value for f in ReadAsFormat} == set(profiles.PROFILES)


def test_enabled_formats_are_known():
    """A format cannot be enabled without being registered."""
    assert ENABLED_FORMATS <= set(profiles.PROFILES)


@pytest.mark.parametrize("fmt", FORMATS)
def test_profile_paths_resolve(fmt):
    """Logic, viewer and post-checks of every profile point to real objects."""
    p = profiles.get(fmt)
    assert profiles.resolve(p.logic)
    assert issubclass(profiles.resolve(p.viewer), BaseViewer)
    if p.post_checks:
        assert callable(profiles.resolve(p.post_checks))


def test_unknown_profile_lists_the_available_ones():
    """An unknown name fails with the list of valid names."""
    with pytest.raises(ValueError, match="Available: owl, rdf, skos"):
        profiles.get("shacl")


@pytest.mark.parametrize("fmt", FORMATS)
def test_format_config_files_exist(fmt):
    """Each format ships its mapper and its viewer config."""
    assert (LODE / "reader" / "config" / f"{fmt}.yaml").is_file()
    assert (LODE / "viewer" / "config" / f"{fmt}_viewer.yaml").is_file()


@pytest.mark.parametrize("fmt", FORMATS)
def test_format_builds_its_logic(fmt):
    """The registry entry resolves to a logic class that can be instantiated."""
    assert get_configuration(fmt).create_logic(Graph(), {}) is not None