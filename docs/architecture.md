# Architecture

LODE is built in layers. Data flows in one direction, from the document you give it to the documentation it produces, and each layer knows only the one before it. A new format is a **profile** that plugs into this flow. The cards below follow it in order, and each one says what the step does, what you can change, and where to read more.

::::{grid} 1 1 1 1

:::{card} 1. Profile
**What it is.** The package `lode/profiles/<format>/` that tells LODE how to read and show one format. Its `__init__.py` registers a `Profile` (name, logic class, viewer class, `Artefact` class, whether it is enabled).

**How LODE uses it.** Everything that depends on the format asks the registry in `lode.profiles`: `lode.read` for the reader, `lode.viewer.get_viewer` for the viewer, the CLI and the API for the formats they accept. It is the only place that knows which formats exist. LODE ships `owl` and `skos`; other packages add formats through the `lode.profiles` entry point group.

**You write.** `reader.yaml`, `logic.py`, `viewer.yaml`, `viewer.py`, `artefact.py`, optional `templates/`.
+++
[See Extending LODE](extending.md)
:::

:::{card} 2. Reader
**What it does.** Turns an RDF graph into model instances. The mapping from RDF constructs to model classes is declared in YAML, not in Python: `lode/reader/config/base.yaml`, with the `reader.yaml` of the profile merged on top. A logic class implements the phases that differ between formats.

**Six phases**, all filling one cache `{IRI: set of instances}`:
1. Classify blank nodes from the predicates they carry (OWL only).
2. Create an instance for every subject typed with a mapped class, and apply the static setters.
3. Populate properties through the setters declared in the mapper.
4. Process group axioms (OWL: `AllDisjointClasses`, `AllDifferent`, ...).
5. Apply fallbacks and defaults (OWL: default domain and range).
6. Turn every triple not consumed so far into a `Statement`.

**You change.** The YAML mapper for what a construct means; a logic class (subclass of `BaseLogic`) only for what YAML cannot say. The entities are `lode.models` classes (`Concept`, `Collection`, `Relation`, ...), which know neither who fills them nor who shows them.
+++
[See Extending LODE](extending.md) · [Step by step](notebooks/extending.ipynb)
:::

:::{card} 3. Artefact
**What it is.** The hand-over between the reader and everything after it. It holds the entities, the RDF graph, the IRI of the documented artefact, the imported modules, the warnings and the format (`read_as`).

**What it gives.** `instances()` and `get_instance()` list its entities, so a consumer never needs the reader that built it. Viewers, the builder and the API depend on this object only.

**Provenance.** The triples an entity was built from, computed on demand with `artefact.provenance(entity)`. Nothing is precomputed: a documentation can hold thousands of entities and most are never inspected.

**You write.** A subclass with no code, so users can read the format with `MyFormat(path)`.
+++
[Python API](usage/python_api.md) · [See Extending LODE](extending.md)
:::

:::{card} 4. Viewer
**What it does.** Turns the artefact into the dictionaries the HTML templates render, and into RDF serializations. `lode.viewer.get_viewer(artefact)` picks the viewer from `artefact.read_as`, asking the registry for the viewer class of that profile.

**You change.** What each format shows (table of contents, display names, card template) is declared in the `viewer.yaml` and the `templates/` folder of its profile. A `viewer.py` is needed only for what those cannot say.
+++
[See Extending LODE](extending.md)
:::
::::

## Dependency rules

- The viewer does not import the reader.
- The model imports neither the reader nor the viewer.
- The reader does not import the viewer.
- The core (reader, viewer, model, helpers) reaches a profile only through the registry in `lode.profiles`. It never imports a profile package.
- A profile does not import another profile.

`tests/test_architecture.py` checks these rules on the source files, so a violation fails the test suite.
