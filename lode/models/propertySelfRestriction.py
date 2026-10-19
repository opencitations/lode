"""PropertySelfRestriction: an owl:hasSelf restriction."""
from .restriction import Restriction

class PropertySelfRestriction(Restriction):
    """A restriction on the individuals related to themselves by a property (owl:hasSelf)."""

    def __init__(self, **kwargs):
        """Create a self restriction with no property."""
        super().__init__(**kwargs)

        self.applies_on_property = None # [1]

    def get_applies_on_property(self):
        """Return applies_on_property."""
        return self.applies_on_property
        
    def set_applies_on_property(self, relation):
        """Set applies_on_property."""
        self.applies_on_property = relation

