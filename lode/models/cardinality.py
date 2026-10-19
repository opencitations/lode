"""Cardinality: an OWL cardinality restriction (exactly, min or max)."""
from .propertyConceptRestriction import PropertyConceptRestriction

class Cardinality(PropertyConceptRestriction):
    """A restriction on how many values a property can take on a concept."""

    def __init__(self, **kwargs):
        """Create a cardinality restriction with no number and no type set."""
        super().__init__(**kwargs)

        self.has_cardinality = None # int[1]
        self.has_cardinality_type  = None # str[1]

    def get_has_cardinality(self):
        """Return has_cardinality, the number of values."""
        return self.has_cardinality
        
    def set_has_cardinality(self, var):
        """Set has_cardinality, converting the value to int."""
        self.has_cardinality = int(var)
    
    def get_has_cardinality_type(self):
        """Return has_cardinality_type ("exactly", "min" or "max")."""
        return self.has_cardinality_type
        
    def set_has_cardinality_type(self, string):
        """Set has_cardinality_type ("exactly", "min" or "max")."""
        self.has_cardinality_type = string

