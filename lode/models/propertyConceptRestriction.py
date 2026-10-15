"""PropertyConceptRestriction: a restriction that links a property to a concept."""
from .restriction import Restriction

class PropertyConceptRestriction(Restriction):
    """Base of the restrictions that apply a property to a concept (quantifiers, cardinalities)."""

    def __init__(self, **kwargs):
        """Create a restriction with no property, no concept, and is_inverse False."""
        super().__init__(**kwargs)

        self.applies_on_property = None # 1
        self.applies_on_concept = None # 1
        self.is_inverse = False #bool 1

    def get_applies_on_property(self):
        """Return applies_on_property."""
        return self.applies_on_property
        
    def set_applies_on_property(self, property):
        """Set applies_on_property."""
        self.applies_on_property = property

    def get_applies_on_concept(self):
        """Return applies_on_concept."""
        return self.applies_on_concept
        
    def set_applies_on_concept(self, concept):
        """Set applies_on_concept."""
        self.applies_on_concept = concept

    def get_is_inverse(self):
        """Return is_inverse."""
        return self.is_inverse
        
    def set_is_inverse(self, boolean):
        """Set is_inverse: whether the restriction is on the inverse of the property."""
        self.is_inverse = boolean
