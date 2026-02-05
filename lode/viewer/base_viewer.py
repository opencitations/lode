# base_viewer.py
from typing import Dict, List, Optional, Tuple
from lode.models import Resource

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
            return self._handle_single_resource(resource_uri, language)

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
            entities.append({
                'type': type(instance).__name__,
                'uri': instance.has_identifier,
                'label': self._get_best_label(instance, language)
            })

        entities.sort(key=lambda x: (x['label'] or x['uri']).lower())
        return entities