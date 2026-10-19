"""OneOf: an owl:oneOf enumeration."""
from .restriction import Restriction

class OneOf(Restriction):
    """A class defined by listing its members (owl:oneOf)."""

    def __init__(self, **kwargs):
        """Create an enumeration with no resources."""
        super().__init__(**kwargs)

        self.applies_on_resource = [] # 1..*

    def get_applies_on_resource(self):
        """Return a copy of applies_on_resource."""
        return list(self.applies_on_resource)
        
    def set_applies_on_resource(self, resource):
        """Add a resource to applies_on_resource."""
        self.applies_on_resource.append(resource)

