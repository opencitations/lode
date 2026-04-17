from .restriction import Restriction

class DatatypeRestriction(Restriction):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.has_constraint = None         # Datatype (xsd:pattern, xsd:minInclusive, ...)
        self.has_restriction_value = None  # string (the corresponding value e.g. 0.0)

    def set_has_constraint(self, datatype):
        self.has_constraint = datatype

    def get_has_constraint(self):
        return self.has_constraint

    def set_has_restriction_value(self, string):
        self.has_restriction_value = string

    def get_has_restriction_value(self):
        return self.has_restriction_value