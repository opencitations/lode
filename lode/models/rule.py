"""Rule: a SWRL rule."""
from .resource import Resource

class Rule(Resource):
    """A SWRL rule: when every antecedent atom holds, the consequent atoms hold."""

    def __init__(self, **kwargs):
        """Create a rule with no antecedent and no consequent."""
        super().__init__(**kwargs)
        self.has_antecedent = []  # Atom [1..*]
        self.has_consequent = []  # Atom [1..*]

    def get_has_antecedent(self):
        """Return a copy of has_antecedent."""
        return list(self.has_antecedent)

    def set_has_antecedent(self, atom):
        """Add an atom to has_antecedent."""
        self.has_antecedent.append(atom)

    def get_has_consequent(self):
        """Return a copy of has_consequent."""
        return list(self.has_consequent)

    def set_has_consequent(self, atom):
        """Add an atom to has_consequent."""
        self.has_consequent.append(atom)