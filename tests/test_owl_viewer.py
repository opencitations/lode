"""
test_owl_viewer.py
Tests for OwlViewer / BaseViewer.

Two layers:
  - Unit:        a fake reader with a hand-built _instance_cache, so we exercise
                 the viewer in isolation (no RDF parsing, no network). These pin
                 the ToC-filtering / internal-vs-external / single-resource
                 contract precisely.
  - Integration: parametrized over the ontologies.json corpus (same pattern as
                 test_owl_integrity), asserting viewer invariants on real data.
                 Skips an ontology if it cannot be loaded.

Run with:
    pytest test_owl_viewer.py -v
"""

import json
import os
from pathlib import Path

import pytest

from lode.models import (
    Concept, Relation, Attribute, Annotation, Individual,
    Model, Statement, Literal,
)
from lode.viewer import OwlViewer
import re


# ---------------------------------------------------------------------------
# Unit-test scaffolding: a minimal fake reader the viewer can consume.
# ---------------------------------------------------------------------------

class _FakeReader:
    """Mimics the parts of Reader that BaseViewer touches: an instance cache,
    a provenance subgraph hook, and a graph for namespace binding."""

    def __init__(self, cache):
        self._instance_cache = cache
        self._graph = _FakeGraph()

    def get_provenance_subgraph(self, instance):
        return _FakeGraph()


class _FakeGraph:
    def namespaces(self):
        return iter(())

    def serialize(self, format="turtle"):
        return ""

    def __iter__(self):
        return iter(())


def _entity(cls, uri, label=None):
    inst = cls()
    inst.set_has_identifier(str(uri))
    if label is not None:
        lit = Literal()
        lit.set_has_value(label)
        lit.set_has_language("en")
        inst.set_has_label(lit)   
    return inst


def _viewer(*instances):
    """Cache keyed by URI -> set of instances (handles punning: same key,
    multiple instances)."""
    cache = {}
    for inst in instances:
        key = inst.get_has_identifier()
        cache.setdefault(key, set()).add(inst)
    return OwlViewer(_FakeReader(cache))

# rdflib BNode ids look like 'N' + 32 hex chars, or 'n<digits/hex>' for parsed
# blank nodes. Anything matching means a raw blank node leaked into the view.
_BNODE_RE = re.compile(r'^(_:)?[Nn][0-9a-fA-F]{8,}$')

def _looks_like_bnode(value) -> bool:
    if not value:
        return False
    return bool(_BNODE_RE.match(str(value).strip()))

def _iter_resolved_values(data):
    """Yield every resolved value dict in an entity view (relations + statements),
    flattening restriction parts."""
    for section in data.get("sections", []):
        for ent in section["entities"]:
            buckets = list(ent.get("relations", {}).values()) + list(ent.get("statements", {}).values())
            for values in buckets:
                for v in (values if isinstance(values, list) else [values]):
                    for part in (v.get("parts") or [v]):
                        yield ent["uri"], part


C = "http://ex.org/MyClass"
P = "http://ex.org/myProp"
I = "http://ex.org/myIndividual"
ONTO = "http://ex.org/ontology"
EXT = "http://purl.org/spar/fabio/ProceedingsPaper"  # not in our cache


# ---------------------------------------------------------------------------
# _is_toc_entity  — the single source of truth for "is this browsable?"
# ---------------------------------------------------------------------------

class TestIsTocEntity:

    def test_concept_is_toc(self):
        v = _viewer()
        assert v._is_toc_entity(_entity(Concept, C)) is True

    def test_relation_is_toc(self):
        v = _viewer()
        assert v._is_toc_entity(_entity(Relation, P)) is True

    def test_model_is_not_toc(self):
        """An ontology (Model) is never a ToC entity: Model is not in get_toc_config()."""
        v = _viewer()
        assert v._is_toc_entity(_entity(Model, ONTO)) is False

    def test_statement_is_not_toc(self):
        v = _viewer()
        assert v._is_toc_entity(_entity(Statement, "http://ex.org/stmt")) is False

    def test_config_drives_membership(self):
        """The decision is purely config-driven: every key in get_toc_config()
        is accepted, nothing else is."""
        v = _viewer()
        toc_keys = {key for key, _id, _title in v.get_toc_config()}
        assert "Concept" in toc_keys
        assert "Model" not in toc_keys


# ---------------------------------------------------------------------------
# get_toc_instances — only ToC entities surface
# ---------------------------------------------------------------------------

class TestGetTocInstances:

    def test_excludes_model(self):
        v = _viewer(_entity(Concept, C), _entity(Model, ONTO))
        types = {type(i).__name__ for i in v.get_toc_instances()}
        assert "Concept" in types
        assert "Model" not in types

    def test_keeps_all_toc_kinds(self):
        v = _viewer(
            _entity(Concept, C),
            _entity(Relation, P),
            _entity(Attribute, "http://ex.org/attr"),
            _entity(Annotation, "http://ex.org/anno"),
            _entity(Individual, I),
        )
        types = {type(i).__name__ for i in v.get_toc_instances()}
        assert types == {"Concept", "Relation", "Attribute", "Annotation", "Individual"}

    def test_punned_individual_still_surfaces(self):
        """If an IRI is punned Model+Individual, the Individual is a legitimate
        ToC entity (config-driven); only the Model facet is dropped."""
        onto = _entity(Model, ONTO)
        indiv = _entity(Individual, ONTO)
        v = _viewer(onto, indiv)
        instances = v.get_toc_instances()
        assert any(type(i).__name__ == "Individual" for i in instances)
        assert not any(type(i).__name__ == "Model" for i in instances)


