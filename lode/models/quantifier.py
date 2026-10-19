"""Quantifier: an existential or universal property restriction."""
from .propertyConceptRestriction import PropertyConceptRestriction

class Quantifier(PropertyConceptRestriction):
    """A quantified restriction of a property on a concept.

    The type is "some" (owl:someValuesFrom) or "only" (owl:allValuesFrom).
    """

    def __init__(self, **kwargs):
        """Create a quantifier with no type set."""
        super().__init__(**kwargs)

        self.has_quantifier_type = None # str[1]
    
    def get_has_quantifier_type(self):
        """Return has_quantifier_type ("some" or "only")."""
        return self.has_quantifier_type
        
    def set_has_quantifier_type(self, string):
        """Set has_quantifier_type ("some" or "only")."""
        self.has_quantifier_type = string