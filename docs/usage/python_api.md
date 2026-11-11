# Python API

LODE can be used as a library, without the CLI or the web service. Reading an
artefact gives you its entities as plain Python objects; rendering is a
separate, optional step.

Use it when you want to extract data from OWL or SKOS artefacts in your own
pipeline, or to build your own renderer. If you only need documentation pages,
use [`lode build`](cli.md).

## Install

```bash
pip install oc-lode
```

The base install is enough. The `[server]` extra is only for the web service.

## Quick example

```python
import lode

artefact = lode.read("vocabulary.ttl", "skos")

for concept in artefact.instances("Concept"):
    print(concept.get_has_identifier(),
          [l.get_has_value() for l in concept.get_has_preferred_label()])

lode.build_site(artefact, "site")
```

On a vocabulary with a scheme and two concepts this prints:

```
http://example.org/animal ['animal']
http://example.org/cat ['cat']
```

and writes `site/index.html` together with the serializations of the artefact
(`index.ttl`, `index.xml`, `index.nt`, `index.jsonld`) and one page per resource.

## Reading

```python
artefact = lode.read(source, read_as, *, imported=False, closure=False,
                     partial_import=False, warnings=False)
```

| Argument | Meaning |
|----------|---------|
| `source` | A local path or a public http(s) URL. URLs go through the same safety checks as the web service. |
| `read_as` | `"owl"`, `"skos"` or `"rdf"`. |
| `imported`, `closure`, `partial_import` | Switches that load the `owl:imports` of the artefact: at depth 1, the full closure, or only the imported entities that are actually used. |
| `warnings` | Collect reader warnings in `artefact.warnings`. The current checks are OWL-specific: leave it off for SKOS. |

`lode.read` is blocking and may fetch remote documents. A failure raises a
subclass of `lode.exceptions.LODEError`, which carries a `context` dictionary
(which file, which URL, which limit).

## The Artefact

`lode.read` returns an `Artefact`: everything extracted from the source, with
no reference to the code that read it.

| Member | Content |
|--------|---------|
| `instances(class_name=None)` | The extracted entities as a list; with a class name, only those of that class. |
| `get_instance(iri)` | The entities registered under an IRI, or `None`. |
| `graph` | The RDF graph, including imported modules when requested. |
| `main_graph()` | Only the triples of the loaded artefact. |
| `ontology_iri` | The IRI of the documented ontology or concept scheme, if any. |
| `imported_uris` | IRIs of the modules pulled in by imports. |
| `warnings` | Reader warnings, when requested. |
| `provenance` | `provenance.for_instance(instance)` returns an `rdflib.Graph` with the triples the instance was built from. It is computed on demand. |
| `read_as` | The format the artefact was read as. |

## Walking the model

`artefact.instances("Concept")` takes the **exact name** of a model class.
Subclasses are not included, and an unknown name gives an empty list. The
classes you will meet are:

| Format | Classes |
|--------|---------|
| SKOS | `Concept`, `Collection`, `Model` (the concept scheme) |
| OWL | `Concept` (classes), `Relation`, `Attribute`, `Annotation`, `Individual`, `Model` (the ontology), and others |

Model objects expose their data through getters named after the property:
`get_has_preferred_label()`, `get_is_sub_concept_of()`, `get_has_member()`.
Literals are objects with `get_has_value()` and `get_has_language()`.

An IRI used for more than one kind of entity (punning) comes back as several
instances from `get_instance(iri)`.

To see where an entity comes from:

```python
triples = artefact.provenance.for_instance(concept)
print(triples.serialize(format="turtle"))
```

## Rendering

`lode.build_site(artefact, out_dir, *, lang="en", artefact_name="index")`
writes the same static site as `lode build`. Existing files with the same names
in `out_dir` are overwritten.

For finer control, use the viewer directly. It is chosen from
`artefact.read_as`:

```python
from lode.viewer import get_viewer

viewer = get_viewer(artefact)
ttl = viewer.export_main("turtle")          # the loaded artefact only
one = viewer.export_resource("http://example.org/cat", "turtle")
data = viewer.get_view_data(language="en")  # dictionary for the HTML templates
```

`export_*` accept `turtle`, `xml`, `nt` and `jsonld`.

## What is stable

Supported: `lode.read`, `lode.build_site`, the members of `Artefact` listed
above, the getters of the model classes in `lode.models`,
`lode.viewer.get_viewer`, `export_main` and `export_resource`.

Not covered by any stability promise: names starting with an underscore, and
the shape of the dictionary returned by `get_view_data`, which follows the
needs of the templates.

`lode.read` is a thin wrapper around `lode.reader.Reader`, which stays
available for advanced use: `reader.load_instances(...)` followed by
`reader.get_artefact()` gives the same result.

!!! note
    The CLI and the web service accept only the formats enabled in the current
    release. The library itself does not enforce that: `rdf` can be read but is
    not yet supported.