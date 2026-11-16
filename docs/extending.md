# Extending LODE

LODE is extended by adding a package next to the existing ones, not by changing the
core. A format (OWL, SKOS, ...) is a **profile**: a package under `lode/profiles/` that
holds everything that format needs. This page shows how to write one, using SKOS as the
worked example: it is the smallest complete format in the code base, a YAML mapper plus
a 40-line logic class and a small viewer. The last section shows how to ship a profile
as a separate package, without touching LODE.

## Rules every extension follows

- **The mapping is data.** The translation from RDF constructs to model classes is
  declared in YAML. Python is written only for what YAML cannot express.
- **Layers stay independent.** The reader does not import the viewer, and the models
  import neither. The core reaches a profile only through the registry
  (`lode.profiles`), never by importing its package, and a profile never imports
  another profile. `tests/test_architecture.py` fails when this is broken.
- **The reader hands over an `Artefact`.** Nothing downstream reads from the Reader
  or from its logic, so a new format needs no change outside its own package.

## Anatomy of a profile

A profile lives in `lode/profiles/<format>/`. Replace `<format>` with its lowercase
name (`skos`, for example).

| File | Role |
|------|------|
| `__init__.py` | Declares the `Profile` and registers it. |
| `reader.yaml` | The mapper: which RDF constructs become which model classes. |
| `logic.py` | Implements what the mapper cannot express. |
| `viewer.yaml` | What the viewer shows: display names, table of contents, vocabulary. |
| `viewer.py` | The viewer class. It can be as small as one line that names the YAML. |
| `templates/` | Optional. Templates that replace the base ones, matched by file name. |

The name of the folder is the name of the format. It is also the value of `read_as`.
`tests/test_formats_registry.py` fails when a registered profile points to a class that
does not exist or lacks one of its YAML files.

## Adding a format: the reader

### Step 1. Write the mapper

The mapper is `reader.yaml`, a YAML file with five top-level keys:

| Key | Meaning |
|-----|---------|
| `namespaces` | Predicates outside these namespaces are not mapped. Their triples are kept as `Statement` instances. |
| `allowed_classes` | The model classes this format may create. |
| `punning_priority` | Which class wins when one IRI has several types. |
| `mapper` | One entry per RDF class or predicate. |
| `enricher` | Handlers for group axioms (OWL). Use `{}` when there are none. |

The file is merged on top of `lode/reader/config/base.yaml`. Dictionaries are merged key
by key, so a format inherits `rdfs:label`, `rdfs:comment` and the other shared entries.
Any other value, lists included, is replaced: `allowed_classes` in
`lode/profiles/skos/reader.yaml` replaces the one in `base.yaml`.

A `mapper` entry takes one of the following shapes, all taken from that file.

An RDF class becomes a model class:

```yaml
skos:Concept:
  is: class
  target_class: Concept

skos:ConceptScheme:
  is: class
  target_class: Model
```

A predicate fills a field through a setter of the model class. `Literal` marks a
literal value:

```yaml
skos:prefLabel:
  is: predicate
  target_classes: [Resource]
  setters: [set_has_preferred_label: Literal]
```

A relation between entities names the class of its target. `inverse_of` makes the
reader also call the inverse setter on the target, so the inverse statement does not
have to be asserted in the source:

```yaml
skos:broader:
  is: predicate
  target_classes: [Concept]
  setters:
    - set_is_sub_concept_of:
        targets: Concept
        inverse_of: set_is_super_concept_of
```

A predicate that needs real code names a handler, which Step 2 implements:

```yaml
skos:memberList:
  is: predicate
  target_classes: [Collection]
  handler: handle_member_list
```

The mapper fails early on mistakes. An unknown model class name raises `KeyError` when
the configuration is loaded, and a handler that does not exist on the logic class raises
`AttributeError` when the logic is built.

### Step 2. Write the logic class

`BaseLogic` already runs the extraction phases (classify, create instances, populate
properties, group axioms, fallback, statements). A format subclasses it in `logic.py` and
overrides only what differs. `SkosLogic` overrides one phase and adds one handler:

