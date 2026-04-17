from .resource import Resource

class Rule(Resource):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.has_body = []  # Atom [1...*]
        self.has_head = []  # Atom [1...*]

    def get_has_body(self): return list(self.has_body)
    def set_has_body(self, atom): self.has_body.append(atom)

    def get_has_head(self): return list(self.has_head)
    def set_has_head(self, atom): self.has_head.append(atom)