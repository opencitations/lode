"""DatatypeRestriction: an owl:DatatypeRestriction (a datatype narrowed by facets)."""
from .restriction import Restriction

class DatatypeRestriction(Restriction):
    """A datatype narrowed by an XSD facet, such as a pattern or a minimum value."""

    def __init__(self, **kwargs):
        """Create a datatype restriction with no datatype and no facet value."""
        super().__init__(**kwargs)
        self.applies_on_concept = None  # Datatype (from owl:onDatatype) string (xsd:pattern, xsd:minInclusive, ...)
        self.has_restriction_value = None  # Literal (the corresponding value e.g. 0.0)


    def get_applies_on_concept(self):
        """Return applies_on_concept (the datatype, or the facet string)."""
        return self.applies_on_concept

    def set_applies_on_concept(self, datatype):
        """Set applies_on_concept (the datatype, or the facet string)."""
        self.applies_on_concept = datatype

    def set_has_restriction_value(self, string):
        """Set has_restriction_value (the literal value of the facet)."""
        self.has_restriction_value = string

    def get_has_restriction_value(self):
        """Return has_restriction_value (the literal value of the facet)."""
        return self.has_restriction_value