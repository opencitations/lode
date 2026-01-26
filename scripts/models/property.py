from .resource import Resource

class Property(Resource):
    """Represents an RDF Property"""

    def __init__(self, **kwargs):
        
        super().__init__(**kwargs)
        
        # Attributes
        self.is_functional = False  # bool [1]
        
        # Relations with Properties (0..*)
        self._is_sub_property_of = []
        self._is_disjoint_with = []
        self._is_equivalent_to = []
        
        # Relation with Resource (1..*) 
        # Nell'extractor - default per OWL ontologies = OWL.Thing
        self._has_range = []  
        
        # Relations with Concept (1..*)
        # Nell'extractor - default per OWL ontologies = OWL.Thing
        self._has_domain = []  

    # Metodi per is_functional
    def set_is_functional(self, bool):
        """Imposta is_functional"""
        self.is_functional = bool
    
    def get_is_functional(self):
        """Restituisce is_functional"""
        return self.is_functional

    # Metodi per is_sub_property_of
    def set_is_sub_property_of(self, property_obj):
        """Aggiunge una property a is_sub_property_of"""
        self._is_sub_property_of.append(property_obj)
    
    def get_is_sub_property_of(self):
        """Restituisce una copia della lista is_sub_property_of"""
        return list(set(self._is_sub_property_of))

    # Metodi per is_disjoint_with
    def set_is_disjoint_with(self, property_obj):
        """Aggiunge una property a is_disjoint_with"""
        self._is_disjoint_with.append(property_obj)
    
    def get_is_disjoint_with(self):
        """Restituisce una copia della lista is_disjoint_with"""
        return list(set(self._is_disjoint_with))

    # Metodi per is_equivalent_to
    def set_is_equivalent_to(self, property_obj):
        """Aggiunge una property a is_equivalent_to"""
        self._is_equivalent_to.append(property_obj)
    
    def get_is_equivalent_to(self):
        """Restituisce una copia della lista is_equivalent_to"""
        return list(set(self._is_equivalent_to))

    # Metodi per has_range
    def set_has_range(self, resource):
        """Aggiunge una risorsa a has_range"""
        self._has_range.append(resource)
    
    def get_has_range(self):
        """Restituisce una copia della lista has_range"""
        return list(set(self._has_range))

    # Metodi per has_domain
    def set_has_domain(self, concept):
        """Aggiunge un concept a has_domain"""
        self._has_domain.append(concept)
    
    def get_has_domain(self):
        """Restituisce una copia della lista has_domain"""
        return list(set(self._has_domain))

