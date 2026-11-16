# Viewer contract

A viewer turns an `Artefact` into a plain dictionary, and a template reads that
dictionary and nothing else. This page describes the dictionary, how to write a template
for it, and how a profile adds its own data to it.

The dictionary is a `ViewData`. The classes that describe it are in
`lode/viewer/view_data.py`. They are `TypedDict` classes and are not used at runtime: they
are the reference for whoever writes a template or a viewer, and
`tests/test_view_data.py` checks that the viewers keep to them.

## Rules

- **Every key listed is always present.** An empty list, an empty dictionary or `None`
  says "nothing", never a missing key. A template never asks whether a key exists.
- **Labels are already in the requested language**, with the fallback applied.
- **Lists keep a meaningful order**: entities by label, relations in display order.
- **Nothing depends on how the data is drawn.** There is no HTML and no CSS class.

## What a viewer returns

```python
data = viewer.view(resource_uri=None, language=None, links=None)
```

`resource_uri` asks for the page of one resource, and without it the view is the whole
artefact. `language` is a language tag, `"en"` by default. `links` decides where each link
goes, as the next section explains.

| Key | Meaning |
|-----|---------|
| `model` | The documented artefact: its header, namespaces, the serializations on offer and the reader warnings. |
| `toc` | The navigation of the whole artefact, as sections. It is `[]` on the page of one resource. |
| `types` | How each type is called, by the model class name that `type` carries: `singular`, `plural` and `abbreviation`. |
| `entities` | What the main part shows: all the cards, one, or none. |
| `focus` | The IRI that was asked for, `None` for the whole artefact. |
| `error` | A message when the request cannot be answered, `None` otherwise. |

There are three kinds of view. The **whole artefact** has every card in `entities`, a
filled `toc` and `focus` set to `None`. **One resource** has one card, an empty `toc` and
`focus` set to its IRI: a site of N resources does not carry N copies of its own index.
An **error** has no card and a message in `error`.

The top level of `ViewData` is fixed, and `test_top_level_keys` fails when a key is added
or removed. A profile adds its data inside the existing structures, as SKOS does.

### The structures inside

An **entity** is the content of one card:

| Key | Meaning |
|-----|---------|
| `iri`, `type`, `label` | Who it is. `type` is the model class name, for example `Concept`. |
| `anchor` | A stable HTML id for this entity. |
| `href`, `kind` | Where its page is, and whether it is an `"anchor"`, a `"page"` or `"external"`. Both are `None` when it has no page. |
| `deprecated` | `True` when the entity is deprecated. |
| `relations` | Display name of a relation, with its list of values. |
| `statements` | The same for the predicates the mapper did not turn into a field. |
| `characteristics` | Flags such as `"is symmetric"`. |
| `provenance` | The triples the entity was built from, serialized, or `[]`. |

A **value** is one piece of data on a card or in the header: a text, possibly a link,
possibly structured.

| Key | Meaning |
|-----|---------|
| `text`, `language` | What is shown and the language tag of a literal. |
| `iri` | The resource the value stands for, when it is one. |
| `href`, `kind` | Where a click goes, as for an entity. |
| `type` | The model class name: `"Literal"`, `"Concept"`, `"PropertyChain"`... |
| `deprecated`, `imported` | The value is deprecated, or defined in an imported module. |
| `visualize` | Header only: the address that opens LODE on this ontology. |
| `parts` | The components of a class expression or of a property chain, or `[]`. |
| `nested` | The annotations carried by a value that is itself a statement, or `None`. |

A **section of the navigation** has `id`, `type`, `label` and `entities`, a list of
entries with `iri`, `type`, `label`, `anchor`, `href` and `kind`: an entity without
relations and statements. The **model** has `iri`, `label`, `metadata`, `namespaces`,
`serializations`, `warnings` and `href`.

`new_value(**fields)` in `view_data.py` returns a value with every key present. A viewer
starts from it, so no value ever lacks a key that a template reads.

### Where the links go

A viewer does not decide the address of a link: the same data serves the web service,
where a resource is an anchor or a query, and the static site, where it is a file. The
caller passes a `Links` object, and once the page is complete `resolve_links` fills in
`href` and `kind` everywhere in the contract. A link follows the first rule that applies:

1. the card is on this very page, so it is an anchor;
2. it belongs to this documentation, so it goes where `Links` says;
3. otherwise it is outside, and goes to its own IRI.

