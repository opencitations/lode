from .restriction import Restriction

class TruthFunction(Restriction):

    # the has_cardinality_type can have one of three values: "max", "min", and "exact". Any other string will be interpreted as "exact".
    # fallback = exact
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.has_logical_operator = None # string[1]
        self.applies_on_concept = [] # 1..*

    def get_has_logical_operator(self):
        """Restituisce la stringa per has_logical_operator"""
        return self.has_logical_operator
        
    def set_has_logical_operator(self, literal):
        """Aggiunge una str a as_logical_operator"""
        self.has_logical_operator = literal

    def get_applies_on_concept(self):
        """Restituisce la lista applies on concept"""
        return list(self.applies_on_concept)
        
    def set_applies_on_concept(self, concept):
        """Aggiunge un Concept a applies_on_concept """
        self.applies_on_concept.append(concept)

