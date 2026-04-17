from .resource import Resource

class Atom(Resource):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.has_argument1 = None   # Variable or Resource [1]
        self.has_argument2 = None   # Variable, Resource (Individual or Literal (optional) per owl?) [0...1]
        self.has_predicate = None   # Concept (classPredicate) or Property (propertyPredicate) [1]

    def get_has_argument1(self): return self.has_argument1
    def set_has_argument1(self, v): self.has_argument1 = v

    def get_has_argument2(self): return self.has_argument2
    def set_has_argument2(self, v): self.has_argument2 = v

    def get_has_predicate(self): return self.has_predicate
    def set_has_predicate(self, v): self.has_predicate = v