"""Restriction: base class of OWL restrictions and anonymous class expressions."""
from .concept import Concept

class Restriction(Concept):
    """Base of the anonymous classes built by restrictions and logical operators."""

    def __init__(self, **kwargs):
        """Create a restriction; all state comes from Concept."""
        super().__init__(**kwargs)

