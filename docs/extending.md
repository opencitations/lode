# Extending LODE

:::{warning} Beta version · unstable
LODE 2 is under development and in beta: anything described in this documentation may change. This page describes internals that can change without notice.
:::

A new format (OWL, SKOS, ...) is a **profile**: a package you add under `lode/profiles/`. You do not change how a source is read, you say what to look for in it. This page shows how, with SKOS as the example. The layers are described in [Architecture](architecture.md).

::::{div}
:class: text-center
```{mermaid}
%%{init: {"themeVariables": {"fontSize": "16px"}, "flowchart": {"nodeSpacing": 30, "rankSpacing": 30, "padding": 12}}}%%
flowchart LR
    source(["Source<br/>file or URL"])
    loader["Loader<br/>RDF graph"]
    reader["Reader<br/>six phases"]
    model[["Model<br/>entity classes"]]
    artefact["Artefact<br/>entities and graph"]
    profile{{"Profile<br/>of the format"}}

    source --> loader --> reader
    reader -. instantiates .-> model
    reader -- populates --> artefact
    profile -. supplies .-> reader
    profile -. supplies .-> artefact

    classDef flow fill:#dbeafe,stroke:#60a5fa,color:#1f2937
    classDef shared fill:#fef3c7,stroke:#f59e0b,color:#1f2937
    classDef io fill:#e5e7eb,stroke:#9ca3af,color:#1f2937
    class loader,reader,artefact flow
    class model,profile shared
    class source io
```
::::

The profile is where you plug in.

## Anatomy of a profile

A profile lives in `lode/profiles/<format>/`, where `<format>` is its lowercase name. That name is also the value of `read_as`.

| File | Role |
|------|------|
| `__init__.py` | Declares the `Profile` and registers it. |
| `reader.yaml` | The mapper: which RDF constructs become which model classes. |
| `reader.py` | Only what the mapper cannot say. |
| `artefact.py` | The class users read the format with (`SkosVocabulary`). It carries no code. |
| `viewer.yaml` | What the viewer shows: names, table of contents, vocabulary. |
| `viewer.py` | The viewer class. Empty when the YAML says everything. |
| `templates/` | Optional. Templates that replace the base ones, matched by file name. |

## Step 1. Write the mapper

`reader.yaml` is merged on top of `lode/reader/config/base.yaml`, so a format inherits `rdfs:label`, `rdfs:comment` and the other shared entries. It has four keys: `namespaces`, `punning_priority`, `mapper` and `enricher` (use `{}` when there are no group axioms). The work is in `mapper`, one entry per RDF class or predicate.

An RDF class becomes a model class:

```yaml
skos:Concept:
  is: class
  target_class: Concept
```

A predicate fills a field through a setter of the model class. `Literal` marks a literal value:

```yaml
skos:prefLabel:
  is: predicate
  target_classes: [Resource]
  setters: [set_has_preferred_label: Literal]
```

A relation names the class of its target. `inverse_of` fills the other side too, so the inverse does not have to be in the source:

```yaml
skos:broader:
  is: predicate
  target_classes: [Concept]
  setters:
    - set_is_sub_concept_of:
        targets: Concept
        inverse_of: set_is_super_concept_of
```

A predicate that needs real code names a handler, written in Step 2:

```yaml
skos:memberList:
  is: predicate
  target_classes: [Collection]
  handler: handle_member_list
```

An unknown model class raises `KeyError` when the configuration loads, and a handler missing from the reader class raises `AttributeError` when the reader is built.

## Step 2. Write the reader class

Skip this step when the YAML says everything. Otherwise subclass `Reader` in `reader.py` and override only what differs. `SkosReader` has one handler:

```python
class SkosReader(Reader):
    """SKOS reader."""

    def handle_member_list(self, entity, uri, predicate, obj, value):
        """Handle skos:memberList: add every item of the RDF list as a member, in order."""
        if not self._is_rdf_collection(obj):
            return False
        for item in RDFLibCollection(self.graph, obj):
            ...
```

A handler has the signature `(self, entity, uri, predicate, obj, value)`:

- Returning `False` means the triple is not for this entity: it ends up as a `Statement`.
- Any other value means it was handled, and the reader records it as provenance.
- An exception is logged as a warning and the triple becomes a `Statement`. Errors are never silently dropped.

Every module, class and method needs a docstring, in English.

## Step 3. Declare the profile

`__init__.py` declares the profile and registers it:

