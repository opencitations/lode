# base_viewer.py
import hashlib
from typing import Dict, List, Optional, Tuple
from lode.models import Model, Resource, Statement
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
    
    # ========Changes in the base_viewer=======

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
            'entities': self._format_entities(instances, language)
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
        entities = []
        for instance in instances:
            uri = instance.has_identifier
            #Create a safe HTML ID to facilitate on-page navigation
            safe_id = hashlib.md5(str(uri).encode('utf-8')).hexdigest()

            # Extract internal attributes (SuperClasses, etc.)
            relations = {}
            for attr, value in instance.__dict__.items():
                if not attr.startswith('_') and value: #Skip internal python attributes
                    # Clean up attribute name (e.g., 'has_super_class' -> 'Super Class')
                    clean_name = attr.replace('has_', '').replace('_', ' ').title()
                    relations[clean_name] = value

            entities.append({
                'type': type(instance).__name__,
                'uri': uri,
                'label': self._get_best_label(instance, language),
                'anchor_id': f"id_{safe_id}",
                'relations': relations
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
            'uri': ontology_model.has_identifier,
            'label': self._get_best_label(ontology_model)
        }

        # 3. Model.py fields
        if ontology_model.get_has_version():
            data['Version'] = [v.has_identifier for v in ontology_model.get_has_version()]

        if ontology_model.get_has_version_info():
            data['Version Info'] = [vi.has_value for vi in ontology_model.get_has_version_info()]

        # 4. Statements
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

                    obj_label = obj.has_value

                    if obj_label not in data[pred_label]:
                        data[pred_label].append(obj_label)

        print(data)
        return data






