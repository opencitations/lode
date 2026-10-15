"""Attribute: an owl:DatatypeProperty."""
from .property import Property

class Attribute(Property):
    """A datatype property: it relates a resource to literals."""

    def __init__(self, **kwargs):
        """Create an attribute with empty has_range and has_type."""
        super().__init__(**kwargs)

        # Relation with Literal
        self.has_range = [] # Already defined in the parent class, card 1..*
        self.has_type = [] # [1..*]