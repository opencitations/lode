import hashlib
from typing import Dict, List, Optional, Tuple
from lode.models import Resource, model, Model

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
        clean_resource_id = resource_id.split('#')[-1] if '#' in resource_id else resource_id.split('/')[-1]
        return clean_resource_id
    
    # ========Changes in the base_viewer=======

    def get_view_data(self, resource_uri: Optional[str] = None, language: Optional[str] = None) -> Dict:
        """
        Main entry point called by the API
        Subclasses should override this to define their specific view strategy
        """
        if resource_uri:
            # Get the specific entity data
            data = self._handle_single_resource(resource_uri, language)

            return data

        # Fallback: generic flat list
        instances = self.get_all_instances()
        return {
            'entities': self._format_entities(instances, language)
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

            # 1. Extract and Format Relations
            relations = {}
            # We filter out internal python attributes (starting with _)
            for attr, value in instance.__dict__.items():
                if attr.startswith('_') or not value:
                    continue

                # Clean the name: 'has_sub_class' -> 'Sub Class'
                clean_name = attr.replace('has_', '').replace('is_', '').replace('_', ' ').title()

                # 2. Convert Values to HTML Links (The Logic)
                formatted_value = self._format_relation_value(value)
                relations[clean_name] = formatted_value

            entities.append({
                'type': type(instance).__name__,
                'uri': uri,
                'label': self._get_best_label(instance, language),
                'anchor_id': f"id_{safe_id}",
                'relations': relations
            })

        entities.sort(key=lambda x: (x['label'] or x['uri']).lower())
        return entities

    def _format_relation_value(self, value: any) -> any:
        """
        Helper: Checks if a value is a Resource (Concept/Property) and converts it
        to a clickable dictionary format for the template.
        """
        # Case A: Value is a List of items (e.g., disjoint classes)
        if isinstance(value, list) or isinstance(value, set):
            return [self._format_single_item(v) for v in value]

        # Case B: Single Value
        return self._format_single_item(value)

    def _format_single_item(self, item: any) -> Dict[str, any]:
        """
        Helper: Formats a single item (Resource object or primitive).
        """
        # Check if it is a Resource AND has a valid identifier
        if hasattr(item, 'has_identifier') and item.has_identifier:
            uri = item.has_identifier

            # Generate ID safely
            safe_id = hashlib.md5(str(uri).encode('utf-8')).hexdigest()

            return {
                'text': self._get_best_label(item),
                'link': f"#id_{safe_id}",
                'is_link': True
            }

        # Fallback for Primitives or Resources without IDs
        return {
            'text': str(item) if item is not None else "",
            'link': None,
            'is_link': False
        }