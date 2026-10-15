"""Container: an RDF container or list."""
from .resource import Resource

class Container(Resource):
    """RDF Container (Bag, Seq, Alt, List)"""

    def __init__(self):
        """Create a container with no members."""
        super().__init__()
        self.members = []
    
    def set_has_member(self, member):
        """Add a single member, ignoring duplicates."""
        if member not in self.members:
            self.members.append(member)
    
    def set_has_members(self, members: list):
        """Set all the members at once, from a copy of `members`."""
        self.members = members.copy()
    
    def get_has_members(self):
        """Return a copy of the members list."""
        return self.members.copy()