When `Links` gives no address for a page of this documentation, the link has no `href`
and no `kind`, and a template shows it as plain text.

## Writing a template

The base templates are in `lode/templates/`:

| File | Role |
|------|------|
| `page.html` | The whole page. It needs one global from the adapter, `url_for(name, path)`, to find the stylesheet. |
| `_toc.html` | The navigation: the macros `sidebar` and `contents`. |
| `_card.html` | The macro `card`, the content of one entity. |
| `_value.html` | The macro `value`, one value with its link, language and nested parts. |
| `_metadata.html` | The macro `metadata_block`, the header of the artefact. |
| `error.html` | The page of an error. |

`docs/examples/minimal.html` is a complete template written from the contract alone. The
tests render it with `StrictUndefined`, so a key outside the contract fails there. It draws
the `tree` of a section when there is one, and tests with `is defined` first, because `tree`
belongs to SKOS and not to the contract.

A viewer says where its templates are with `template_dirs()`: the `templates/` folder of
its profile first, then `lode/templates/`. The first folder that has the file wins. A
profile therefore replaces a template by giving it the same name, and every template it
does not provide comes from the base. `page.html` imports `sidebar` and `contents` from
`_toc.html`, so a profile that replaces `_toc.html` must keep those two macro names.

## Adding data to a viewer

A profile adds data when the contract has no place for it. SKOS needs a taxonomy of its
concepts, so each section of its navigation carries a `tree`. The steps are the same for
any addition. The code is in `lode/profiles/skos/viewer.py`.

**1. Declare the shape.** Extend the contract classes with the new key. They are not
enforced at runtime, so this is documentation: it tells whoever writes a template for the
profile what to expect. The top level of `ViewData` stays the same, and the new key goes
inside a section. The tests accept extra keys below the top level and fail only when a key
the contract declares is missing.

```python
class TreeNode(TocEntity):
    """One node of the concept taxonomy: a concept and the concepts narrower than it."""

    children: List["TreeNode"]


class SkosTocSection(TocSection):
    """A section of the SKOS navigation: the base one plus the taxonomy of its concepts.

    The section of the collections has an empty `tree`.
    """

    tree: List[TreeNode]
```

**2. Add the data where it is built.** Override the step of the base viewer that builds
that part, call it, and add to its result. Give the key to *every* section, with an empty
list where there is nothing, so the template never checks that it exists.

```python
def _build_toc(self, language: str) -> List[TocSection]:
    toc = super()._build_toc(language)
    concepts = [i for i in self.get_toc_instances() if type(i).__name__ == 'Concept']
    for section in toc:
        section['tree'] = self._build_taxonomy(concepts, language) if section['type'] == 'Concept' else []
    return toc
```

**3. Give the new items their links.** The links of the structures in the contract are
filled in for you. An item that you add is not one of them, so it must copy the address
from the entry of the contract that has the same IRI. `SkosViewer` does it in `view()`,
after the base method has run:

```python
def view(self, resource_uri=None, language=None, links=None) -> ViewData:
    data = super().view(resource_uri, language, links)
    for section in data['toc']:
        addresses = {e['iri']: (e['href'], e['kind']) for e in section['entities']}
        self._copy_addresses(section['tree'], addresses)
    return data
```

**4. Read it in a template.** The profile's `templates/_toc.html` defines `sidebar` and
`contents`, and draws `section.tree` where the base template draws `section.entities`.

**5. Check it.** Build the viewer on a small artefact and render the page, as
`tests/test_view_data.py` does for OWL and SKOS.

### The steps you can override

| Method | What it builds |
|--------|----------------|
| `view()` | The whole `ViewData`. Public: the web service and the static builder call it. |
| `_build_toc(language)` | The sections of the navigation. |
| `_build_entities(resource_uri, language)` | The cards of the main part. |
| `_format_entities(instances, language)` | One card for each instance. |
| `_toc_entry(instance, language)` | One entry of the navigation. |
| `_build_types()` | The `types` dictionary, from the `type_map` of `viewer.yaml`. |

The names that start with an underscore are internal: they can change between versions of
LODE, and only the profiles inside the repository are updated with them. A plugin that
overrides one should pin the version of LODE it was written for. `view()` and the
contract in `view_data.py` are the stable surface.