```python
"""SKOS profile: concept schemes read with reader.yaml and shown by SkosViewer."""
from lode.profiles import Profile, register

register(Profile(
    name="skos",
    package=__name__,
    reader=".reader:SkosReader",
    viewer=".viewer:SkosViewer",
    artefact=".artefact:SkosVocabulary",
))
```

Classes are given as `module:Name`; a module that starts with a dot is relative to `package`. They are imported only when needed, so `lode.profiles` stays free of reader and viewer imports.

To load a profile that ships in the repository, add its package to `_BUILTIN` in `lode/profiles/__init__.py`. Set `enabled=False` until the format is finished: the CLI and the API refuse it, while its `Artefact` class still reads it.

## The artefact class

Subclass `Artefact`. The profile names the class, so the class carries nothing else:

```python
class MyFormat(Artefact):
    """A <format> artefact: read one with MyFormat(source)."""
```

Users read the format with `MyFormat("file.ttl")`. A caller that only has the name, such as the CLI or the web service, uses `lode.read(source, "<format>")`.

## Step 4. Try it

Save a small vocabulary as `fruit.ttl`:

```turtle
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix ex:   <http://example.org/fruit#> .

ex:scheme a skos:ConceptScheme ;
    skos:prefLabel "Fruit"@en .

ex:fruit a skos:Concept ;
    skos:inScheme ex:scheme ;
    skos:prefLabel "Fruit"@en .

ex:citrus a skos:Concept ;
    skos:inScheme ex:scheme ;
    skos:prefLabel "Citrus"@en ;
    skos:broader ex:fruit .
```

Read it and inspect the artefact:

```python
from lode import SkosVocabulary
from lode.models import Concept, Model, Statement

artefact = SkosVocabulary("fruit.ttl")

print(artefact.artefact_iri)
for cls in (Model, Concept, Statement):
    print(cls.__name__, [str(e.get_has_identifier()) for e in artefact.get_entities(cls)])
```

```text
http://example.org/fruit#scheme
Model ['http://example.org/fruit#scheme']
Concept ['http://example.org/fruit#fruit', 'http://example.org/fruit#citrus']
Statement []
```

The empty `Statement` list is the quick check for a new mapper: every triple it does not consume becomes a `Statement`, so a non-empty list points at the constructs still missing from the YAML.

## The viewer

`viewer.yaml` has two required keys, `type_map` and `toc`, and two optional ones, `vocabulary` and `characteristics`. From `lode/profiles/skos/viewer.yaml`:

```yaml
type_map:
  concept:    {singular: Concept,    plural: Concepts,    abb: c}

toc:
  - [Concept,    concepts,    Concept]

vocabulary:
  is sub concept of: broader
```

`type_map` gives the display names, `toc` the sections in order (model class, section id, `type_map` key), `vocabulary` the words shown instead of the internal ones. A missing file or key raises `ValueError`.

The viewer class is a subclass of `BaseViewer`, and it can be empty:

```python
class MyViewer(BaseViewer):
    """Viewer of the <format> profile: everything it shows comes from viewer.yaml."""
```

A profile that needs a different page puts the templates that differ in `templates/`. A file there replaces the base file of the same name; the others come from `lode/templates/`.

## Shipping a profile as a plugin

A profile can live in its own package, installed next to LODE. It exposes the profile as an object:

```python
# lode_shacl/__init__.py
from lode.profiles import Profile

PROFILE = Profile(
    name="shacl",
    package=__name__,
    reader="lode_shacl.reader:ShaclReader",
    viewer="lode_shacl.viewer:ShaclViewer",
    artefact="lode_shacl.artefact:ShaclRules",
)
```

and announces it in its own `pyproject.toml`:

```toml
[project.entry-points."lode.profiles"]
shacl = "lode_shacl:PROFILE"
```

After `pip install lode-shacl`, `shacl` is a valid `read_as` in the CLI, the API and `lode.read`. The package must be a regular package on disk, because `reader.yaml`, `viewer.yaml` and `templates/` are read from its folder.

A mapper can use model classes of the plugin, written as `module:Name` in `target_class`, `target_classes`, `inferred_class` and `punning_priority`:

```yaml
shacl:NodeShape:
  is: class
  target_class: "lode_shacl.models:Shape"
```

A plugin that fails to load is skipped and logged. A plugin cannot take the name of a registered format. A profile imports the core and the models, never another profile.
