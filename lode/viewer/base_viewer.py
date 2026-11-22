"""Generic viewer: turns model entities into the dictionaries the HTML templates render.

Format-specific viewers (OWL, RDF, SKOS) extend it with their table of contents
and display names. It also serializes the provenance of each entity.
"""
import hashlib
import re
from typing import Dict, List, Optional, Tuple 
from pathlib import Path
from rdflib import Graph, URIRef

from lode.models import Literal, Model, Resource, Statement
from lode.helpers.formats import QUAD_SERIALIZATION_FORMATS, SERIALIZATION_FORMATS
from lode.helpers.rdf import iri_local_name
from lode.viewer.contract import resolve_links, to_model
from lode.helpers.links import Links
from lode.viewer.view_data import Card, TocEntry, TocSection, TypeLabel, Value, ViewData, new_value

import lode.models as _models

from lode.viewer.helpers import (
    annotation_sort_key,
    clean_name,
    load_viewer_config,
    safe_serialize,
)

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

class BaseViewer:
    """Base viewer to display the entities extracted by the Reader.

    It orchestrates the view: everything that differs between formats (display
    names, table of contents, card template, vocabulary) is read from
    the viewer.yaml of the artefact's profile. Subclasses override only the
    steps that really need code.
    """

    # ==========================================================================
    # SETUP
    # ==========================================================================

    def __init__(self, artefact):
        """Bind the viewer to an artefact and load the viewer config of its profile.

        An artefact without a profile gets the generic flat list view.
        """
        self.artefact = artefact
        self._internal_iris = None
        self._config = (
            load_viewer_config(artefact.profile) if artefact.profile
            else {"type_map": {}, "toc": [],
                  "vocabulary": {}, "characteristics": []}
        )

    def get_toc_config(self) -> List[Tuple[str, str, str]]:
        """Return the table of contents: (class name, section id, type_map key) in display order."""
        return [tuple(entry) for entry in self._config["toc"]]

    def template_dirs(self) -> List[Path]:
        """Return the folders the page templates are searched in; the first match wins.

        A format keeps the templates that differ from the base ones in the templates/ folder of its profile:
        a file with the same name there replaces the base file, and every file it does not
        provide comes from the base. The adapters build their Jinja loader from this list, so
        the viewer itself knows nothing about Jinja.
        """
        profile = self.artefact.profile
        own = profile.path() / "templates" if profile else None
        return [own, _TEMPLATES_DIR] if own and own.is_dir() else [_TEMPLATES_DIR]


    # ==========================================================================
    # 2. ARTEFACT ACCESS
    # ==========================================================================

    def get_artefact_ns(self) -> str:
        """Return the namespace of the documented semantic artefact (its IRI ending in '/' or '#'), or ''.

        Read from the artefact: the Reader derives it from the artefact IRI.
        """
        return str(self.artefact.artefact_base_iri or '')

    def _has_local_triples(self, uri) -> bool:
        """Return True if the graph has at least one triple whose subject is this IRI."""
        if not uri:
            return False
        return (URIRef(str(uri)), None, None) in self.artefact.graph

    # ==========================================================================
    # 3. NAVIGATION RULES
    # ==========================================================================

    def _is_internal(self, uri) -> bool:
        """Return True if the IRI belongs to a browsable entity of this documentation.

        The set of IRIs is built once, on first use.
        """
        if not uri:
            return False
        if self._internal_iris is None:
            self._internal_iris = {
                str(i.get_has_identifier())
                for i in self.get_toc_entities()
                if i.get_has_identifier()
            }
        return str(uri) in self._internal_iris

    def _is_toc_entity(self, entity) -> bool:
        """Browsable (own card + clickable link) iff its type is in get_toc_config. 
            Resources not listed in get_o_config are shown when mentioned as plain text 
            in cards  (external-ref), just never linked."""
        toc_keys = {key for key, _id, _title in self.get_toc_config()}
        if type(entity).__name__ not in toc_keys:
            return False
        return self._has_local_triples(entity.get_has_identifier())

    def get_toc_entities(self) -> List:
        """Return the entities that get their own card and link (the browsable entities)."""
        return [i for i in self.artefact.get_entities() if self._is_toc_entity(i)]

    # ==========================================================================
    # 3. LABELS AND LANGUAGES
    # ==========================================================================

    def _clean_name(self, name: str) -> str:
        """Turn an attribute or getter name into a display label, using this viewer's vocabulary."""
        return clean_name(name, self._config["vocabulary"])

    def _select_by_language(self, values: List, language: Optional[str] = None) -> List:
        """Keep the values of one property in the best available language.

        The choice is made per property, not per literal: only with all the
        siblings in view can a fallback exist. Tags follow BCP 47, so they are
        compared case-insensitively. Order of preference (RFC 4647 lookup): the
        exact tag, the tag truncated from the right (en-GB, then en), 'en',
        untagged literals, then every literal sorted by tag (nothing disappears).
        Non-literal values always pass, and the input order is kept.
        """
        lits = [v for v in values if isinstance(v, Literal)]
        parts = (language or "en").strip().lower().split("-")
        # shortcut: no skipping of singleton subtags (zh-x-private), upgrade if such tags matter
        chain = ["-".join(parts[:i]) for i in range(len(parts), 0, -1)] + ["en"]

        def tagged(wanted: str) -> List:
            """Literals whose tag is exactly `wanted`, ignoring case."""
            return [l for l in lits if (l.get_has_language() or "").lower() == wanted]

        chosen = (next((m for m in map(tagged, chain) if m), None)
                  or [l for l in lits if not l.get_has_language()]
                  or sorted(lits, key=lambda l: str(l.get_has_language() or "")))
        keep = {id(l) for l in chosen}
        return [v for v in values if not isinstance(v, Literal) or id(v) in keep]

    def _get_best_label(self, resource, language: Optional[str] = None) -> Optional[str]:
        """Gets the best label to display: language > preferred_label > label > identifier."""

        # Preferred labels come first, so they win within the same language
        labels = list(resource.get_has_preferred_label()) + list(resource.get_has_label())
        selected = self._select_by_language(labels, language)
        if selected:
            return selected[0].get_has_value()

        # Final Fallback: The URI Identifier
        resource_id = resource.get_has_identifier()
        if resource_id:
            clean_resource_id = iri_local_name(resource_id)
            # ONLY clean the identifier!
            return self._clean_name(clean_resource_id)

        return None

    # ==========================================================================
    # 3. VIEW DATA
    # ==========================================================================    

    def view(self, resource_uri: Optional[str] = None, language: Optional[str] = None,
             links: Optional[Links] = None) -> ViewData:
        """Return the data of a page as the contract between viewers and templates defines it.

        `resource_uri` asks for the page of one resource; without it, the whole artefact. The
        contract is described in lode.viewer.view_data. The page of one resource has no
        navigation (`toc` is empty): it shows its card and nothing else, so a site of N
        resources does not carry N copies of its own index. Main entry point of the viewer:
        the web service and the static builder both call it, each with its own `links`.
        """
        language = language.strip() if language else "en"   # no language means English
        links = links or Links()
        cards, error = self._build_cards(resource_uri, language)
        header = self._find_and_format_semantic_artefact_metadata(self.artefact.get_entities(), language)
        data = {
            'model': to_model(header, self._formats(), self.format_warnings(self.artefact.warnings)),
            'toc': [] if resource_uri else self._build_toc(language),
            'types': self._build_types(),
            'cards': cards,
            'focus': resource_uri or None,
            'error': error,
        }

        # "Visualise it with LODE" is offered for the imported ontologies only: an import
        # is an ontology by definition, any other IRI (creator, licence...) is not
        for value in data['model']['metadata'].get(self._clean_name('get_imports'), []):
            if value['iri']:
                value['visualize'] = links.visualize(value['iri'])

        resolve_links(data, links)
        return data

    def _build_cards(self, resource_uri: Optional[str], language: str) -> Tuple[List[Card], Optional[str]]:
        """Return the cards of a page and the error, if there is one.

        One resource gives its own cards (an IRI can name several entities: a class and an
        individual, punned); the whole artefact gives every browsable entity, grouped by
        section in the order of the table of contents. Without a table of contents (the generic
        viewer) the artefact is shown as a flat list.
        """
        if resource_uri:
            found = self.artefact.get_entities_by_iri(resource_uri)
            if not found:
                return [], f'Resource {resource_uri} not found'
            candidates = list(found) if isinstance(found, set) else [found]
            candidates = [i for i in candidates if self._is_toc_entity(i)]
            if not candidates:
                return [], f'{resource_uri} is not a browsable entity'
            return self._format_cards(candidates, language), None

        all_entities = self.artefact.get_entities()
        if not self._config["toc"]:
            return self._format_cards(all_entities, language), None
        cards = []
        for class_key, _section_id, _title in self.get_toc_config():
            members = [i for i in all_entities
                       if type(i).__name__ == class_key and self._is_toc_entity(i)]
            cards += self._format_cards(members, language)
        return cards, None


    def _build_types(self) -> Dict[str, TypeLabel]:
        """How each type is called and abbreviated, keyed by the name of its model class.

        The configuration keys the names by the lower-case class name; the contract uses the exact
        name, the one a Value, an Card and a section carry in `type`.
        """
        exact = {name.lower(): name for name in _models.__all__}
        return {exact.get(key, key.capitalize()): {'singular': entry['singular'],
                                                   'plural': entry['plural'],
                                                   'abbreviation': entry['abb']}
                for key, entry in self._config["type_map"].items()}


    def _build_toc(self, language: str) -> List[TocSection]:
        """Build the navigation: every browsable entity as a short entry, grouped by section.

        It does not depend on the view, so the page of one resource has the same navigation as
        the whole artefact.
        """
        entities = self.artefact.get_entities()
        toc = []
        for class_key, section_id, _ in self.get_toc_config():
            members = [i for i in entities
                       if type(i).__name__ == class_key and self._is_toc_entity(i)]
            if not members:
                continue
            entries = sorted((self._toc_entry(i, language) for i in members),
                             key=lambda e: (e['label'] or e['iri']).lower())
            names = self._config["type_map"].get(class_key.lower(), {})
            toc.append({'id': section_id, 'type': class_key, 'label': names.get('plural', class_key),
                        'entries': entries})
        return toc

    def _anchor(self, entity) -> str:
        """Return the HTML id of the card of an entity.

        Derived from its IRI, so it is stable and safe in an attribute. The navigation 
        and the card both use it: a link from the navigation reaches the card.
        """
        type_name = type(entity).__name__.replace(" ", "_")
        digest = hashlib.md5(str(entity.has_identifier).encode('utf-8')).hexdigest()
        return f"id_{digest}_{type_name}"


    def _toc_entry(self, entity, language: str) -> TocEntry:
        """Reduce an entity to what a navigation needs: IRI, type, label and anchor.

        The anchor has the same form as the one of its card, so a link from the navigation
        reaches the card.
        """
        return {'iri': entity.has_identifier, 'type': type(entity).__name__.replace(" ", "_"),
                'label': self._get_best_label(entity, language),
                'anchor': self._anchor(entity), 'href': None, 'kind': "page"}

    def _format_cards(self, members: List, language: Optional[str] = None) -> List[Card]:
        """
        onverts Python Models -> contract Entities (the content of a card).
        Ensures the same keys across all viewers.
        """
        all_entities = self.artefact.get_entities()

        cards = []
        for entity in members:
            uri = entity.has_identifier if hasattr(entity, 'has_identifier') else None

            if not uri:
                continue

            # Extract internal attributes (SuperClasses, etc.)
            relations = {}
            if hasattr(entity, '__dict__'):
                for attr, value in entity.__dict__.items():
                    if not attr.startswith('_') and value:
                        # Skip attributes that are handled elsewhere or are empty
                        # Clean up name:
                        clean_name = self._clean_name(attr)

                        # Process value (could be a list of objects)clean
                        # We use the helper to get clean text for each item
                        formatted_values = []
                        if isinstance(value, list):
                            for v in self._select_by_language(value, language):
                                # Nested list (e.g. has_property_chain: list of chains)
                                if isinstance(v, list):
                                    chain_dict = self._resolve_chain_value(v, language)
                                    if chain_dict and chain_dict['text']:
                                        formatted_values.append(chain_dict)
                                    continue
                                # Normal list
                                val_dict = self._resolve_resource_value(v, language)
                                if val_dict['text']: formatted_values.append(val_dict)
                        else:
                            val_dict = self._resolve_resource_value(value, language)
                            if val_dict['text']: formatted_values.append(val_dict)

                        if formatted_values:
                            if attr in self._FULL_IRI_ATTRS:
                                for fv in formatted_values:
                                    if fv['iri']:
                                        fv['text'] = str(fv['iri'])
                            if clean_name not in relations:
                                relations[clean_name] = []
                            for v in formatted_values:
                                if v not in relations[clean_name]:  # Valentina FIX: this do not add duplicates in metadata values  
                                    relations[clean_name].append(v)
            # Sort relations
            ordered_relations = {}

            # Define the exact order you
            priority_order = [
                "is sub property of",
                "domain",
                "range",
                "is inverse Of",
                "property chain",
                "is disjoint with"
            ]

            # Extract and insert the priority keys first
            for key in priority_order:
                if key in relations:
                    ordered_relations[key] = relations[key]

            # Insert all remaining keys alphabetically
            for key in sorted(relations.keys()):
                if key not in ordered_relations:
                    ordered_relations[key] = relations[key]

            characteristics = []
            for attr in self._config["characteristics"]:
                getter = f"get_{attr}"
                # Safely get the boolean value
                is_true = getattr(entity, getter)() if hasattr(entity, getter) else getattr(entity, attr, False)

                # Convert 'is_asymmetric' to 'is asymmetric' for the HTML label
                if is_true:
                    characteristics.append(attr.replace('_', ' '))

            # Extract Statement Entities
            statements = self._format_statement(all_entities, entity, language)
            type_inst = type(entity).__name__.replace(" ", "_")

            is_dep = getattr(entity, 'get_is_deprecated')() if hasattr(entity, 'get_is_deprecated') else getattr(
                entity, 'is_deprecated', False)

            cards.append({
                'iri': uri,
                'type': type_inst,
                'label': self._get_best_label(entity, language),
                'anchor': self._anchor(entity),
                'href': None,
                'kind': "page" if self._is_internal(uri) else "external",
                'deprecated': bool(is_dep),
                'relations': ordered_relations,
                'statements': statements,
                'characteristics': characteristics,
                'provenance': self._serialize_provenance(entity),
            })

        cards.sort(key=lambda x: (x['label'] or x['iri']).lower())
        return cards

    def _find_and_format_semantic_artefact_metadata(self, all_entities: List[Resource], language=None) -> Dict:
        """
        Searches for the Model and its Statements and formatting them
        for the template.
        """
        
        # 1. Find the Model of the documented semantic artefact (not the imported ones):
        # the cache also holds Models for imports and version IRIs, so pick it by IRI.
        # A source that declares no ontology or concept scheme has none: no header.
        main_iri = str(self.artefact.artefact_iri)
        sem_art_model = next(
            (m for m in self.artefact.get_entities(Model)
             if str(m.get_has_identifier()) == main_iri),
            None,
        )

        if not sem_art_model:

            return {}

        # 2. Prepare Output
        data = {
            'uri': [self._resolve_resource_value(sem_art_model, language)],
            'label': [self._resolve_resource_value(self._get_best_label(sem_art_model, language))]
        }

        #  3: Dynamic Extraction of Structural Data ---
        # Methods we want to skip because they belong in the Header or Annotations
        ignore_methods = [
            'get_has_identifier',
            'get_has_label',
            'get_has_subject',
            'get_has_predicate',
            'get_has_object',
            'get_has_namespaces',
        ]

        # 1. Loop through ALL attributes and methods of the Model object
        for attr_name in dir(sem_art_model):
            # 2. Look specifically for getter methods
            if attr_name.startswith('get_') and attr_name not in ignore_methods:

                method = getattr(sem_art_model, attr_name)

                if callable(method):
                    try:
                        values = method()
                    except AttributeError:
                        # skip attributes that are not initialized
                        continue

                    if values:
                        # 4. Auto-format the key name
                        clean_key = self._clean_name(attr_name)

                        # 5. Ensure values are in a list
                        if not isinstance(values, list):
                            values = [values]

                        # 6. Extract the actual text values
                        extracted_values = []
                        for val in self._select_by_language(values, language):
                            entry = self._resolve_resource_value(val, language)
                            if entry['text']:
                                extracted_values.append(entry)

                        # 8. Add to structural data ONLY if we found valid text
                        if extracted_values:
                            data[clean_key] = extracted_values

        # Namespaces (dict prefix -> URI), handled explicitly: not a Resource
        ns = sem_art_model.get_has_namespaces()
        if ns:
            data['_namespaces'] = [
                {'prefix': prefix or 'default namespace', 'uri': uri}
                for prefix, uri in sorted(ns.items(), key=lambda kv: (kv[0] or ''))
            ]
            
        # 9. Statements
        data.update(self._format_statement(all_entities, sem_art_model, language))

        # The header shows every link as its full IRI, not as a label or the last part of it:
        # the reader needs to see where it points. Applied here, once, because the values come
        # from two places (getters above, statements) and cards keep their labels.
        for key, values in data.items():
            if key in ('uri', 'label', '_namespaces'):
                continue
            for value in values:
                if value['iri']:
                    value['text'] = str(value['iri'])

        # uri/label first, then the order from the YAML, then alphabetical
        pinned = ['uri', 'label']
        rest = sorted((k for k in data if k not in pinned), key=annotation_sort_key)
        data = {k: data[k] for k in pinned if k in data} | {k: data[k] for k in rest}

        return data

    # ==========================================================================
    # 3. VALUE RESOLUTION
    # ==========================================================================    

    def _resolve_special(self, obj, value: Value, language=None) -> Optional[Value]:
        """Resolve a value only one format knows how to render, or return None.

        The base knows none: a format viewer overrides this to intercept its own
        constructs (OWL class expressions) before the generic resolution runs. It
        fills in `value`, an empty Value, and returns it.
        """
        return None
    
    def _resolve_chain_value(self, chain, language=None) -> Optional[Value]:
        """Render an ordered property chain (a list of Relations) as a single Value.

        The clickable parts are joined by the composition operator. Returns None
        when no member has a displayable text.
        """
        members = [m for m in (self._resolve_resource_value(r, language) for r in chain) if m['text']]
        if not members:
            return None
        parts = []
        for i, member in enumerate(members):
            if i > 0:
                parts.append(new_value(text=' o '))  # ring operator
            parts.append(member)
        return new_value(text=' o '.join(m['text'] for m in members), parts=parts, type='PropertyChain')

    def _resolve_resource_value(self, obj, language=None) -> Value:
        """Turn any object (resource, literal, statement, string) into a contract Value.

        The Value carries its IRI and a `kind` ("page" inside this documentation, "external"
        outside); the address (`href`) is filled in later, by the Links of the caller.
        """
        value = new_value()

        if not obj:
            return value

        # --- 1. FORMAT-SPECIFIC VALUES (e.g. OWL restrictions) ---
        special = self._resolve_special(obj, value, language)
        if special is not None:
            return special

        obj_type = type(obj).__name__

        # --- 2. String Handling ---
        if isinstance(obj, str):
            value['text'] = obj
            return value

        # --- 3. Literal Handling ---
        if obj_type == 'Literal':
            if hasattr(obj, 'get_has_value') and obj.get_has_value():
                is_dep = getattr(obj, 'get_is_deprecated')() if hasattr(obj, 'get_is_deprecated') else getattr(
                    obj, 'is_deprecated', False)
                value['deprecated'] = bool(is_dep)
                value['text'] = obj.get_has_value()
                value['language'] = obj.get_has_language()
                value['type'] = obj_type
                return value

            raw_str = str(obj)
            if "object at" not in raw_str:
                value['text'] = raw_str
                value['type'] = obj_type
                return value

        # --- 4. Statement (nested annotation) ---
        if obj_type == 'Statement':
            value['type'] = 'Statement'   # no IRI: never link to the id of the blank node
            inner_pred = obj.get_has_predicate()
            inner = {
                'predicate': self._get_best_label(inner_pred, language) if inner_pred else None,
                'value': self._resolve_resource_value(obj.get_has_object(), language),
            }
            # Walk Statement's own annotations (anything else in __dict__ besides
            # the reification slots), so dc:date, rdf:value siblings show up too.
            skip = {'has_subject', 'has_predicate', 'has_object',
                    'has_identifier', 'is_positive_statement'}
            siblings = []
            for attr, attr_value in obj.__dict__.items():
                if attr.startswith('_') or attr in skip or not attr_value:
                    continue
                values = attr_value if isinstance(attr_value, list) else [attr_value]
                for v in self._select_by_language(values, language):
                    resolved = self._resolve_resource_value(v, language)
                    if resolved['text'] or resolved['nested']:
                        siblings.append({'predicate': self._clean_name(attr), 'value': resolved})
            # Reader order depends on the source file: sort by label, then by value
            pairs = sorted([inner] + siblings,
                           key=lambda p: ((p['predicate'] or '').lower(), (p['value']['text'] or '').lower()))
            value['nested'] = {'main': pairs[0], 'siblings': pairs[1:]}
            # The text for a collapsed display: the one of the inner value
            value['text'] = inner['value']['text'] or '[Statement]'
            return value

        # --- 5. Normal Resource Handling (e.g., Concepts, Properties, Individuals) ---
        if hasattr(obj, 'get_has_identifier'):
            iri = obj.get_has_identifier()
            value['iri'] = iri
            ns = self.get_artefact_ns()
            internal = self._is_internal(iri)
            native = bool(iri) and bool(ns) and str(iri).startswith(ns)
            if iri:
                value['kind'] = "page" if internal else "external"
            value['imported'] = internal and not native
            is_dep = getattr(obj, 'get_is_deprecated')() if hasattr(obj, 'get_is_deprecated') else getattr(
                obj, 'is_deprecated', False)
            value['deprecated'] = bool(is_dep)
            value['type'] = obj_type
            try:
                value['text'] = self._get_best_label(obj, language)
            except AttributeError:
                value['text'] = iri

        # Fallbacks
        if not value['text'] and value['iri']:
            value['text'] = value['iri']
            value['type'] = obj_type

        return value

    def format_warnings(self, warnings: List[Dict]) -> List[Dict]:
        """Return the reader warnings with model class names replaced by this viewer's display names.

        The reader words its messages with internal class names (Attribute, Annotation) and
        cannot know how a format shows them; the display names live in the type_map of this
        viewer, so the swap happens here, before the warnings reach any output. Only standalone
        words are replaced: a class name inside an IRI (.../Concept, ...#Concept) is left alone.
        Returns copies, the reader's own list is never modified.
        """
        names = {key.capitalize(): entry["singular"] for key, entry in self._config["type_map"].items()}
        if not names:
            return [dict(w) for w in warnings]
        pattern = re.compile(r"(?<![\w/#:-])(" + "|".join(map(re.escape, names)) + r")(?![\w/#:-])")
        return [{**w, "message": pattern.sub(lambda m: names[m.group(1)], w["message"])}
                for w in warnings]

    # ==========================================================================
    # RDF RELATED FEATURES = Provenance + Export RDF
    # ==========================================================================
            
    def _formats(self):
        """Return the export formats (triples): the same whatever modules are active."""
        return SERIALIZATION_FORMATS

    def _format_statement(self, entities, target_entity, language=None) -> Dict:
        """
        Extracts all statements where the subject matches the given target_entity.
        """
        statements = {}

        # 1. Validate the target entity
        if target_entity is None:
            return statements

        # 2. Group the objects by predicate: the language is chosen per property
        grouped = {}
        for entity in entities:
            if not isinstance(entity, Statement):
                continue
            # Identity comparison (handles punning: same URI, different Python entities)
            if entity.get_has_subject() is not target_entity:
                continue
            obj = entity.get_has_object()
            if not obj:
                continue
            predicate = entity.get_has_predicate()
            pred_label = self._get_best_label(predicate, language) if predicate else "Annotation"
            grouped.setdefault(pred_label, []).append(obj)

        # 3. Pick the language per property, resolve, drop empties and duplicates
        for pred_label, objs in grouped.items():
            values = []
            for obj in self._select_by_language(objs, language):
                obj_data = self._resolve_resource_value(obj, language)
                if obj_data['text'] and obj_data not in values:
                    values.append(obj_data)
            if values:
                statements[pred_label] = sorted(values, key=lambda v: (str(v['nested']), v['text'].lower()))

        return dict(sorted(statements.items(), key=lambda kv: kv[0].lower()))

    _FULL_IRI_ATTRS = {'is_defined_by'}
    
    # ==========================================================================
    # RDF RELATED FEATURES = Provenance + Export RDF
    # ==========================================================================
    
    def _serialize_provenance(self, entity) -> List[Dict[str, str]]:
        """Serialize the triples an entity comes from, once per available format.

        Returns an empty list when the entity has no provenance.
        """
        sub = self.artefact.provenance(entity)
        if not any(True for _ in sub):
            return []
        sub = self.artefact.with_provenance(sub)
        return [
            {"label": f["label"], "code": safe_serialize(sub, f["fmt"])}
            for f in QUAD_SERIALIZATION_FORMATS
        ]
    
    def _resource_graph(self, resource_uri: str) -> Graph:
        """Build the subgraph of a single resource (the union of its punned entities).

        Only triples of the loaded artefact are kept; the ones that come from imported
        modules belong to the provenance, not to the export. The graph starts without
        the default rdflib prefixes: the artefact graph already carries them, and
        binding them twice is the most expensive part of an export.
        """
        g = Graph(bind_namespaces="none")
        for prefix, ns in self.artefact.graph.namespaces():
            g.bind(prefix, ns)
        main = self.artefact.main_graph()
        entities = self.artefact.get_entities_by_iri(resource_uri)
        if entities:
            inst_iter = entities if isinstance(entities, set) else [entities]
            for inst in inst_iter:
                for t in self.artefact.provenance(inst):
                    if t in main:
                        g.add(t)
        return g

    def export_resource(self, resource_uri: str, fmt: str = "turtle") -> str:
        """Serialize the subgraph of a single resource in one format."""
        return safe_serialize(self._resource_graph(resource_uri), fmt)

    def export_resource_all(self, resource_uri: str, formats: List[str]) -> Dict[str, str]:
        """Serialize the subgraph of a single resource in several formats.

        The subgraph is built once and reused: a static build asks for every format of
        every resource, and building it per format multiplied the cost by the number
        of formats.
        """
        g = self._resource_graph(resource_uri)
        return {fmt: safe_serialize(g, fmt) for fmt in formats}

    def export_main(self, fmt: str = "turtle") -> str:
        """Serialize the main graph, i.e. the triples of the loaded artefact only.

        Imported modules are left out: they belong to the provenance, not to the
        export. A format that fails yields an error comment instead of raising, so
        one bad format cannot break the whole export or build.
        """
        return safe_serialize(self.artefact.main_graph(), fmt)