from .resource import Resource

class Rule(Resource):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.has_antecedent = []  # Atom [1..*]
        self.has_consequent = []  # Atom [1..*]

    def get_has_antecedent(self): return list(self.has_antecedent)
    def set_has_antecedent(self, atom): self.has_antecedent.append(atom)

    def get_has_consequent(self): return list(self.has_consequent)
    def set_has_consequent(self, atom): self.has_consequent.append(atom)