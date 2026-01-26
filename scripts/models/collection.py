from .resource import Resource

class Collection(Resource):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.is_ordered= False # bool[1]
        self.has_member= [] # [0..*]

    def get_is_ordered(self):
        """Restituisce il valore is_ordered bool[1]"""
        return self.is_ordered
    
    def set_is_ordered(self, bool):
        """Setta il valore di is_ordered bool [1]"""
        self.is_ordered = bool

    def get_has_member(self):
        """Restituisce il valore has_member [0..*]"""
        return list(self.has_member)
    
    def set_has_member(self, concept_or_collection):
        """Setta il valore di has_member [0..*]"""
        self.has_member.append(concept_or_collection)
    