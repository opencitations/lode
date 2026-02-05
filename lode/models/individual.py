from .resource import Resource

class Individual(Resource):
    """
    Rappresenta un'istanza individuale di una classe (owl:NamedIndividual).
    Estende Resource con relazioni specifiche per individui OWL.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Relations with Individual
        self.is_same_as = []         # 0..*
        self.is_different_from = []  # 0..*
        # Relations with Concept (ereditato ma qui esplicitato, perchè cambia la cardinalità)
        self.has_type = []  # 1..* 

    def get_has_type(self):
        return list(self.has_type)
    
    def set_has_type(self, concept):
        self.has_type.append(concept)
    
    def get_is_same_as(self):
        """Restituisce la lista is_same_as [0..*]"""
        return list(self.is_same_as)
    
    def set_is_same_as(self, individual):
        """Aggiunge un Individual a is_same_as [0..*]"""
        self.is_same_as.append(individual)
    
    def get_is_different_from(self):
        """Restituisce la lista is_different_from [0..*]"""
        return list(self.is_different_from)
    
    def set_is_different_from(self, individual):
        """Aggiunge un Individual a is_different_from [0..*]"""
        self.is_different_from.append(individual)
