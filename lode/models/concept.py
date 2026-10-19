"""Concept: an OWL class or SKOS concept, with its hierarchy and matching relations."""
from .resource import Resource

class Concept(Resource):
    """An OWL class or a SKOS concept.

    Holds the relations between concepts (sub/super, disjoint, equivalent, SKOS
    matches) and the inverse links to the properties and individuals that refer to it.
    """

    def __init__(self, **kwargs):
        """Create a concept with every relation list empty."""

        super().__init__(**kwargs)

        # Relations with Concepts
        self.is_sub_concept_of = []   # 0..*
        self.is_super_concept_of = [] # 0..*
        self.is_disjoint_with = []    # 0..*
        self.is_equivalent_to = []    # 0..*
        self.is_related_to = []       # 0..*
        self.has_broad_match = []     # 0..*
        self.has_narrow_match = []    # 0..*
        self.has_related_match = []   # 0..*
        self.has_exact_match = []     # 0..* 
        self.has_close_match = []     # 0..*
        self.has_key = []             # 0..*
        self.individuals_with_this_type = []          # 0..*  (inverse of Individual.has_type)
        self.is_in_domain_of = []     # 0..*


    def set_has_key(self, prop):
        """Add a property to has_key (owl:hasKey)."""
        self.has_key.append(prop)

    def get_has_key(self):
        """Return the has_key list (not a copy)."""
        return self.has_key

    # Setter and getter foris_sub_concept_of
    def set_is_sub_concept_of(self, concept):
        """Add a super concept to is_sub_concept_of and register self as its sub concept.

        The inverse link is set only when the target supports it (a Restriction or
        TruthFunction may not have the attribute).
        """
        if concept not in self.is_sub_concept_of:
            self.is_sub_concept_of.append(concept)
        # inverse: only if the target supports the relation
        inv = getattr(concept, 'is_super_concept_of', None)
        if inv is not None and self not in inv:
            inv.append(self)

    def set_is_super_concept_of(self, concept):
        """Add a concept to is_super_concept_of, ignoring duplicates."""
        if concept not in self.is_super_concept_of:
            self.is_super_concept_of.append(concept)

    def get_is_super_concept_of(self):
        """Return the is_super_concept_of list (not a copy)."""
        return self.is_super_concept_of
    
    def get_is_sub_concept_of(self):
        """Return the is_sub_concept_of list (not a copy)."""
        return self.is_sub_concept_of
    
    # Setter and getter foris_disjoint_with
    def set_is_disjoint_with(self, concept):
        """Add a concept to is_disjoint_with."""
        self.is_disjoint_with.append(concept)
    
    def get_is_disjoint_with(self):
        """Return the is_disjoint_with list (not a copy)."""
        return self.is_disjoint_with
    
    # Setter and getter foris_equivalent_to
    def set_is_equivalent_to(self, concept):
        """Add a concept to is_equivalent_to."""
        self.is_equivalent_to.append(concept)
    
    def get_is_equivalent_to(self):
        """Return the is_equivalent_to list (not a copy)."""
        return self.is_equivalent_to
    
    # Setter and getter foris_related_to
    def set_is_related_to(self, concept):
        """Add a concept to is_related_to."""
        self.is_related_to.append(concept)
    
    def get_is_related_to(self):
        """Return the is_related_to list (not a copy)."""
        return self.is_related_to
    
    # Setter and getter forhas_broad_match
    def set_has_broad_match(self, concept):
        """Add a concept to has_broad_match."""
        self.has_broad_match.append(concept)
    
    def get_has_broad_match(self):
        """Return the has_broad_match list (not a copy)."""
        return self.has_broad_match
    
    # Setter and getter forhas_narrow_match
    def set_has_narrow_match(self, concept):
        """Add a concept to has_narrow_match."""
        self.has_narrow_match.append(concept)
    
    def get_has_narrow_match(self):
        """Return the has_narrow_match list (not a copy)."""
        return self.has_narrow_match
    
    # Setter and getter forhas_related_match
    def set_has_related_match(self, concept):
        """Add a concept to has_related_match."""
        self.has_related_match.append(concept)
    
    def get_has_related_match(self):
        """Return the has_related_match list (not a copy)."""
        return self.has_related_match
    
    # Setter and getter forhas_exact_match
    def set_has_exact_match(self, concept):
        """Add a concept to has_exact_match."""
        self.has_exact_match.append(concept)
    
    def get_has_exact_match(self):
        """Return the has_exact_match list (not a copy)."""
        return self.has_exact_match
    
    # Setter and getter forhas_close_match
    def set_has_close_match(self, concept):
        """Add a concept to has_close_match."""
        self.has_close_match.append(concept)
    
    def get_has_close_match(self):
        """Return the has_close_match list (not a copy)."""
        return self.has_close_match

    def set_individuals_with_this_type(self, individual):
        """Add an individual to individuals_with_this_type (inverse of rdf:type), ignoring duplicates."""
        if individual not in self.individuals_with_this_type:
            self.individuals_with_this_type.append(individual)

    def get_individuals_with_this_type(self):
        """Return a copy of individuals_with_this_type."""
        return list(self.individuals_with_this_type)
    
    def set_is_in_domain_of(self, prop):
        """Add a property to is_in_domain_of, ignoring duplicates."""
        if prop not in self.is_in_domain_of:
            self.is_in_domain_of.append(prop)

    def get_is_in_domain_of(self):
        """Return a copy of is_in_domain_of."""
        return list(self.is_in_domain_of)
    