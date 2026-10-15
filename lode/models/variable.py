"""Variable: a variable of a SWRL rule."""
from .resource import Resource

class Variable(Resource):
    """A SWRL variable, used as an argument of an atom."""

    def __init__(self, **kwargs):
        """Create a variable; all state comes from Resource."""
        super().__init__(**kwargs)