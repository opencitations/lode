# Extending LODE

LODE is extended by adding data and small classes next to the existing ones, not by
changing the core. This page shows how, using SKOS as the worked example: it is the
smallest complete format in the code base, a YAML mapper plus a 40-line logic class.

## Rules every extension follows

- **The mapping is data.** The translation from RDF constructs to model classes is
  declared in YAML. Python is written only for what YAML cannot express.
- **Layers stay independent.** The reader does not import the viewer, and the models
  import neither. `tests/test_architecture.py` fails when this is broken.
- **The reader hands over an `Artefact`.** Nothing downstream reads from the Reader
  or from its logic, so a new format needs no change outside its own files.

## Adding a format: the reader

A format needs three pieces on the reader side. Replace `<format>` with its lowercase
name (`skos`, for example).

| Piece | File | Role |
|-------|------|------|
| Mapper | `lode/reader/config/<format>.yaml` | Declares which RDF constructs become which model classes. |
| Logic | `lode/reader/logic/<format>_logic.py` | Implements what the mapper cannot express. |
| Registry entry | `CONFIGURATION_REGISTRY` in `lode/helpers/formats.py` | Binds the format name to its logic class. |

A format is complete only when it also has a viewer. `tests/test_formats_registry.py`
fails until the viewer is registered.

### Step 1. Write the mapper

The mapper is a YAML file with five top-level keys:

| Key | Meaning |
|-----|---------|
| `namespaces` | Predicates outside these namespaces are not mapped. Their triples are kept as `Statement` instances. |
| `allowed_classes` | The model classes this format may create. |
| `punning_priority` | Which class wins when one IRI has several types. |
| `mapper` | One entry per RDF class or predicate. |
| `enricher` | Handlers for group axioms (OWL). Use `{}` when there are none. |

The file is merged on top of `base.yaml`. Dictionaries are merged key by key, so a
format inherits `rdfs:label`, `rdfs:comment` and the other shared entries. Any other
value, lists included, is replaced: `allowed_classes` in `skos.yaml` replaces the one
in `base.yaml`.

A `mapper` entry takes one of the following shapes, all taken from `skos.yaml`.

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
properties, group axioms, fallback, statements). A format subclasses it and overrides
only what differs. `SkosLogic` overrides one phase and adds one handler:

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

Every module, class and method needs a docstring, in English. Export the class from
`lode/reader/logic/__init__.py` by adding its import and its name to `__all__`.

### Step 3. Register the format

In `lode/helpers/formats.py`, add one line to the registry:

```python
CONFIGURATION_REGISTRY = {
    'owl': 'OwlLogic',
    'rdf': 'RdfLogic',
    'skos': 'SkosLogic',
}
```

The key is the format name. It is also the stem of the YAML file and the value of
`read_as`. The value is the name of the logic class in `lode.reader.logic`. The
registry holds plain strings on purpose: that module is imported by every layer and
must not import the reader or the viewers.

Leave the format out of `ENABLED_FORMATS` until it is finished. The CLI and the API
refuse formats that are not enabled; `lode.read` does not, so you can try the format
while you develop it.

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
