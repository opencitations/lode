"""DatatypeRestriction: an owl:DatatypeRestriction (a datatype narrowed by facets)."""
from .restriction import Restriction

class DatatypeRestriction(Restriction):
    """A datatype narrowed by XSD facet/value pairs, such as numeric bounds."""

    def __init__(self, **kwargs):
        """Create a datatype restriction with no base datatype or facets."""
        super().__init__(**kwargs)
        self.applies_on_concept = None  # Datatype from owl:onDatatype
        self.has_facets = []  # Ordered (facet operator, Literal) pairs
        self.has_restriction_value = None  # Last value, for single-facet callers


    def get_applies_on_concept(self):
        """Return the base datatype."""
        return self.applies_on_concept

    def set_applies_on_concept(self, datatype):
        """Set the base datatype without changing its facets."""
        self.applies_on_concept = datatype

    def set_has_facet(self, constraint, value):
        """Add a facet/value pair, preserving its association and list order."""
        pair = (constraint, value)
        if pair not in self.has_facets:
            self.has_facets.append(pair)
        self.set_has_restriction_value(value)

    def get_has_facets(self):
        """Return a copy of all facet/value pairs."""
        return list(self.has_facets)

    def set_has_restriction_value(self, string):
        """Set has_restriction_value (the literal value of the facet)."""
        self.has_restriction_value = string

    def get_has_restriction_value(self):
        """Return the last facet value; use get_has_facets() for all constraints."""
        return self.has_restriction_value
