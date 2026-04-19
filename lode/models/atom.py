from .resource import Resource

class Atom(Resource):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.has_arguments = []   # Variable or Resource [1...n]
        self.has_predicate = None   # Concept (classPredicate) or Property (propertyPredicate) [1]


    def get_has_arguments(self): return list(self.has_arguments)
    def set_has_arguments(self, v): self.has_arguments.append(v)

    def get_has_predicate(self): return self.has_predicate
    def set_has_predicate(self, v): self.has_predicate = v