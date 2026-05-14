from .restriction import Restriction

class PropertySelfRestriction(Restriction):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.applies_on_property = None # [1]

    def get_applies_on_property(self):
        return self.applies_on_property
        
    def set_applies_on_property(self, relation):
        self.applies_on_property = relation

