from .restriction import Restriction

class PropertyConceptRestriction(Restriction):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.applies_on_property = None # 1
        self.applies_on_concept = None # 1

    def get_applies_on_property(self):
        """Restituisce il valore applies on property"""
        return self.applies_on_property
        
    def set_applies_on_property(self, property):
        """Aggiunge un Property a applies_on_property """
        self.applies_on_property = property

    def get_applies_on_concept(self):
        """Restituisce la lista applies on concept"""
        return self.applies_on_concept
        
    def set_applies_on_concept(self, concept):
        """Aggiunge un Concept a applies_on_concept """
        self.applies_on_concept = concept
