from .propertyConceptRestriction import PropertyConceptRestriction

class Cardinality(PropertyConceptRestriction):
            
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.has_cardinality = None # int[1]
        self.has_cardinality_type  = None # str[1]

    def get_has_cardinality(self):
        """Restituisce il valore has_cardinality"""
        return self.has_cardinality
        
    def set_has_cardinality(self, var):
        """Aggiunge un integer a has_cardinality"""
        self.has_cardinality = int(var)
    
    def get_has_cardinality_type(self):
        """Restituisce il valore has_cardinality_type"""
        return self.has_cardinality_type
        
    def set_has_cardinality_type(self, string):
        """Aggiunge una string a has_cardinality_type"""
        self.has_cardinality_type = string

