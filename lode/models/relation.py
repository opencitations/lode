"""Relation: an owl:ObjectProperty and its logical characteristics."""
from .property import Property

class Relation(Property):
    """Represents an RDF Object Property"""

    def __init__(self, **kwargs):
        """Create a relation with every characteristic set to False and no inverses or chains."""
        super().__init__(**kwargs)
        
        # Attributes
        self.is_asymmetric = False  # [1]
        self.is_inverse_functional = False  # [1]
        self.is_irreflexive = False  # [1]
        self.is_reflexive = False  # [1]
        self.is_symmetric = False  # [1]
        self.is_transitive = False  # [1]
        
        # Relations with Relations
        self.is_inverse_of = []  # [0..*] Relation
        self.has_property_chain = []  # 1..*

        # Relation with Concept
        self.has_range = [] # 1..*

    # Methods foris_asymmetric
    def set_is_asymmetric(self, value):
        """Set is_asymmetric."""
        self.is_asymmetric = value
    
    def get_is_asymmetric(self):
        """Return is_asymmetric."""
        return self.is_asymmetric

    # Methods foris_inverse_functional
    def set_is_inverse_functional(self, value):
        """Set is_inverse_functional."""
        self.is_inverse_functional = value
    
    def get_is_inverse_functional(self):
        """Return is_inverse_functional."""
        return self.is_inverse_functional

    # Methods foris_irreflexive
    def set_is_irreflexive(self, value):
        """Set is_irreflexive."""
        self.is_irreflexive = value
    
    def get_is_irreflexive(self):
        """Return is_irreflexive."""
        return self.is_irreflexive

    # Methods foris_reflexive
    def set_is_reflexive(self, value):
        """Set is_reflexive."""
        self.is_reflexive = value
    
    def get_is_reflexive(self):
        """Return is_reflexive."""
        return self.is_reflexive

    # Methods foris_symmetric
    def set_is_symmetric(self, value):
        """Set is_symmetric."""
        self.is_symmetric = value
    
    def get_is_symmetric(self):
        """Return is_symmetric."""
        return self.is_symmetric

    # Methods foris_transitive
    def set_is_transitive(self, value):
        """Set is_transitive."""
        self.is_transitive = value
    
    def get_is_transitive(self):
        """Return is_transitive."""
        return self.is_transitive

    def get_is_inverse_of(self):
        """Return a de-duplicated copy of is_inverse_of (order is not preserved)."""
        return list(set(self.is_inverse_of))
    
    def set_is_inverse_of(self, relation):
        """Add a relation to is_inverse_of."""
        self.is_inverse_of.append(relation)

    def set_has_property_chain(self, relation):
        """Add a relation to has_property_chain, ignoring duplicates."""
        if relation not in self.has_property_chain:
            self.has_property_chain.append(relation)

    def get_has_property_chain(self):
        """Return a copy of has_property_chain."""
        return list(self.has_property_chain)
    
    # def set_has_range(self, concept):
    #     """Imposta has_range"""
    #     self.has_range = concept
    
    # def get_has_range(self):
    #     """Restituisce has_range"""
    #     return list(self.has_range)
    
