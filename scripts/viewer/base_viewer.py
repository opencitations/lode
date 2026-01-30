# base_viewer.py
from typing import Dict, List, Optional
from models import Resource

class BaseViewer:
    """Base viewer per visualizzare istanze estratte dal Reader."""
    
    def __init__(self, reader):
        self.reader = reader
        self._cache = reader._instance_cache
    
    def get_all_instances(self) -> List:
        """Ottiene tutte le istanze (esclusi literal)."""
        instances = []
        
        for uri_id, instance_set in self._cache.items():
            if isinstance(uri_id, str) and uri_id.startswith("LITERAL::"):
                continue
            
            instance_list = instance_set if isinstance(instance_set, set) else [instance_set]
            instances.extend(instance_list)
        
        return instances
    
    def _get_best_label(self, resource: Resource) -> Optional[str]:
        """Ottiene la miglior label: preferred_label > label > identifier."""
        labels = resource.get_has_preferred_label()
        if labels:
            return labels[0].get_has_value()
        
        labels = resource.get_has_label()
        if labels:
            return labels[0].get_has_value()
        
        return resource.has_identifier
    
    def get_view_data(self, resource_uri: Optional[str] = None) -> Dict:
        """
        Prepara dati per la vista.
        Se resource_uri è fornito, mostra solo quella risorsa.
        Altrimenti mostra tutte le entità.
        """
        if resource_uri:
            # Vista singola risorsa
            instance = self.reader.get_instance(resource_uri)
            if not instance:
                return {'error': f'Resource {resource_uri} not found'}
            
            return {
                'single_resource': True,
                'entity': {
                    'type': type(instance).__name__,
                    'uri': instance.has_identifier,
                    'label': self._get_best_label(instance)
                }
            }
        
        # Vista tutte le entità
        instances = self.get_all_instances()
        
        entities = []
        for instance in instances:
            entities.append({
                'type': type(instance).__name__,
                'uri': instance.has_identifier,
                'label': self._get_best_label(instance)
            })
        
        return {'entities': entities}