```python
class SkosLogic(BaseLogic):
    """SKOS logic."""

    def phase1_classify_from_predicates(self):
        """Do nothing: in SKOS the class always comes from rdf:type."""
        logger.debug("Phase 1 (SKOS classification): skipped, SKOS uses only rdf:type which is handled in phase 2")

    def handle_member_list(self, instance, uri, predicate, obj, value):
        """Handle skos:memberList: add every item of the RDF list as a member, in order.

        The list is expanded here because a plain setter would receive the list head, not
        its items. [...]
        """
        if not self._is_rdf_collection(obj):
            return False
        for item in RDFLibCollection(self.graph, obj):
            ...
```

A handler has the signature `(self, instance, uri, predicate, obj, value)` and follows
this contract:

- Returning `False` means the triple is not admissible for this instance. It is not
  consumed and ends up as a `Statement`.
- Any other return value means the triple was handled. The reader records it as the
  provenance of the instance.
- An exception is logged as a warning and the triple is left unhandled, so it also ends
  up as a `Statement`. Errors are never silently dropped.

Every module, class and method needs a docstring, in English. The class needs no export:
the profile names it by path, as Step 3 shows.

### Step 3. Declare the profile

`__init__.py` declares the profile and registers it:

```python
"""SKOS profile: concept schemes read with reader.yaml and shown by SkosViewer."""
from lode.profiles import Profile, register

register(Profile(
    name="skos",
    package=__name__,
    logic="lode.profiles.skos.logic:SkosLogic",
    viewer="lode.profiles.skos.viewer:SkosViewer",
))
```

| Field | Meaning |
|-------|---------|
| `name` | The name of the format, and the value of `read_as`. |
| `package` | The package that holds `reader.yaml`, `viewer.yaml` and `templates/`. Use `__name__`. |
| `logic` | The logic class, as `module:Name`. |
| `viewer` | The viewer class, as `module:Name`. |
| `post_checks` | Optional `module:function`, called with the logic after extraction. OWL uses it for its warnings. |
| `enabled` | `True` by default. |

Classes are given as strings and imported only when they are needed. That keeps
`lode.profiles` free of reader and viewer imports, so every layer can read it.

To make LODE load a profile that ships in the repository, add its package to `_BUILTIN` in
`lode/profiles/__init__.py`.

Set `enabled=False` until the format is finished. The CLI and the API refuse formats that
are not enabled; `lode.read` does not, so you can try the format while you develop it.

### Step 4. Try it on an artefact

Save this vocabulary as `fruit.ttl`:

```turtle
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix ex:   <http://example.org/fruit#> .

ex:scheme a skos:ConceptScheme ;
    skos:prefLabel "Fruit"@en ;
    skos:hasTopConcept ex:fruit .

ex:fruit a skos:Concept ;
    skos:inScheme ex:scheme ;
    skos:topConceptOf ex:scheme ;
    skos:prefLabel "Fruit"@en ;
    skos:definition "Edible product of a plant."@en .

ex:citrus a skos:Concept ;
    skos:inScheme ex:scheme ;
    skos:prefLabel "Citrus"@en ;
    skos:altLabel "Citrus fruit"@en ;
    skos:broader ex:fruit .

ex:lemons a skos:Collection ;
    skos:prefLabel "Lemons"@en ;
    skos:member ex:citrus .
```

Read it and inspect the `Artefact`:

```python
import lode

artefact = lode.read("fruit.ttl", "skos")

print(artefact.read_as)           # skos
print(artefact.ontology_iri)      # http://example.org/fruit#scheme

for name in ("Model", "Concept", "Collection", "Statement"):
    print(name, [str(i.get_has_identifier()) for i in artefact.instances(name)])
```

```text
skos
http://example.org/fruit#scheme
Model ['http://example.org/fruit#scheme']
Concept ['http://example.org/fruit#fruit', 'http://example.org/fruit#citrus']
Collection ['http://example.org/fruit#lemons']
Statement []
```

What the mapper did:

- `skos:ConceptScheme` became a `Model`, and its IRI is the `ontology_iri` of the
  artefact.
- `skos:Concept` and `skos:Collection` became `Concept` and `Collection` instances.
- Only `skos:broader` is asserted between `ex:citrus` and `ex:fruit`. The `inverse_of`
  setter also filled the other side:

```python
fruit = next(iter(artefact.get_instance("http://example.org/fruit#fruit")))
[str(c.get_has_identifier()) for c in fruit.get_is_super_concept_of()]
# ['http://example.org/fruit#citrus']
```

