"""Every artefact format must be wired in all the places that need it.

A format is declared once, in the profile registry (lode.profiles); these tests fail
with a clear message when the enabled set, the YAML files or the paths a profile points
to drift from it, and they cover how plugin profiles are discovered.
"""
import dataclasses
from types import SimpleNamespace

import pytest
from rdflib import Graph

import lode
from lode import profiles
from lode.artefact import Artefact
from lode.exceptions import ArtefactValidationError
from lode.reader.config_manager import ConfigManager
from lode.viewer.base_viewer import BaseViewer

FORMATS = sorted(profiles.names())


def test_get_enabled_accepts_only_enabled_profiles_in_any_case():
    """An enabled profile passes in any case; an unknown one fails with the list of valid formats."""
    assert profiles.get_enabled("OWL") is profiles.get("owl")
    with pytest.raises(ArtefactValidationError) as err:
        profiles.get_enabled("shacl")
    assert err.value.context["supported"] == profiles.names(enabled_only=True)


@pytest.mark.parametrize("fmt", FORMATS)
def test_profile_paths_resolve(fmt):
    """Reader, viewer and post-checks of every profile point to real objects."""
    p = profiles.get(fmt)
    assert profiles.resolve(p.reader, p.package)
    assert issubclass(profiles.resolve(p.viewer, p.package), BaseViewer)
    assert issubclass(p.artefact_class(), Artefact)
    if p.post_checks:
        assert callable(profiles.resolve(p.post_checks, p.package))


def test_unknown_profile_lists_the_available_ones():
    """An unknown name fails with the list of valid names."""
    with pytest.raises(ValueError, match="Available: owl, skos"):
        profiles.get("shacl")


@pytest.mark.parametrize("fmt", FORMATS)
def test_format_config_files_exist(fmt):
    """Each format ships its mapper and its viewer config."""
    assert (profiles.get(fmt).path() / "reader.yaml").is_file()
    assert (profiles.get(fmt).path() / "viewer.yaml").is_file()


@pytest.mark.parametrize("fmt", FORMATS)
def test_format_builds_its_reader(fmt):
    """The registry entry resolves to a reader class that can be instantiated."""
    assert profiles.get(fmt).make_reader(Graph(), {}, ConfigManager(profiles.get(fmt))) is not None


@pytest.fixture
def plugins(monkeypatch):
    """Let a test choose the entry points the registry sees; the built-ins stay registered."""
    profiles.names()  # make sure the built-ins are loaded before the registry is patched
    monkeypatch.setattr(profiles, "_PROFILES", dict(profiles._PROFILES))
    monkeypatch.setattr(profiles, "_BUILTIN", ())
    monkeypatch.setattr(profiles, "_loaded", False)

    def offer(*entry_points):
        monkeypatch.setattr(profiles, "entry_points", lambda **_group: list(entry_points))
    return offer


def _fake_profile(name):
    """A profile that reuses the SKOS classes under another name."""
    return profiles.Profile(name, "lode.profiles.skos", "lode.profiles.skos.reader:SkosReader",
                            "lode.profiles.skos.viewer:SkosViewer",
                            "lode.profiles.skos.artefact:SkosVocabulary")


def test_a_plugin_profile_is_registered(plugins):
    """A profile offered through the entry point group joins the built-in ones."""
    plugins(SimpleNamespace(name="fake", load=lambda: _fake_profile("fake")))
    assert "fake" in profiles.names()


def test_a_broken_plugin_is_skipped_and_logged(plugins, caplog):
    """A plugin that fails to load does not break LODE: it is logged and skipped."""
    def boom():
        raise ImportError("nope")
    plugins(SimpleNamespace(name="bad", load=boom))
    assert "owl" in profiles.names()
    assert "Profile plugin 'bad' failed to load" in caplog.text


def test_a_plugin_cannot_replace_a_builtin(plugins, caplog):
    """A plugin that reuses a registered name is refused; the built-in stays."""
    original = profiles._PROFILES["owl"]
    plugins(SimpleNamespace(name="evil", load=lambda: _fake_profile("owl")))
    assert profiles.get("owl") is original
    assert "redefines 'owl'" in caplog.text


def test_a_mapper_can_name_a_class_by_path():
    """'module:Name' in a mapper resolves to a class; a wrong path fails loudly."""
    from lode.models import Concept
    manager = ConfigManager(profiles.get("owl"))
    assert manager._parse_class("lode.models:Concept") is Concept
    with pytest.raises(KeyError):
        manager._parse_class("lode.models:Nope")


def test_a_disabled_profile_is_refused_by_read(monkeypatch, tmp_path):
    """lode.read is the gate of the adapters: a disabled format never reaches the reader."""
    owl = profiles.get("owl")
    monkeypatch.setitem(profiles._PROFILES, "owl", dataclasses.replace(owl, enabled=False))
    with pytest.raises(ArtefactValidationError):
        lode.read(str(tmp_path / "never-read.ttl"), "owl")


def test_of_finds_the_profile_of_a_class_and_of_its_subclasses():
    """A format class has its profile; a user's subclass inherits it; Artefact has none."""
    from lode.profiles.owl.artefact import OwlOntology

    class MyOntology(OwlOntology):
        """A user's own subclass."""

    assert profiles.of(OwlOntology) is profiles.get("owl")
    assert profiles.of(MyOntology) is profiles.get("owl")
    assert profiles.of(Artefact) is None