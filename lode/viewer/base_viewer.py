# base_viewer.py
import hashlib
from typing import Dict, List, Optional, Tuple
from lode.models import Literal, Model, Resource, Statement
from tests.test_reader import ontology_reader


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
        # If language is specified in params, search for label in specified language
        if language:
            # first, preferred label in language
            labels = resource.get_has_preferred_label()
            for label in labels:
                if hasattr(label, 'get_has_language') and label.get_has_language() == language:
                    return label.get_has_value()
            
            # then, label in language
            labels = resource.get_has_label()
            for label in labels:
                if hasattr(label, 'get_has_language') and label.get_has_language() == language:
                    return label.get_has_value()
        
        # Fallback: first preferred label (in any language)
        labels = resource.get_has_preferred_label()
        if labels:
            return labels[0].get_has_value()
        
        # Fallback 2: first label (in any language)
        labels = resource.get_has_label()
        if labels:
            return labels[0].get_has_value()
        
        # Fallback 3: Last part of the URI after "#" or "/"
        resource_id = resource.get_has_identifier()
        if resource_id:
            clean_resource_id = resource_id.split('#')[-1] if '#' in resource_id else resource_id.split('/')[-1]
            return clean_resource_id

        return None

    def get_view_data(self, resource_uri: Optional[str] = None, language: Optional[str] = None) -> Dict:
        """
        Main entry point called by the API
        Subclasses should override this to define their specific view strategy
        """
        # Fallback: generic flat list
        all_instances = self.get_all_instances()
        metadata_dict = self._find_and_format_metadata(all_instances)

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
                        clean_name = attr.replace('has_', '').replace('_', ' ').title()

                        # Process value (could be a list of objects)
                        # We use the helper to get clean text for each item
                        formatted_values = []
                        if isinstance(value, list):
                            for v in value:
                                val_dict = self._resolve_resource_value(v)
                                if val_dict['text']: formatted_values.append(val_dict)
                        else:
                            val_dict = self._resolve_resource_value(value)
                            if val_dict['text']: formatted_values.append(val_dict)

                        if formatted_values:
                            relations[clean_name] = formatted_values

            # Extract Statement Entities
            statements =  self._format_statement(all_instances, uri)

            entities.append({
                'type': type(instance).__name__,
                'uri': uri,
                'label': self._get_best_label(instance, language),
                'anchor_id': f"id_{safe_id}",
                'relations': relations,
                'statements': statements
            })

        entities.sort(key=lambda x: (x['label'] or x['uri']).lower())
        return entities

    def _find_and_format_metadata(self, all_instances: List[Resource]) -> Dict:
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
            'uri': [self._resolve_resource_value(ontology_model)],
            'label': [self._resolve_resource_value(self._get_best_label(ontology_model))]
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
                        clean_key = (attr_name.replace('get_has_', '').replace('get_', '').
                                     replace('_', ' ').title())

                        # 5. Ensure values are in a list
                        if not isinstance(values, list):
                            values = [values]

                        # 6. Extract the actual text values
                        extracted_values = []
                        for val in values:
                            entry = self._resolve_resource_value(val)
                            if entry['text']:
                                extracted_values.append(entry)

                        # 7. Add to structural data ONLY if we found valid text
                        if extracted_values:
                            data[clean_key] = extracted_values

        # 4. Statements
        data.update(self._format_statement(all_instances, ontology_model.has_identifier))
        '''
        for instance in all_instances:
            if isinstance(instance, Statement):
                subj = instance.get_has_subject()

                # Check if this statement is about our Ontology
                if subj and subj.has_identifier == ontology_model.has_identifier:

                    predicate = instance.get_has_predicate()
                    obj = instance.get_has_object()

                    # A. Handle Predicate Label
                    pred_label = self._get_best_label(predicate) if predicate else "Annotation"

                    if pred_label not in data:
                        data[pred_label] = []
                    #B. Handle Object label
                    if (obj_label := self._resolve_resource_value(obj)) not in data[pred_label]:
                        data[pred_label].append(obj_label)
        '''

        return data

    def _resolve_resource_value(self, obj) -> dict:
        """Helper: Extracts text and link from any object (Resource, Literal, or String)."""
        handler_dic = {
            'text': None,
            'link': None,
            'lan': None
        }

        if not obj: return handler_dic

        # 1. Case: It is already a plain string
        if isinstance(obj, str):
            handler_dic['text'] = obj
            return handler_dic

        # --- THE NEW FIX: Check for Literal Objects ---
        # If the object is a custom Literal class, it usually stores the actual text
        # in an attribute like 'value', 'text', or 'lexical_form'.
        if type(obj).__name__ == 'Literal':
            if hasattr(obj, 'get_has_value') and obj.has_value:
                if hasattr(obj, 'get_has_language'):
                    handler_dic['text'] = obj.get_has_value()
                    handler_dic['lan'] = obj.has_language
                    return handler_dic
                else:
                    handler_dic['text'] = obj.get_has_value()
                    return handler_dic

            # If we still can't find it, try standard string conversion
            raw_str = str(obj)
            if "object at" not in raw_str:
                handler_dic['text'] = raw_str
                return handler_dic

        # 2. Case: It is a Resource Object
        if hasattr(obj, 'get_has_identifier'):
            handler_dic['link'] = obj.get_has_identifier()

        # 3. Fallbacks
        if not handler_dic['text'] and handler_dic['link']:
            handler_dic['text'] = handler_dic['link']

        return handler_dic

    def _format_statement(self, instances, identifier: str) -> Dict:
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
                    pred_label = self._get_best_label(predicate) if predicate else "Annotation"

                    if pred_label not in statements:
                        statements[pred_label] = []

                    # 5. Resolve Object and Prevent Duplicates
                    if obj:
                        obj_data = self._resolve_resource_value(obj)


                        if obj_data not in statements[pred_label]:
                            statements[pred_label].append(obj_data)

        return statements