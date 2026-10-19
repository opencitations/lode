"""Property: the base class of RDF/OWL properties."""
from .resource import Resource

class Property(Resource):
    """Represents an RDF Property"""

    def __init__(self, **kwargs):
        """Create a property that is not functional, with empty hierarchy, domain and range."""

        super().__init__(**kwargs)
        
        # Attributes
        self.is_functional = False  # bool [1]
        
        # Relations with Properties (0..*)
        self.is_sub_property_of = []
        self.is_super_property_of = []
        self.is_disjoint_with = []
        self.is_equivalent_to = []
        
        # Relation with Resource (1..*) 
        self.has_range = []  
        
        # Relations with Concept (1..*)
        self.has_domain = []  

    # Methods foris_functional
    def set_is_functional(self, bool):
        """Set is_functional."""
        self.is_functional = bool
    
    def get_is_functional(self):
        """Return is_functional."""
        return self.is_functional

    # Methods foris_sub_property_of / is_super_property_of
    def set_is_sub_property_of(self, property_obj):
        """Add a super property to is_sub_property_of and register self as its sub property.

        The inverse link is set only when the target supports it.
        """
        if property_obj not in self.is_sub_property_of:
            self.is_sub_property_of.append(property_obj)
        inv = getattr(property_obj, 'is_super_property_of', None)
        if inv is not None and self not in inv:
            inv.append(self)

    def get_is_sub_property_of(self):
        """Return a copy of is_sub_property_of."""
        return list(self.is_sub_property_of)

    def set_is_super_property_of(self, property_obj):
        """Add a property to is_super_property_of, ignoring duplicates."""
        if property_obj not in self.is_super_property_of:
            self.is_super_property_of.append(property_obj)

    def get_is_super_property_of(self):
        """Return a copy of is_super_property_of."""
        return list(self.is_super_property_of)
    
    # Methods foris_disjoint_with
    def set_is_disjoint_with(self, property_obj):
        """Add a property to is_disjoint_with."""
        self.is_disjoint_with.append(property_obj)
    
    def get_is_disjoint_with(self):
        """Return a de-duplicated copy of is_disjoint_with (order is not preserved)."""
        return list(set(self.is_disjoint_with))

    def set_is_equivalent_to(self, property_obj):
        """Add a property to is_equivalent_to."""
        self.is_equivalent_to.append(property_obj)
    
    def get_is_equivalent_to(self):
        """Return a de-duplicated copy of is_equivalent_to (order is not preserved)."""
        return list(set(self.is_equivalent_to))

    # Methods forhas_range
    def set_has_range(self, resource):
        """Add a resource to has_range, ignoring duplicates."""
        if resource not in self.has_range:
            self.has_range.append(resource)
    
    def get_has_range(self):
        """Return a copy of has_range."""
        return list(self.has_range)

    def set_has_domain(self, concept):
        """Add a concept to has_domain, ignoring duplicates."""
        if concept not in self.has_domain:
            self.has_domain.append(concept)
    
    def get_has_domain(self):
        """Return a copy of has_domain."""
        return list(self.has_domain)

