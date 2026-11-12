"""Every artefact format must be wired in all the places that need it.

Adding a format touches the reader registry, the viewer registry, the
ReadAsFormat enum and two YAML files; these tests fail with a clear message
when one of them is missing.
"""
from pathlib import Path

import pytest
from rdflib import Graph

from lode.helpers.formats import ENABLED_FORMATS, ReadAsFormat
from lode.helpers.formats import CONFIGURATION_REGISTRY, ENABLED_FORMATS, ReadAsFormat
from lode.reader.config_manager import get_configuration
from lode.viewer import _VIEWERS

LODE = Path(__file__).resolve().parent.parent / "lode"
FORMATS = sorted(CONFIGURATION_REGISTRY)

def test_read_as_enum_matches_reader_registry():
    """The API and CLI accept exactly the formats the reader knows."""
    assert {f.value for f in ReadAsFormat} == set(CONFIGURATION_REGISTRY)


def test_enabled_formats_are_known():
    """A format cannot be enabled without being registered."""
    assert ENABLED_FORMATS <= set(CONFIGURATION_REGISTRY)


def test_every_format_has_a_viewer():
    """Reader and viewer registries list the same formats."""
    assert set(_VIEWERS) == set(CONFIGURATION_REGISTRY)


@pytest.mark.parametrize("fmt", FORMATS)
def test_format_config_files_exist(fmt):
    """Each format ships its mapper and its viewer config."""
    assert (LODE / "reader" / "config" / f"{fmt}.yaml").is_file()
    assert (LODE / "viewer" / "config" / f"{fmt}_viewer.yaml").is_file()


@pytest.mark.parametrize("fmt", FORMATS)
def test_format_builds_its_logic(fmt):
    """The registry entry resolves to a logic class that can be instantiated."""
    assert get_configuration(fmt).create_logic(Graph(), {}) is not None
