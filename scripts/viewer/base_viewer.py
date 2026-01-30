# base_viewer.py
from typing import Dict, List, Optional
from models import Resource

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
            instance_set = self.get_instances_from_single_resource(resource_uri)
            
            if not instance_set:
                return {'error': f'Resource {resource_uri} not found'}
            
            # Converti set in lista per gestire tutte le istanze
            instance_list = list(instance_set) if isinstance(instance_set, set) else [instance_set]
            
            entities = []
            for instance in instance_list:
                entities.append({
                    'type': type(instance).__name__,
                    'uri': instance.has_identifier,
                    'label': self._get_best_label(instance)
                })
            
            return {
                'single_resource': True,
                'entities': entities
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