"""Collection: a SKOS collection of concepts."""
from .resource import Resource

class Collection(Resource):
    """A SKOS collection: a labelled group of concepts or other collections."""

    def __init__(self, **kwargs):
        """Create an unordered collection with no members."""
        super().__init__(**kwargs)

        self.is_ordered= False # bool[1]
        self.has_member= [] # [0..*]

    def get_is_ordered(self):
        """Return is_ordered."""
        return self.is_ordered
    
    def set_is_ordered(self, bool):
        """Set is_ordered."""
        self.is_ordered = bool

    def get_has_member(self):
        """Return a copy of has_member."""
        return list(self.has_member)
    
    def set_has_member(self, concept_or_collection):
        """Add a concept or a collection to has_member."""
        self.has_member.append(concept_or_collection)
    