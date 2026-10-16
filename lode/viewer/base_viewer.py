"""Generic viewer: turns model instances into the dictionaries the HTML templates render.

Format-specific viewers (OWL, RDF, SKOS) extend it with their table of contents
and display names. It also serializes the provenance of each entity.
"""
import hashlib
from typing import Dict, List, Optional, Tuple

from lode.models import Literal, Model, Resource, Statement

from rdflib import Graph, URIRef, BNode, Literal as RDFlibLiteral

from lode.reader.provenance_graph import ProvenanceGraph
from lode.helpers.rdf import iri_local_name

from lode.viewer.helpers import (
    QUAD_SERIALIZATION_FORMATS,
    SERIALIZATION_FORMATS,
    annotation_sort_key,
    clean_name,
    is_likely_ontology,
    load_viewer_config,
    safe_serialize,
)


class BaseViewer:
    """Base viewer to display the instances extracted by the Reader.

    It orchestrates the view: everything that differs between formats (display
    names, table of contents, hierarchy, card template, vocabulary) is read from
    the YAML file named by CONFIG_NAME. Subclasses set that name and override
    only the steps that really need code.
    """

    # Name of config/<name>_viewer.yaml; None gives the generic flat list view.
    CONFIG_NAME: Optional[str] = None

    def __init__(self, reader):
        """Bind the viewer to a Reader, share its instance cache and load its config."""
        self.reader = reader
        self._cache = reader._instance_cache  # it uses
        self._internal_iris = None
        self._ontology_ns = None
        self._config = (
            load_viewer_config(self.CONFIG_NAME) if self.CONFIG_NAME
            else {"type_map": {}, "toc": [], "card": "_card_owl.html",
                  "vocabulary": {}, "hierarchy": {}, "characteristics": []}
        )

    def get_toc_config(self) -> List[Tuple[str, str, str]]:
        """Return the table of contents: (class name, section id, type_map key) in display order."""
        return [tuple(entry) for entry in self._config["toc"]]

    def _clean_name(self, name: str) -> str:
        """Turn an attribute or getter name into a display label, using this viewer's vocabulary."""
        return clean_name(name, self._config["vocabulary"])

    def _get_ontology_ns(self) -> str:
        """Return the namespace of the documented ontology (its IRI ending in '/' or '#'), or ''.

        Computed once from the first Model instance and then cached.
        """
        if self._ontology_ns is None:
            self._ontology_ns = ''
            for inst in self.get_all_instances():
                if isinstance(inst, Model):
                    nid = inst.get_has_identifier()
                    if nid:
                        self._ontology_ns = nid if nid.endswith(('/', '#')) else nid + '/'
                    break
        return self._ontology_ns

    def _has_local_triples(self, uri) -> bool:
        """Return True if the graph has at least one triple whose subject is this IRI."""
        if not uri:
            return False
        return (URIRef(str(uri)), None, None) in self.reader._graph

    def _formats(self):
        """Return the export formats (triples): the same whatever modules are active."""
        return SERIALIZATION_FORMATS

    def _with_provenance(self, sub):
        """Return `sub` as quads, each triple in the named graph(s) it comes from.

        With modules active the graphs are the ones of the source ontologies;
        without, every triple goes in the graph of the loaded artefact.
        """
        ds = self.reader._graph
        out = ProvenanceGraph()
        for prefix, ns in ds.namespaces():
            out.bind(prefix, ns)
        if isinstance(ds, ProvenanceGraph):
            for s, p, o in sub:
                for *_, c in ds.quads((s, p, o, None)):
                    out.graph(c).add((s, p, o))
        else:
            main = out.graph(self.reader._ontology_iri)
            for t in sub:
                main.add(t)
        return out
    
    def _is_internal(self, uri) -> bool:
        """Return True if the IRI belongs to a browsable entity of this documentation.

        The set of IRIs is built once, on first use.
        """
        if not uri:
            return False
        if self._internal_iris is None:
            self._internal_iris = {
                str(i.get_has_identifier())
                for i in self.get_toc_instances()
                if i.get_has_identifier()
            }
        return str(uri) in self._internal_iris
    
    def get_all_instances(self) -> List:
        """Return all the instances in the cache, literals excluded."""
        instances = []
        
        for uri_id, instance_set in self._cache.items():
            if isinstance(uri_id, str) and uri_id.startswith("LITERAL::"):
                continue
            
            instance_list = instance_set if isinstance(instance_set, set) else [instance_set]
            instances.extend(instance_list)

        return instances

    def get_instances_from_single_resource(self, resource_uri: str) -> Optional[set]:
        """Return the cached instances registered under an IRI, or None when it is unknown."""
        # Look the IRI up in the cache
        for uri_id in self._cache.keys():
            if str(uri_id) == resource_uri:
                return self._cache[uri_id]
        
        return None

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

    def get_view_data(self, resource_uri: Optional[str] = None, language: Optional[str] = None) -> Dict:
        """Build the template data for one resource, or for the whole artefact grouped by entity type.

        Main entry point called by the API and by the static builder. Both views also
        carry the header metadata, the export formats, the display names of the types
        and the card template. Without a table of contents (generic viewer) the
        artefact is shown as a flat list.
        """
        # If no language is provided, the default would be English
        language = language.strip() if language else "en"

        all_instances = self.get_all_instances()
        metadata_dict = self._find_and_format_metadata(all_instances, language)

        if resource_uri:
            data = self._handle_single_resource(resource_uri, language)
        elif self._config["toc"]:
            data = self._build_grouped_view(self.get_toc_config(), language)
        else:
            data = {'entities': self._format_entities(all_instances, language)}

        data['metadata'] = metadata_dict
        data['export_formats'] = self._formats()
        data['type_map'] = self._config["type_map"]
        data['card_template'] = self._config["card"]
        return data

    def _is_toc_entity(self, instance) -> bool:
        """Browsable (own card + clickable link) iff its type is in get_toc_config. 
            Resources not listed in get_o_config are shown when mentioned as plain text 
            in cards  (external-ref), just never linked."""
        toc_keys = {key for key, _id, _title in self.get_toc_config()}
        if type(instance).__name__ not in toc_keys:
            return False
        return self._has_local_triples(instance.get_has_identifier())
    
    def get_toc_instances(self) -> List:
        """Return the instances that get their own card and link (the browsable entities)."""
        return [i for i in self.get_all_instances() if self._is_toc_entity(i)]
    
    def _handle_single_resource(self, resource_uri: str, language: Optional[str] = None) -> Dict:
        """
        Standard logic for displaying a single resource.
        Returns the specific dictionary structure required by viewer.html
        """
        instance_set = self.get_instances_from_single_resource(resource_uri)

        if not instance_set:
            return {'error': f'Resource {resource_uri} not found'}

        instances = list(instance_set) if isinstance(instance_set, set) else [instance_set]
        instances = [i for i in instances if self._is_toc_entity(i)]
        if not instances:
            return {'error': f'{resource_uri} is not a browsable entity'}

        return {
            'single_resource': True,
            'entities': self._format_entities(instances, language),
            'groupped_view': False,
            'sections': None
        }

    def _build_grouped_view(self, group_definitions: List[Tuple[str, str, str]], language: Optional[str] = None) -> Dict:
        """
        Constructs the 'Table of Contents' view.
        Adds optional 'tree' to sections whose class_key supports hierarchy.
        """
        all_instances = self.get_all_instances()
        sections = []

        for class_key, section_id, section_title in group_definitions:
            instances = [
                inst for inst in all_instances
                if type(inst).__name__ == class_key and self._is_toc_entity(inst)
            ]

            if instances:
                section = {
                    'id': section_id,
                    'title': section_title,
                    'entities': self._format_entities(instances, language),
                }

                parent_getter = self._config["hierarchy"].get(class_key)
                if parent_getter:
                    section['tree'] = self._build_hierarchy(instances, parent_getter, language)

                sections.append(section)

        return {
            'grouped_view': True,
            'sections': sections,
            'export_formats': self._formats()
        }

    def _format_entities(self, instances: List, language: Optional[str] = None) -> List[Dict]:
        """
        Converts Python Models -> HTML Template Dictionary.
        Ensures consistent keys ('type', 'uri', 'label') across all viewers.
        """
        all_instances = self.get_all_instances()

        entities = []
        for instance in instances:
            uri = instance.has_identifier if hasattr(instance, 'has_identifier') else None

            if not uri:
                continue

            #Create a safe HTML ID to facilitate on-page navigation
            safe_id = hashlib.md5(str(uri).encode('utf-8')).hexdigest()

            # Extract internal attributes (SuperClasses, etc.)
            relations = {}
            if hasattr(instance, '__dict__'):
                for attr, value in instance.__dict__.items():
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
                                    if fv.get('link'):
                                        fv['text'] = str(fv['link'])
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

            characteristics = {}
            for attr in self._config["characteristics"]:
                getter = f"get_{attr}"
                # Safely get the boolean value
                is_true = getattr(instance, getter)() if hasattr(instance, getter) else getattr(instance, attr, False)

                # Convert 'is_asymmetric' to 'is asymmetric' for the HTML label
                if is_true:
                    display_name = attr.replace('_', ' ')
                    characteristics[display_name] = True

            # Extract Statement Entities
            statements = self._format_statement(all_instances, instance, language)
            type_inst = type(instance).__name__.replace(" ", "_")

            is_dep = getattr(instance, 'get_is_deprecated')() if hasattr(instance, 'get_is_deprecated') else getattr(
                instance, 'is_deprecated', False)

            entities.append({
                'type': type_inst,
                'uri': uri,
                'label': self._get_best_label(instance, language),
                'anchor_id': f"id_{safe_id}_{type_inst}",
                'relations': ordered_relations,
                'statements': statements,
                'characteristics': characteristics,
                'is_deprecated': bool(is_dep),
                'provenance': self._build_provenance_subgraph(instance),
                'is_external': not self._is_internal(uri),
            })

        entities.sort(key=lambda x: (x['label'] or x['uri']).lower())
        return entities

    def _find_and_format_metadata(self, all_instances: List[Resource], language=None) -> Dict:
        """
        Searches for the Model and its Statements and formatting them
        for the template.
        """
        ontology_model = None

        # 1. Find the Model (skip imported/closure ontologies)
        imported = getattr(self.reader, "_imported_uris", set()) or set()
        models = [i for i in all_instances if isinstance(i, Model)]
        ontology_model = next(
            (m for m in models if str(m.get_has_identifier()) not in imported),
            models[0] if models else None,
        )

        if not ontology_model:
            return {}

        # 2. Prepare Output
        data = {
            'uri': [self._resolve_resource_value(ontology_model, language)],
            'label': [self._resolve_resource_value(self._get_best_label(ontology_model, language))]
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
        entry = {'text': None, 'link': None}
        # 1. Loop through ALL attributes and methods of the Model object
        for attr_name in dir(ontology_model):
            # 2. Look specifically for getter methods
            if attr_name.startswith('get_') and attr_name not in ignore_methods:

                method = getattr(ontology_model, attr_name)

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
                                # 7. Check if the link if an visualizable ontology or not
                                if entry.get('link'):
                                    entry['is_visualizable'] = is_likely_ontology(entry['link'])
                                else:
                                    entry['is_visualizable'] = False

                                extracted_values.append(entry)

                        # 8. Add to structural data ONLY if we found valid text
                        if extracted_values:
                            data[clean_key] = extracted_values

        # Namespaces (dict prefix -> URI), handled explicitly: not a Resource
        ns = ontology_model.get_has_namespaces()
        if ns:
            data['_namespaces'] = [
                {'prefix': prefix or 'default namespace', 'uri': uri}
                for prefix, uri in sorted(ns.items(), key=lambda kv: (kv[0] or ''))
            ]
            
        # 9. Statements
        data.update(self._format_statement(all_instances, ontology_model, language))

        # uri/label first, then the order from the YAML, then alphabetical
        pinned = ['uri', 'label']
        rest = sorted((k for k in data if k not in pinned), key=annotation_sort_key)
        data = {k: data[k] for k in pinned if k in data} | {k: data[k] for k in rest}

        return data
            
    def _resolve_chain_value(self, chain, language=None) -> dict:
        """Render an ordered property chain (a list of Relations) as a single value.

        The clickable parts are joined by the composition operator. Returns None
        when no member has a displayable text.
        """
        members = []
        for m in chain:
            md = self._resolve_resource_value(m, language)
            if md.get('text'):
                members.append(md)
        if not members:
            return None
        parts = []
        for i, md in enumerate(members):
            if i > 0:
                parts.append({'text': ' o ', 'link': None})  # ring operator
            parts.append(md)
        return {
            'text': ' o '.join(md['text'] for md in members),
            'link': None,
            'lan': None,
            'parts': parts,
            'type': 'PropertyChain',
        }

    def _resolve_special(self, obj, handler_dic: dict, language=None) -> Optional[dict]:
        """Resolve a value only one format knows how to render, or return None.

        The base knows none: a format viewer overrides this to intercept its own
        constructs (OWL class expressions) before the generic resolution runs.
        """
        return None

    def _resolve_resource_value(self, obj, language=None) -> dict:
        """Helper: Extracts text and link from any object."""
        handler_dic = {
            'text': None,
            'link': None,
            'lan': None,
            'parts': None,  # This key is for restrictions
            'type': None,
            'is_deprecated': False,
            'is_imported': False,
            'is_external': False,
        }

        if not obj: return handler_dic

        # --- 1. FORMAT-SPECIFIC VALUES (e.g. OWL restrictions) ---
        special = self._resolve_special(obj, handler_dic, language)
        if special is not None:
            return special

        obj_type = type(obj).__name__

        # --- 2. String Handling ---
        if isinstance(obj, str):
            handler_dic['text'] = obj
            return handler_dic

        # --- 3. Literal Handling ---
        if type(obj).__name__ == 'Literal':
            if hasattr(obj, 'get_has_value') and obj.get_has_value():

                is_dep = getattr(obj, 'get_is_deprecated')() if hasattr(obj, 'get_is_deprecated') else getattr(obj,
                                                                                                               'is_deprecated',
                                                                                                               False)
                handler_dic['is_deprecated'] = bool(is_dep)

                lit_lang = obj.get_has_language()

                handler_dic['text'] = obj.get_has_value()
                handler_dic['lan'] = lit_lang
                handler_dic['type'] = obj_type
                return handler_dic

            raw_str = str(obj)
            if "object at" not in raw_str:
                handler_dic['text'] = raw_str
                handler_dic['type'] = obj_type
                return handler_dic

        # --- 4. Statement (nested annotation) ---
        if obj_type == 'Statement':
            handler_dic['type'] = 'Statement'
            handler_dic['link'] = None  # don't link to the BNode id
            inner_pred = obj.get_has_predicate()
            inner_obj = obj.get_has_object()
            
            # Resolve the inner (predicate, value) pair recursively
            inner = {
                'predicate': self._get_best_label(inner_pred, language) if inner_pred else None,
                'value': self._resolve_resource_value(inner_obj, language) if inner_obj else None,
            }
            # Walk Statement's own annotations (anything else in __dict__ besides
            # the reification slots), so dc:date, rdf:value siblings show up too.
            skip = {'has_subject', 'has_predicate', 'has_object',
                    'has_identifier', 'is_positive_statement'}
            siblings = []
            for attr, value in obj.__dict__.items():
                if attr.startswith('_') or attr in skip or not value:
                    continue
                values = value if isinstance(value, list) else [value]
                for v in self._select_by_language(values, language):
                    resolved = self._resolve_resource_value(v, language)
                    if resolved.get('text') or resolved.get('nested'):
                        siblings.append({
                            'predicate': self._clean_name(attr),
                            'value': resolved,
                        })
            # Reader order depends on the source file: sort by label, then by value
            pairs = sorted(
                [inner] + siblings,
                key=lambda p: ((p['predicate'] or '').lower(),
                               ((p['value'] or {}).get('text') or '').lower()),
            )
            handler_dic['nested'] = {'main': pairs[0], 'siblings': pairs[1:]}
            # Pick a primary text for collapsed display: the inner value's text
            handler_dic['text'] = (inner.get('value') or {}).get('text') or '[Statement]'
            return handler_dic

        # --- 5. Normal Resource Handling (Concepts, Properties, Individuals) ---
        if hasattr(obj, 'get_has_identifier'):
            handler_dic['link'] = obj.get_has_identifier()
            link = handler_dic['link']
            ns = self._get_ontology_ns()
            internal = self._is_internal(link)
            native = bool(link) and bool(ns) and str(link).startswith(ns)
            handler_dic['is_external'] = not internal
            handler_dic['is_imported'] = internal and not native
            is_dep = getattr(obj, 'get_is_deprecated')() if hasattr(obj, 'get_is_deprecated') else getattr(obj, 'is_deprecated',  False)
            handler_dic['is_deprecated'] = bool(is_dep)

            try:
                handler_dic['text'] = self._get_best_label(obj, language)
                handler_dic['type'] = obj_type
            except AttributeError:
                handler_dic['text'] = handler_dic['link']
                handler_dic['type'] = obj_type

        # Fallbacks
        if not handler_dic['text'] and handler_dic['link']:
            handler_dic['text'] = handler_dic['link']
            handler_dic['type'] = obj_type

        return handler_dic

    def _format_statement(self, instances, target_instance, language=None) -> Dict:
        """
        Extracts all statements where the subject matches the given target_instance.
        """
        statements = {}

        # 1. Validate the target instance
        if target_instance is None:
            return statements

        # 2. Group the objects by predicate: the language is chosen per property
        grouped = {}
        for instance in instances:
            if not isinstance(instance, Statement):
                continue
            # Identity comparison (handles punning: same URI, different Python instances)
            if instance.get_has_subject() is not target_instance:
                continue
            obj = instance.get_has_object()
            if not obj:
                continue
            predicate = instance.get_has_predicate()
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
                statements[pred_label] = sorted(values, key=lambda v: (str(v.get('nested')), v['text'].lower()))

        return dict(sorted(statements.items(), key=lambda kv: kv[0].lower()))

    _FULL_IRI_ATTRS = {'is_defined_by'}
    
    def _build_hierarchy(self, instances, parent_getter_name, language=None):
        """
        Build a forest (list of trees) of dicts from the parent relation.
        anchor_id uses the same format as _format_entities: id_{md5}_{ClassName}
        """
        import hashlib

        by_uri = {}
        for inst in instances:
            uri = getattr(inst, 'has_identifier', None)
            if uri:
                by_uri[str(uri)] = inst

        children_map = {uri: [] for uri in by_uri}
        has_internal_parent = set()

        for uri, inst in by_uri.items():
            getter = getattr(inst, parent_getter_name, None)
            if not callable(getter):
                continue
            parents = getter() or []
            for p in parents:
                p_uri = getattr(p, 'has_identifier', None)
                if p_uri and str(p_uri) in by_uri and str(p_uri) != uri:
                    children_map[str(p_uri)].append(uri)
                    has_internal_parent.add(uri)

        roots = [uri for uri in by_uri if uri not in has_internal_parent]

        def node_dict(uri, visited):
            """Build the tree node of an entity with its children, stopping on cycles."""
            if uri in visited:
                return None
            visited = visited | {uri}
            inst = by_uri[uri]
            label = self._get_best_label(inst, language) or uri
            type_inst = type(inst).__name__.replace(" ", "_")
            safe_id = hashlib.md5(str(uri).encode('utf-8')).hexdigest()
            anchor_id = f"id_{safe_id}_{type_inst}"
            kids = []
            for child_uri in sorted(
                children_map.get(uri, []),
                key=lambda u: (self._get_best_label(by_uri[u], language) or u).lower()
            ):
                child_node = node_dict(child_uri, visited)
                if child_node:
                    kids.append(child_node)
            return {'label': label, 'anchor_id': anchor_id, 'uri': uri, 'children': kids}

        tree = []
        for uri in sorted(roots, key=lambda u: (self._get_best_label(by_uri[u], language) or u).lower()):
            node = node_dict(uri, set())
            if node:
                tree.append(node)
        return tree
    
    # ========== PROVENANCE: subgraph serialisation for each card ==========
    
    def _build_provenance_subgraph(self, instance) -> List[Dict[str, str]]:
        """Serialize the triples an instance comes from, once per available format.

        Returns an empty list when the instance has no provenance.
        """
        sub = self.reader.get_provenance_subgraph(instance)
        if not any(True for _ in sub):
            return []
        sub = self._with_provenance(sub)
        return [
            {"label": f["label"], "code": safe_serialize(sub, f["fmt"])}
            for f in QUAD_SERIALIZATION_FORMATS
        ]
    
    def export_resource(self, resource_uri: str, fmt: str = "turtle") -> str:
        """Serialize the subgraph of a single resource (the union of its punned instances).

        Only triples of the loaded artefact are exported; the ones that come from
        imported modules belong to the provenance, not to the export.
        """
        g = Graph()
        for prefix, ns in self.reader._graph.namespaces():
            g.bind(prefix, ns)
        main = self.reader.get_main_graph()
        instances = self.get_instances_from_single_resource(resource_uri)
        if instances:
            inst_iter = instances if isinstance(instances, set) else [instances]
            for inst in inst_iter:
                for t in self.reader.get_provenance_subgraph(inst):
                    if t in main:
                        g.add(t)
        return safe_serialize(g, fmt)