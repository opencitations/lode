from .concept import Concept

class Restriction(Concept):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.applies_on_concept = [] # 1..*

    def get_applies_on_concept(self):
        """Restituisce la lista applies on concept"""
        return list(self.applies_on_concept)
        
    def set_applies_on_concept(self, concept):
        """Aggiunge un Concept a applies_on_concept """
        self.applies_on_concept.append(concept)

