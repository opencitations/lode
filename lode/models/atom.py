"""Atom: an atom of a SWRL rule."""
from .resource import Resource

class Atom(Resource):
    """A SWRL atom: a predicate applied to a list of arguments."""

    def __init__(self, **kwargs):
        """Create an atom with no arguments and no predicate."""
        super().__init__(**kwargs)
        self.has_arguments = []   # Variable or Resource [1...n]
        self.has_predicate = None   # Concept (classPredicate) or Property (propertyPredicate) [1]


    def get_has_arguments(self):
        """Return a copy of has_arguments."""
        return list(self.has_arguments)

    def set_has_arguments(self, v):
        """Add an argument (a variable or a resource) to has_arguments."""
        self.has_arguments.append(v)

    def get_has_predicate(self):
        """Return has_predicate (a concept or a property)."""
        return self.has_predicate

    def set_has_predicate(self, v):
        """Set has_predicate."""
        self.has_predicate = v