# ---------------------------------------------------------------------------
# _is_internal — internal == present among ToC entities
# ---------------------------------------------------------------------------

class TestIsInternal:

    def test_known_concept_is_internal(self):
        v = _viewer(_entity(Concept, C))
        assert v._is_internal(C) is True

    def test_external_uri_is_not_internal(self):
        v = _viewer(_entity(Concept, C))
        assert v._is_internal(EXT) is False

    def test_punned_ontology_iri_is_internal_as_individual(self):
        v = _viewer(_entity(Concept, C), _entity(Model, ONTO), _entity(Individual, ONTO))
        assert v._is_internal(ONTO) is True

    def test_none_is_not_internal(self):
        v = _viewer(_entity(Concept, C))
        assert v._is_internal(None) is False


# ---------------------------------------------------------------------------
# _resolve_resource_value — is_external flag is set correctly
# ---------------------------------------------------------------------------

class TestResolveResourceValue:

    def test_internal_resource_not_external(self):
        v = _viewer(_entity(Concept, C, "My Class"))
        target = _entity(Concept, C, "My Class")
        d = v._resolve_resource_value(target)
        assert d["link"] == C
        assert d["is_external"] is False

    def test_external_resource_is_external(self):
        v = _viewer(_entity(Concept, C))
        target = _entity(Concept, EXT, "Proceedings Paper")
        d = v._resolve_resource_value(target)
        assert d["link"] == EXT
        assert d["is_external"] is True

    def test_punned_ontology_individual_is_internal(self):
        v = _viewer(_entity(Concept, C), _entity(Model, ONTO), _entity(Individual, ONTO))
        target = _entity(Individual, ONTO, "fabio")
        d = v._resolve_resource_value(target)
        assert d["is_external"] is False


# ---------------------------------------------------------------------------
# _handle_single_resource — non-ToC URIs are not browsable
# ---------------------------------------------------------------------------

class TestHandleSingleResource:

    def test_browsable_concept_returns_entities(self):
        v = _viewer(_entity(Concept, C, "My Class"))
        data = v._handle_single_resource(C)
        assert data.get("single_resource") is True
        assert len(data["entities"]) == 1
        assert data["entities"][0]["uri"] == C

    def test_ontology_iri_is_not_browsable(self):
        """Opening ?resource=<ontology> must NOT dump the whole model."""
        v = _viewer(_entity(Model, ONTO))
        data = v._handle_single_resource(ONTO)
        assert "error" in data
        assert "entities" not in data

    def test_punned_ontology_drops_model_keeps_individual(self):
        v = _viewer(_entity(Model, ONTO), _entity(Individual, ONTO, "thing"))
        data = v._handle_single_resource(ONTO)
        assert data.get("single_resource") is True
        types = {e["type"] for e in data["entities"]}
        assert "Model" not in types
        assert "Individual" in types

    def test_unknown_uri_returns_error(self):
        v = _viewer(_entity(Concept, C))
        data = v._handle_single_resource("http://ex.org/nope")
        assert "error" in data


# ---------------------------------------------------------------------------
# Grouped view — sections come only from ToC config, Model excluded
# ---------------------------------------------------------------------------

class TestGroupedView:

    def test_model_absent_from_sections(self):
        v = _viewer(
            _entity(Concept, C, "Class"),
            _entity(Individual, I, "Indiv"),
            _entity(Model, ONTO),
        )
        data = v.get_view_data()  # no resource_uri -> grouped
        section_titles = {s["title"] for s in data["sections"]}
        assert "Concept" in section_titles
        # Model has no section because it is not in get_toc_config()
        assert all("Ontolog" not in t for t in section_titles)

    def test_each_section_entity_is_toc_kind(self):
        v = _viewer(
            _entity(Concept, C, "Class"),
            _entity(Relation, P, "prop"),
            _entity(Model, ONTO),
        )
        data = v.get_view_data()
        toc_keys = {key for key, _id, _title in v.get_toc_config()}
        for section in data["sections"]:
            for ent in section["entities"]:
                assert ent["type"] in toc_keys


# ===========================================================================
# Integration: real corpus, same loader pattern as test_owl_integrity.
# ===========================================================================

ONTOLOGIES_PATH = Path(__file__).parent / "ontologies_spar.json"


def _load_uris():
    single = os.environ.get("TEST_ONTOLOGY_URI")
    if single:
        return [single]
    if not ONTOLOGIES_PATH.exists():
        return []
    with open(ONTOLOGIES_PATH) as f:
        data = json.load(f)
    return [entry["uri"] for entry in data["uris"]]


