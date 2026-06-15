from .resource import Resource

class Concept(Resource):

    def __init__(self, **kwargs):

        super().__init__(**kwargs)

        # Relations with Concepts
        self.is_sub_concept_of = []   # 0..*
        self.is_disjoint_with = []    # 0..*
        self.is_equivalent_to = []    # 0..*
        self.is_related_to = []       # 0..*
        self.has_broad_match = []     # 0..*
        self.has_narrow_match = []    # 0..*
        self.has_related_match = []   # 0..*
        self.has_exact_match = []     # 0..* 
        self.has_close_match = []     # 0..*
        self.has_key = []             # 0..*
        self.individuals_with_this_type = []          # 0..*  (inverso di Individual.has_type)


    def set_has_key(self, prop):
        self.has_key.append(prop)

    def get_has_key(self):
        return self.has_key

    # Setter e Getter per is_sub_concept_of
    def set_is_sub_concept_of(self, concept):
        """Aggiunge un Concept a is_sub_concept_of"""
        self.is_sub_concept_of.append(concept)
    
    def get_is_sub_concept_of(self):
        """Restituisce la lista is_sub_concept_of"""
        return self.is_sub_concept_of
    
    # Setter e Getter per is_disjoint_with
    def set_is_disjoint_with(self, concept):
        """Aggiunge un Concept a is_disjoint_with"""
        self.is_disjoint_with.append(concept)
    
    def get_is_disjoint_with(self):
        """Restituisce la lista is_disjoint_with"""
        return self.is_disjoint_with
    
    # Setter e Getter per is_equivalent_to
    def set_is_equivalent_to(self, concept):
        """Aggiunge un Concept a is_equivalent_to"""
        self.is_equivalent_to.append(concept)
    
    def get_is_equivalent_to(self):
        """Restituisce la lista is_equivalent_to"""
        return self.is_equivalent_to
    
    # Setter e Getter per is_related_to
    def set_is_related_to(self, concept):
        """Aggiunge un Concept a is_related_to"""
        self.is_related_to.append(concept)
    
    def get_is_related_to(self):
        """Restituisce la lista is_related_to"""
        return self.is_related_to
    
    # Setter e Getter per has_broad_match
    def set_has_broad_match(self, concept):
        """Aggiunge un Concept a has_broad_match"""
        self.has_broad_match.append(concept)
    
    def get_has_broad_match(self):
        """Restituisce la lista has_broad_match"""
        return self.has_broad_match
    
    # Setter e Getter per has_narrow_match
    def set_has_narrow_match(self, concept):
        """Aggiunge un Concept a has_narrow_match"""
        self.has_narrow_match.append(concept)
    
    def get_has_narrow_match(self):
        """Restituisce la lista has_narrow_match"""
        return self.has_narrow_match
    
    # Setter e Getter per has_related_match
    def set_has_related_match(self, concept):
        """Aggiunge un Concept a has_related_match"""
        self.has_related_match.append(concept)
    
    def get_has_related_match(self):
        """Restituisce la lista has_related_match"""
        return self.has_related_match
    
    # Setter e Getter per has_exact_match
    def set_has_exact_match(self, concept):
        """Aggiunge un Concept a has_exact_match"""
        self.has_exact_match.append(concept)
    
    def get_has_exact_match(self):
        """Restituisce la lista has_exact_match"""
        return self.has_exact_match
    
    # Setter e Getter per has_close_match
    def set_has_close_match(self, concept):
        """Aggiunge un Concept a has_close_match"""
        self.has_close_match.append(concept)
    
    def get_has_close_match(self):
        """Restituisce la lista has_close_match"""
        return self.has_close_match

    def set_individuals_with_this_type(self, individual):
        """Aggiunge un Individual a individuals_with_this_type (inverso di rdf:type)."""
        if individual not in self.individuals_with_this_type:
            self.individuals_with_this_type.append(individual)

    def get_individuals_with_this_type(self):
        """Restituisce la lista individuals_with_this_type."""
        return list(self.individuals_with_this_type)
    