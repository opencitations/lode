# base_viewer.py
import hashlib
import re
from typing import Dict, List, Optional, Tuple
from lode.models import Literal, Model, Resource, Statement

class BaseViewer:
    """Base viewer per visualizzare istanze estratte dal Reader."""
    
    def __init__(self, reader):
        self.reader = reader
        self._cache = reader._instance_cache  # it uses 
    
    def get_all_instances(self) -> List:
        """Ottiene tutte le istanze (esclusi literal)."""
        instances = []
        
        for uri_id, instance_set in self._cache.items():
            if isinstance(uri_id, str) and uri_id.startswith("LITERAL::"):
                continue
            
            instance_list = instance_set if isinstance(instance_set, set) else [instance_set]
            instances.extend(instance_list)

        return instances
    
    def get_instances_from_single_resource(self, resource_uri: str) -> Optional[set]:
        """Ottiene istanze per un URI specifico dalla cache."""
        # Cerca l'URI nella cache
        for uri_id in self._cache.keys():
            if str(uri_id) == resource_uri:
                return self._cache[uri_id]
        
        return None

    def _get_best_label(self, resource: Resource, language: Optional[str] = None) -> Optional[str]:
        """Gets the best label to display: language > preferred_label > label > identifier."""

        # 1. Force 'en' as the absolute default if no language makes it this far
        target_lang = language.strip().lower() if language else "en"

        # Check Preferred Labels for the target language
        labels = resource.get_has_preferred_label()
        for label in labels:
            if hasattr(label, 'get_has_language') and label.get_has_language():
                if label.get_has_language().lower().startswith(target_lang):
                    return self._clean_name(label.get_has_value())

        # Check Normal Labels for the target language
        labels = resource.get_has_label()
        for label in labels:
            if hasattr(label, 'get_has_language') and label.get_has_language():
                if label.get_has_language().lower().startswith(target_lang):
                    return self._clean_name(label.get_has_value())

        # --- DETERMINISTIC FALLBACKS ---
        # If we reach here, no English label exists.
        # We sort them by language tag so it doesn't randomly shuffle!

        labels = resource.get_has_preferred_label()
        if labels:
            # Sort alphabetically by language tag (e.g., 'es' then 'pt')
            sorted_labels = sorted(labels, key=lambda x: str(x.get_has_language() or ""))
            return self._clean_name(sorted_labels[0].get_has_value())

        labels = resource.get_has_label()
        if labels:
            sorted_labels = sorted(labels, key=lambda x: str(x.get_has_language() or ""))
            return self._clean_name(sorted_labels[0].get_has_value())

        # Final Fallback: The URI Identifier
        resource_id = resource.get_has_identifier()
        if resource_id:
            clean_resource_id = resource_id.split('#')[-1] if '#' in resource_id else resource_id.split('/')[-1]
            return self._clean_name(clean_resource_id)

        return None

    def get_view_data(self, resource_uri: Optional[str] = None, language: Optional[str] = None) -> Dict:
        """
        Main entry point called by the API
        Subclasses should override this to define their specific view strategy
        """
        # If no language is provided, the default would be English
        language = language.strip() if language else "en"

        # Fallback: generic flat list
        all_instances = self.get_all_instances()
        metadata_dict = self._find_and_format_metadata(all_instances, language)

        if resource_uri:
            data = self._handle_single_resource(resource_uri, language)
            data['metadata'] = metadata_dict
            return data

        return {
            'metadata': metadata_dict,
            'entities': self._format_entities(all_instances, language)
        }

    def _handle_single_resource(self, resource_uri: str, language: Optional[str] = None) -> Dict:
        """
        Standard logic for displaying a single resource.
        Returns the specific dictionary structure required by viewer.html
        """
        instance_set = self.get_instances_from_single_resource(resource_uri)

        if not instance_set:
            return {'error': f'Resource {resource_uri} not found'}

        instances = list(instance_set) if isinstance(instance_set, set) else [instance_set]

        return {
            'single_resource': True,
            'entities': self._format_entities(instances, language),
            'groupped_view': False,
            'sections': None
        }

    def _build_grouped_view(self, group_definitions: List[Tuple[str, str, str]], language: Optional[str] = None) -> Dict:
        """
        Constructs the 'Table of Contents' view.

        Args:
            group_definitions: List of tuples (ClassKey, HTML_ID, Title)
                            e.g. [('Concept', 'classes', 'Classes')]
            language: Optional language code for label filtering
        """
        all_instances = self.get_all_instances()
        sections = []

        for class_key, section_id, section_title in group_definitions:
            instances = [
                inst for inst in all_instances 
                if type(inst).__name__ == class_key
            ]

            if instances:
                sections.append({
                    'id': section_id,
                    'title': section_title,
                    'entities': self._format_entities(instances, language)
                })

        return {
            'grouped_view': True,
            'sections': sections
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
                            for v in value:
                                val_dict = self._resolve_resource_value(v, language)
                                if val_dict['text']: formatted_values.append(val_dict)
                        else:
                            val_dict = self._resolve_resource_value(value, language)
                            if val_dict['text']: formatted_values.append(val_dict)

                        if formatted_values:
                            if clean_name not in relations:
                                relations[clean_name] = []
                            for v in formatted_values:
                                if v not in relations[clean_name]:  # Valentina FIX: this do not add duplicates in metadata values  
                                    relations[clean_name].append(v)

            # Extract Statement Entities
            statements =  self._format_statement(all_instances, uri, language)
            type_inst = type(instance).__name__.replace(" ", "_")

            entities.append({
                'type': type_inst,
                'uri': uri,
                'label': self._get_best_label(instance, language),
                'anchor_id': f"id_{safe_id}_{type_inst}",
                'relations': relations,
                'statements': statements
            })

        entities.sort(key=lambda x: (x['label'] or x['uri']).lower())
        return entities

    def _find_and_format_metadata(self, all_instances: List[Resource], language=None) -> Dict:
        """
        Searches for the Model and its Statements and formatting them
        for the template.
        """
        ontology_model = None

        # 1. Find the Model
        for instance in all_instances:
            if isinstance(instance, Model):
                ontology_model = instance
                break

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
            'get_has_object'
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
                        for val in values:
                            entry = self._resolve_resource_value(val, language)
                            if entry['text']:
                                extracted_values.append(entry)

                        # 7. Add to structural data ONLY if we found valid text
                        if extracted_values:
                            data[clean_key] = extracted_values

        # 4. Statements
        data.update(self._format_statement(all_instances, ontology_model.has_identifier, language))

        return data

    def _resolve_resource_value(self, obj, language=None) -> dict:
        """Helper: Extracts text and link from any object."""
        handler_dic = {
            'text': None,
            'link': None,
            'lan': None,
            'parts': None,  # This key is for restrictions
            'type': None
        }

        if not obj: return handler_dic

        # --- 1. INTERCEPT RESTRICTIONS ---
        restriction_types = ["Restriction", "PropertyConceptRestriction", "Quantifier", "Cardinality", "TruthFunction",
                             "OneOf", "Value"]
        obj_type = type(obj).__name__

        if obj_type in restriction_types:
            # Recursively parse the restriction into clickable parts
            parts = self._parse_restriction(obj, language)

            handler_dic['parts'] = parts
            handler_dic['text'] = "".join([p['text'] for p in parts if p.get('text')])
            handler_dic['link'] = None  # Forces Jinja to ignore the blank node URI
            handler_dic['type'] = obj_type
            return handler_dic

        # --- 2. String Handling ---
        if isinstance(obj, str):
            handler_dic['text'] = obj
            return handler_dic

        # --- 3. Literal Handling ---
        if type(obj).__name__ == 'Literal':
            if hasattr(obj, 'get_has_value') and obj.get_has_value():
                lit_lang = obj.get_has_language()

                # If a language is requested (e.g., 'pt')
                if language:
                    target_lang = language.strip().lower()

                    # If the literal has a tag, and it DOES NOT match 'pt', destroy it.
                    if lit_lang and not lit_lang.lower().startswith(target_lang):
                        return handler_dic

                    if not lit_lang:
                        return handler_dic

                handler_dic['text'] = obj.get_has_value()
                handler_dic['lan'] = lit_lang
                return handler_dic

            raw_str = str(obj)
            if "object at" not in raw_str:
                handler_dic['text'] = raw_str
                return handler_dic

        # --- 4. Normal Resource Handling (Concepts, Properties, Individuals) ---
        if hasattr(obj, 'get_has_identifier'):
            handler_dic['link'] = obj.get_has_identifier()
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

    def _format_statement(self, instances, identifier: str, language=None) -> Dict:
        """
        Extracts all statements where the subject matches the given identifier.
        """
        statements = {}

        # 1. Normalize the target identifier to a clean string
        target_id = str(identifier).strip() if identifier else ""
        if not target_id:
            return statements

        for instance in instances:
            if isinstance(instance, Statement):
                subj = instance.get_has_subject()

                # 2. Extract and normalize the subject's identifier
                subj_id = ""
                if hasattr(subj, 'has_identifier') and subj.has_identifier:
                    subj_id = str(subj.has_identifier).strip()
                elif isinstance(subj, str):
                    subj_id = subj.strip()

                # 3. String Comparison
                if subj_id == target_id:
                    predicate = instance.get_has_predicate()
                    obj = instance.get_has_object()

                    # 4. Predicate Resolution
                    pred_label = self._get_best_label(predicate, language) if predicate else "Annotation"

                    if pred_label not in statements:
                        statements[pred_label] = []

                    # 5. Resolve Object and Prevent Duplicates
                    if obj:
                        obj_data = self._resolve_resource_value(obj, language)


                        if obj_data not in statements[pred_label]:
                            statements[pred_label].append(obj_data)

        return statements

    @staticmethod
    def _clean_name(name: str) -> str:
        if not name: return ""

        name = re.sub(r'^(get_has_|get_|has_)', '', name)
        name = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', name)
        name = name.replace('_', ' ')

        return ' '.join(name.split()).title()

    def _parse_restriction(self, obj, language=None) -> list:
        """
        Recursively unpacks nested restrictions into a list of display parts
        (each part being a dict with 'text' and 'link').
        """
        if not obj: return []

        # 1. Handle lists of restrictions/concepts (e.g., in TruthFunctions or OneOf)
        if isinstance(obj, list) or isinstance(obj, set):
            parts = []
            for i, item in enumerate(obj):
                if i > 0:
                    parts.append({'text': ', ', 'link': None})
                parts.extend(self._parse_restriction(item, language))
            return parts

        obj_type = type(obj).__name__
        restriction_types = ["Restriction", "PropertyConceptRestriction", "Quantifier", "Cardinality", "TruthFunction",
                             "OneOf", "Value"]

        # 2. If it is a Restriction, recursively unpack its specific components
        if obj_type in restriction_types:
            parts = []

            # Helper to safely call getter methods (e.g., get_applies_on_property)
            def _get(instance, prop_name, default=None):
                getter = f"get_{prop_name}"
                if hasattr(instance, getter):
                    res = getattr(instance, getter)()
                    return res if res is not None else default
                return getattr(instance, prop_name, default)

            if obj_type == "Quantifier":
                prop = _get(obj, 'applies_on_property')
                quant = _get(obj, 'has_quantifier_type', "some")
                concept = _get(obj, 'applies_on_concept')

                parts.extend(self._parse_restriction(prop, language))
                parts.append({'text': f' {quant} ', 'link': None})
                parts.extend(self._parse_restriction(concept, language))

            elif obj_type == "Cardinality":
                prop = _get(obj, 'applies_on_property')
                card = _get(obj, 'has_cardinality_type', "exactly")
                card_num = _get(obj, 'has_cardinality')
                concept = _get(obj, 'applies_on_concept')

                parts.extend(self._parse_restriction(prop, language))
                parts.append({'text': f' {card} {card_num}',  'link': None})
                parts.extend(self._parse_restriction(concept, language))

            elif obj_type == "TruthFunction":
                operator = _get(obj, 'has_logical_operator', "and")
                concepts = _get(obj, 'applies_on_concept', [])
                if not isinstance(concepts, list): concepts = [concepts]

                parts.append({'text': '(', 'link': None})
                for i, c in enumerate(concepts):
                    if i > 0:
                        parts.append({'text': f' {operator} ', 'link': None})
                    parts.extend(self._parse_restriction(c, language))
                parts.append({'text': ')', 'link': None})

            elif obj_type == "OneOf":
                resources = _get(obj, 'applies_on_resource', [])
                if not isinstance(resources, list): resources = [resources]

                parts.append({'text': 'one of { ', 'link': None})
                for i, r in enumerate(resources):
                    if i > 0:
                        parts.append({'text': ', ', 'link': None})
                    parts.extend(self._parse_restriction(r, language))
                parts.append({'text': ' }', 'link': None})

            elif obj_type == "Value":
                prop = _get(obj, 'applies_on_property')
                resource = _get(obj, 'applies_on_resource')

                parts.extend(self._parse_restriction(prop, language))
                parts.append({'text': ' value ', 'link': None})
                parts.extend(self._parse_restriction(resource, language))

            return parts

        # 3. Base Case: We hit a non-blank node (Concept, Relation, String)
        # Send it to the main resolver to extract its URI link and clean text.
        resolved = self._resolve_resource_value(obj, language)

        if resolved.get('text'):
            return [{'text': resolved['text'], 'link': resolved.get('link'), 'type': resolved.get('type')}]

        return []