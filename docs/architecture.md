# Architecture

LODE is built in layers. Data flows in one direction and each layer knows only
the one below it.

```text
  Loader ──▶ Reader ──fills──▶ Model
               │
               └──builds──▶ Artefact ──▶ Viewer ──▶ Static builder
                                           │
                                           └──────▶ Web service / REST API

  CLI ──▶ Static builder
  lode.read / lode.build_site ── a thin facade over Reader, Artefact and Viewer
```


## Layers

| Layer | Package | Responsibility |
|-------|---------|----------------|
| Loader | `lode.reader.loader` | Fetches and parses the artefact, resolves imports, enforces URL and size limits. |
| Reader | `lode.reader` | Turns an RDF graph into model instances, driven by a YAML mapper. |
| Model | `lode.models` | Plain Python classes for entities: `Concept`, `Collection`, `Relation`, and so on. It knows neither who fills it nor who shows it. |
| Artefact | `lode.artefact` | The hand-over between the reader and everything that consumes its result. |
| Viewer | `lode.viewer` | Turns model instances into the dictionaries the HTML templates render, and into RDF serializations. |
| Profiles | `lode.profiles` | One package per artefact format (OWL, SKOS, ...): its mapper, logic class, viewer and templates. The registry in `lode.profiles` is the only place that knows which formats exist. |
| Adapters | `lode.cli`, `lode.api`, `lode.builder` | Thin entry points that wire the layers together. They contain no extraction logic. |
| Facade | `lode` | Two functions for library users: `lode.read` returns an Artefact, `lode.build_site` writes a site from one. |

## The Artefact

After a read, `Reader.get_artefact()` (or `lode.read`) returns an `Artefact`
with the entities, the RDF graph, the IRI of the documented ontology, the
imported modules, the warnings, the format (`read_as`) and a `provenance`
object. It can list its own entities (`instances()`, `get_instance()`), so a
consumer never needs the reader that built it. Viewers depend on this object
only. See the [Python API](usage/python_api.md) for the members.

Provenance, the set of triples an entity was built from, is computed on demand
with `artefact.provenance.for_instance(instance)`. Nothing is precomputed,
because a documentation can hold thousands of entities and most are never
inspected.

## Dependency rules

- The viewer does not import the reader.
- The model imports neither the reader nor the viewer.
- The reader does not import the viewer.
- The core (reader, viewer, model, helpers) reaches a profile only through the
  registry in `lode.profiles`. It never imports a profile package.
- A profile does not import another profile.

`tests/test_architecture.py` checks these rules on the source files, so a
violation fails the test suite.

## Profiles

An artefact format is a profile: the package `lode/profiles/<format>/`, with its
mapper (`reader.yaml`), logic class, viewer class, viewer settings and optional
templates. Its `__init__.py` registers a `Profile`, and everything that depends on the
format asks the registry: `lode.read` for the reader, `lode.viewer.get_viewer` for the
viewer, the CLI and the API for the formats they accept. LODE ships `owl` and `skos`,
and other packages can add formats through the `lode.profiles` entry point group.
See [Extending LODE](extending.md).

## Reading

The mapping from RDF constructs to model classes is declared in YAML, not in
Python: `lode/reader/config/base.yaml` plus the `reader.yaml` of each profile. A
format specific logic class implements the phases that differ; SKOS, for example, has
no group axioms.

1. Classify blank nodes from the predicates they carry (OWL only).
2. Create an instance for every subject typed with a mapped class, and apply
   the static setters of that class.
3. Populate properties through the setters declared in the mapper.
4. Process group axioms (OWL: `AllDisjointClasses`, `AllDifferent`, ...).
5. Apply fallbacks and defaults (OWL: default domain and range).
6. Turn every triple not consumed so far into a `Statement`.

## Viewing

`lode.viewer.get_viewer(artefact)` selects the viewer from `artefact.read_as`, by
asking the registry for the viewer class of that profile. What each format shows (table of
contents, display names, card template) is declared in the `viewer.yaml` and the
`templates/` folder of its profile.

## Adding a format

Add a profile package. [Extending LODE](extending.md) walks through it, from the
mapper to the viewer, and shows how to ship the profile as a separate package.
