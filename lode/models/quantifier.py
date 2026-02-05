from .propertyConceptRestriction import PropertyConceptRestriction

class Quantifier(PropertyConceptRestriction):
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.has_quantifier_type = None # str[1]
    
    def get_has_quantifier_type(self):
        """Restituisce il valore has_quantifier_type"""
        return self.has_quantifier_type
        
    def set_has_quantifier_type(self, string):
        """Aggiunge una string a has_quantifier_type"""
        self.has_quantifier_type = string