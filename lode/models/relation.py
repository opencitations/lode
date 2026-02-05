from .property import Property

class Relation(Property):
    """Rappresenta una Object Property RDF"""

    def __init__(self, **kwargs):
        # Chiama il costruttore della classe padre
        super().__init__(**kwargs)
        
        # Attributes
        self.is_asymmetric = False  # [1]
        self.is_inverse_functional = False  # [1]
        self.is_irreflexive = False  # [1]
        self.is_reflexive = False  # [1]
        self.is_symmetric = False  # [1]
        self.is_transitive = False  # [1]
        
        # Relations with Relations
        self.is_inverse_of = None  # 0..1 Relation
        self._has_property_chain = []  # 1..*

        # Relation with Concept
        self.has_range = [] # 1..*

    # Metodi per is_asymmetric
    def set_is_asymmetric(self, value):
        """Imposta is_asymmetric"""
        self.is_asymmetric = value
    
    def get_is_asymmetric(self):
        """Restituisce is_asymmetric"""
        return self.is_asymmetric

    # Metodi per is_inverse_functional
    def set_is_inverse_functional(self, value):
        """Imposta is_inverse_functional"""
        self.is_inverse_functional = value
    
    def get_is_inverse_functional(self):
        """Restituisce is_inverse_functional"""
        return self.is_inverse_functional

    # Metodi per is_irreflexive
    def set_is_irreflexive(self, value):
        """Imposta is_irreflexive"""
        self.is_irreflexive = value
    
    def get_is_irreflexive(self):
        """Restituisce is_irreflexive"""
        return self.is_irreflexive

    # Metodi per is_reflexive
    def set_is_reflexive(self, value):
        """Imposta is_reflexive"""
        self.is_reflexive = value
    
    def get_is_reflexive(self):
        """Restituisce is_reflexive"""
        return self.is_reflexive

    # Metodi per is_symmetric
    def set_is_symmetric(self, value):
        """Imposta is_symmetric"""
        self.is_symmetric = value
    
    def get_is_symmetric(self):
        """Restituisce is_symmetric"""
        return self.is_symmetric

    # Metodi per is_transitive
    def set_is_transitive(self, value):
        """Imposta is_transitive"""
        self.is_transitive = value
    
    def get_is_transitive(self):
        """Restituisce is_transitive"""
        return self.is_transitive

    # Metodi per is_inverse_of (0..1 - singolo valore)
    def set_is_inverse_of(self, relation):
        """Imposta is_inverse_of"""
        self.is_inverse_of = relation
    
    def get_is_inverse_of(self):
        """Restituisce is_inverse_of"""
        return self.is_inverse_of

    # Metodi per has_property_chain
    def set_has_property_chain(self, relation):
        """Aggiunge una relation a has_property_chain"""
        self._has_property_chain.append(relation)
    
    def get_has_property_chain(self):
        """Restituisce una copia della lista has_property_chain"""
        return list(set(self._has_property_chain))
    
    # def set_has_range(self, concept):
    #     """Imposta has_range"""
    #     self.has_range = concept
    
    # def get_has_range(self):
    #     """Restituisce has_range"""
    #     return list(self.has_range)
    
