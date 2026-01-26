from .property import Property

class Attribute(Property):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Relation with Literal
        self.has_range = [] # GIà definita in parent class, card 1..*
        self.has_type = [] # [1..*]