@pytest.fixture(scope="module", params=_load_uris())
def viewer(request):
    from lode.reader import Reader
    reader = Reader()
    try:
        reader.load_instances(request.param, "owl")
    except Exception as e:
        pytest.skip(f"Could not load {request.param}: {e}")
    v = reader.get_viewer()
    yield v
    reader.clear_cache()


class TestCorpusInvariants:

    def test_no_model_in_toc_instances(self, viewer):
        """No ToC entity is a Model, on any real ontology."""
        assert all(type(i).__name__ != "Model" for i in viewer.get_toc_instances())

    def test_grouped_sections_only_toc_kinds(self, viewer):
        data = viewer.get_view_data()
        toc_keys = {key for key, _id, _title in viewer.get_toc_config()}
        for section in data.get("sections", []):
            for ent in section["entities"]:
                assert ent["type"] in toc_keys

    def test_single_resource_roundtrip(self, viewer):
        """Opening any ToC entity by URI returns exactly that entity, browsable."""
        toc = viewer.get_toc_instances()
        if not toc:
            pytest.skip("no ToC entities in this ontology")
        target = toc[0]
        uri = str(target.get_has_identifier())
        data = viewer.get_view_data(resource_uri=uri)
        assert "error" not in data
        assert any(e["uri"] == uri for e in data["entities"])

    def test_opening_ontology_iri_shows_no_model_facet(self, viewer):
        """Opening the ontology IRI never surfaces the Model facet (only its
        ToC facets, if any)."""
        from rdflib.namespace import RDF, OWL
        from rdflib import URIRef
        for onto in viewer.reader._graph.subjects(RDF.type, OWL.Ontology):
            if not isinstance(onto, URIRef):
                continue
            data = viewer.get_view_data(resource_uri=str(onto))
            if "error" not in data:
                assert all(e["type"] != "Model" for e in data["entities"])
            break

    def test_no_raw_bnode_in_entity_links(self, viewer):
        """No resolved relation/statement value points to a raw BNode id:
        unprocessed blank nodes must never become clickable links."""
        data = viewer.get_view_data()
        offenders = []
        for section in data.get("sections", []):
            for ent in section["entities"]:
                for rel_name, values in ent["relations"].items():
                    for v in (values if isinstance(values, list) else [values]):
                        # restriction parts carry their own sub-links
                        for part in (v.get("parts") or [v]):
                            if _looks_like_bnode(part.get("link")):
                                offenders.append((ent["uri"], rel_name, part.get("link")))
        assert not offenders, f"raw BNode ids leaked as links: {offenders[:10]}"

    def test_no_raw_bnode_as_entity_uri(self, viewer):
        """No ToC entity is itself a raw BNode (every card must have a real IRI)."""
        bad = [
            str(i.get_has_identifier())
            for i in viewer.get_toc_instances()
            if _looks_like_bnode(i.get_has_identifier())
        ]
        assert not bad, f"ToC entities with BNode identifier: {bad[:10]}"

    def test_no_raw_bnode_in_displayed_text(self, viewer):
        """No resolved value shows a raw BNode id as its visible text.
        Restrictions are allowed (their text is composed), so we check leaf
        values only — a leaf whose text equals a BNode id is a leak."""
        data = viewer.get_view_data()
        offenders = []
        for section in data.get("sections", []):
            for ent in section["entities"]:
                for rel_name, values in ent["relations"].items():
                    for v in (values if isinstance(values, list) else [values]):
                        if v.get("parts"):
                            continue  # composed restriction text is fine
                        if _looks_like_bnode(v.get("text")):
                            offenders.append((ent["uri"], rel_name, v.get("text")))
        assert not offenders, f"raw BNode ids leaked as text: {offenders[:10]}"

    def test_external_links_are_not_clickable(self, viewer):
        """Any value whose link is NOT a ToC entity (external URL, uncached
        import, raw bnode) must be is_external=True, so the template renders it
        as plain text — never as an /extract?resource= link. Regression for the
        nlm.nih.gov 'see also' that wrongly reloaded the API."""
        data = viewer.get_view_data()
        offenders = []
        for ent_uri, val in _iter_resolved_values(data):
            link = val.get("link")
            if not link:
                continue
            # ground truth: is this link a real ToC entity?
            is_toc = viewer._is_internal(link)
            if not is_toc and not val.get("is_external", False):
                offenders.append((ent_uri, link))
        assert not offenders, (
            f"external/non-ToC links not marked is_external "
            f"(would become clickable /extract links): {offenders[:10]}"
        )

    def test_toc_links_stay_internal(self, viewer):
        """Mirror invariant: a link that IS a ToC entity must be is_external=False
        (so internal navigation still works)."""
        data = viewer.get_view_data()
        offenders = []
        for ent_uri, val in _iter_resolved_values(data):
            link = val.get("link")
            if not link:
                continue
            if viewer._is_internal(link) and val.get("is_external", True):
                offenders.append((ent_uri, link))
        assert not offenders, (
            f"ToC links wrongly marked external (lose internal navigation): {offenders[:10]}"
        )