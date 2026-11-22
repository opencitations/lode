# Python library

:::{note} Beta version
LODE 2 is under development and in beta: anything described in this documentation may change.
:::

LODE works as a library, without the CLI or the web service: read a source, get its entities as plain Python objects, and render them if you want. If you only need documentation pages, use [`lode build`](cli.md).

```bash
pip install oc-lode
```

## Read

Each format has its own class, `OwlOntology` or `SkosVocabulary`. The source is a local path or a public http(s) URL. Pass a URL as a plain string, never as a `Path`: on Windows a `Path` rewrites the slashes.

```python
from lode import OwlOntology

ontology = OwlOntology("http://purl.org/spar/cito/")
```

When the format is only known as a string, use `lode.read`. It returns the same class:

```python
import lode

ontology = lode.read("http://purl.org/spar/cito/", "owl")
```

Options, for both: `imported=True` also loads the `owl:imports` of the ontology (`closure=True` loads imports of imports, `partial_import=True` only the imported entities that are used), and `warnings=True` collects the reader warnings in `ontology.warnings`.

Reading blocks and may fetch remote documents. A failure raises a subclass of `lode.exceptions.LODEError`, with a `context` dictionary (which file, which URL, which limit).

## Walk the entities

```python
from lode.models import Concept

for concept in ontology.get_entities(Concept)[:3]:
    print(concept.get_has_identifier(), [l.get_has_value() for l in concept.get_has_label()])

ontology.get_entities_by_iri("http://purl.org/spar/cito/cites")   # a set, or None
```

`get_entities(cls)` takes a class from `lode.models`; subclasses are included, and without an argument you get everything. Fields are read with getters named after them (`get_has_label()`, `get_is_sub_concept_of()`). The classes of each format are in [Model](../examples/model.ipynb).

To see which triples an entity comes from: `ontology.provenance(concept)` returns an `rdflib.Graph`.

## Render

```python
lode.build_site(ontology, "site")
```

It writes the same static site as `lode build`: `index.html`, the serializations and one page per resource. Existing files with the same names are overwritten.

For one serialization, use the viewer:

```python
from lode.viewer import get_viewer

viewer = get_viewer(ontology)
ttl = viewer.export_main("turtle")                                    # the loaded artefact
one = viewer.export_resource("http://purl.org/spar/cito/cites", "turtle")   # one resource
```

The formats are `turtle`, `xml`, `json-ld` and `nt`.

## What is stable

`lode.read`, `lode.build_site`, the `Artefact` classes and their members, the getters of `lode.models`, `get_viewer`, `export_main` and `export_resource`. Names that start with an underscore and the dictionary returned by `viewer.view` are not covered.

## Going further

- [Architecture](../architecture.md): the layers, and what each one holds.
- [Extending LODE](../extending.md): add a format of your own.
