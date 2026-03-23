from .restriction import Restriction

class DatatypeRestriction(Restriction):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.has_constraint = []         # list of Annotation (xsd:pattern, xsd:minInclusive, ...)
        self.has_restriction_value = []  # list of Literal (the corresponding values)

    def set_has_constraint(self, annotation):
        self.has_constraint.append(annotation)

    def get_has_constraint(self):
        return list(self.has_constraint)

    def set_has_restriction_value(self, literal):
        self.has_restriction_value.append(literal)

    def get_has_restriction_value(self):
        return list(self.has_restriction_value)