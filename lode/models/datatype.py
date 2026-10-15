"""Datatype: an RDFS/OWL datatype such as xsd:string."""
from .concept import Concept

class Datatype(Concept):
    """A datatype: the kind of value a literal can have."""

    def __init__(self, **kwargs):
        """Create a datatype; all state comes from Concept."""
        super().__init__(**kwargs)
