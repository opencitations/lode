from .restriction import Restriction

class DatatypeRestriction(Restriction):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.applies_on_concept = None  # Datatype (from owl:onDatatype) string (xsd:pattern, xsd:minInclusive, ...)
        self.has_restriction_value = None  # Literal (the corresponding value e.g. 0.0)


    def get_applies_on_concept(self):
        return self.applies_on_concept

    def set_applies_on_concept(self, datatype):
        self.applies_on_concept = datatype

    def set_has_restriction_value(self, string):
        self.has_restriction_value = string

    def get_has_restriction_value(self):
        return self.has_restriction_value