The empty `Statement` list is the quick check for a new mapper. Every triple the mapper
does not consume becomes a `Statement` in the last phase, so a non-empty list points at
the constructs still missing from the YAML.

## Adding a format: the viewer

A format is complete only when it also has a viewer. What differs between formats is data,
so most of the viewer is `viewer.yaml`, and the class can stay small.

### The viewer settings

`viewer.yaml` has two required keys and two optional ones:

| Key | Meaning |
|-----|---------|
| `type_map` | Required. Display names of the entity types, keyed by the lowercase model class name: `singular`, `plural` and the short badge `abb`. |
| `toc` | Required. The table of contents in display order: model class name, section id, and the `type_map` key. Only these classes get their own card and link. |
| `vocabulary` | Optional. Words shown instead of the internal ones, applied to the labels of properties. SKOS shows `broader` where the model says `is sub concept of`. |
| `characteristics` | Optional. Boolean flags of an entity that the card lists, such as `is_ordered`. |

From `lode/profiles/skos/viewer.yaml`:

```yaml
vocabulary:
  is sub concept of: broader
  is super concept of: narrower

type_map:
  concept:    {singular: Concept,    plural: Concepts,    abb: c}
  collection: {singular: Collection, plural: Collections, abb: col}

toc:
  - [Concept,    concepts,    Concept]
  - [Collection, collections, Collection]

characteristics:
  - is_ordered
```

A missing file or a missing required key raises `ValueError` when the viewer is built:
a silent default would change the page without a trace.

### The viewer class

Subclass `BaseViewer` and name the profile in `CONFIG_NAME`. That is the whole class
when the YAML says everything:

```python
class MyViewer(BaseViewer):
    """Viewer of the <format> profile: everything it shows comes from viewer.yaml."""

    CONFIG_NAME = "<format>"
```

Override `view()` only to add data. `SkosViewer` calls the base method and adds the
taxonomy of the concepts to every section of the navigation. The data the viewer returns
follows the contract in `lode/viewer/view_data.py`: `model`, `toc`, `types`, `entities`,
`focus` and `error`, so a template written from the contract works with any format. The
[viewer contract](usage/viewer_contract.md) describes every key and walks through how
SKOS adds its own.

### Templates

A profile that needs a different page keeps the templates that differ in its own
`templates/` folder. A file there replaces the base file with the same name, and every
file it does not provide comes from `lode/templates/`. SKOS replaces `_toc.html` to draw
its taxonomy and uses the base page for everything else.
`docs/examples/minimal.html` is a complete template written from the contract alone.

## Shipping a format as a plugin

A profile does not have to live in the LODE repository. A package that you install next
to LODE can register its own format, and LODE finds it at the first use.

The package has the layout of the table above, with its own name in place of
`lode.profiles.<format>`. It exposes the profile as an object:

```python
# lode_shacl/__init__.py
from lode.profiles import Profile

PROFILE = Profile(
    name="shacl",
    package=__name__,
    logic="lode_shacl.logic:ShaclLogic",
    viewer="lode_shacl.viewer:ShaclViewer",
)
```

and announces it in its own `pyproject.toml`, not in the one of LODE:

```toml
[project.entry-points."lode.profiles"]
shacl = "lode_shacl:PROFILE"
```

After `pip install lode-shacl`, `shacl` is a valid value of `read_as` in the CLI, the API
and `lode.read`. The package must be a regular package on disk, because `reader.yaml`,
`viewer.yaml` and `templates/` are read from its folder.

A mapper can use model classes defined by the plugin. Write the class as `module:Name`
wherever the mapper names a class:

```yaml
shacl:NodeShape:
  is: class
  target_class: "lode_shacl.models:Shape"
```

This works for `target_class`, `target_classes`, `inferred_class` and `punning_priority`.
The arguments of `setters` still accept only the classes of `lode.models`.

LODE protects itself from plugins:

- A plugin that fails to load is skipped, and the failure is logged with the name of the
  plugin. The other formats keep working.
- A plugin cannot take the name of a registered format: the profile that was there first
  stays, and the plugin is skipped with a warning.
- Like any profile, a plugin imports the core and the models, never another profile.
