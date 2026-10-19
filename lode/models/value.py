"""Value: an owl:hasValue restriction."""
from .restriction import Restriction

class Value(Restriction):
    """A restriction requiring a property to take one specific resource as value (owl:hasValue)."""

    def __init__(self, **kwargs):
        """Create a value restriction with no resource and no property."""
        super().__init__(**kwargs)

        self.applies_on_resource = None # 1
        self.applies_on_property = None # 1

    def get_applies_on_resource(self):
        """Return applies_on_resource."""
        return self.applies_on_resource
        
    def set_applies_on_resource(self, resource):
        """Set applies_on_resource."""
        self.applies_on_resource = resource

    def get_applies_on_property(self):
        """Return applies_on_property."""
        return self.applies_on_property

    def set_applies_on_property(self, prop):
        """Set applies_on_property."""
        self.applies_on_property = prop