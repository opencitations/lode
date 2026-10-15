"""Individual: an OWL named individual."""
from .resource import Resource

class Individual(Resource):
    """
    Represents an individual instance of a class (owl:NamedIndividual).
    Extends Resource with the relations specific to OWL individuals.
    """

    def __init__(self, **kwargs):
        """Create an individual with empty is_same_as and is_different_from lists."""
        super().__init__(**kwargs)
        
        # Relations with Individual
        self.is_same_as = []         # 0..*
        self.is_different_from = []  # 0..*
        # Relations with Concept (inherited but made explicit here, because the cardinality changes)
        # self.has_type = []  # 1..* 

    # def get_has_type(self):
    #     return list(self.has_type)
    
    # def set_has_type(self, concept):
    #     self.has_type.append(concept)
    
    def get_is_same_as(self):
        """Return a copy of is_same_as [0..*]."""
        return list(self.is_same_as)
    
    def set_is_same_as(self, individual):
        """Add an individual to is_same_as [0..*]."""
        self.is_same_as.append(individual)
    
    def get_is_different_from(self):
        """Return a copy of is_different_from [0..*]."""
        return list(self.is_different_from)
    
    def set_is_different_from(self, individual):
        """Add an individual to is_different_from [0..*]."""
        self.is_different_from.append(individual)
