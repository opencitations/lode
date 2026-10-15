"""TruthFunction: a class expression built with a logical operator (and, or, not)."""
from .restriction import Restriction

class TruthFunction(Restriction):
    """A class expression combining concepts with a logical operator (and, or, not)."""

    # the has_cardinality_type can have one of three values: "max", "min", and "exact". Any other string will be interpreted as "exact".
    # fallback = exact
    
    def __init__(self, **kwargs):
        """Create a truth function with no operator and no concepts."""
        super().__init__(**kwargs)

        self.has_logical_operator = None # string[1]
        self.applies_on_concept = [] # 1..*

    def get_has_logical_operator(self):
        """Return has_logical_operator."""
        return self.has_logical_operator
        
    def set_has_logical_operator(self, literal):
        """Set has_logical_operator."""
        self.has_logical_operator = literal

    def get_applies_on_concept(self):
        """Return a copy of applies_on_concept."""
        return list(self.applies_on_concept)
        
    def set_applies_on_concept(self, concept):
        """Add a concept to applies_on_concept."""
        self.applies_on_concept.append(concept)

