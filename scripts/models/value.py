from .propertyConceptRestriction import PropertyConceptRestriction

class Value(PropertyConceptRestriction):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.applies_on_resource = None # 1

    def get_applies_on_resource(self):
        """Restituisce la lista applies on resource"""
        return self.applies_on_resource
        
    def set_applies_on_resource(self, resource):
        """Aggiunge un Resource a applies_on_resource """
        self.applies_on_resource = resource
