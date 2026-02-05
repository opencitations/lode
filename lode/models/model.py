from .resource import Resource

class Model(Resource):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.has_version = []                  # 0..*
        self.is_backward_compatible_with = []  # 0..* 
        self.imports = []                      # 0..*
        self.is_incompatible_with = []         # 0..*
        self.has_top_concept = []              # 0..1
        self.has_prior_version = None          # 0..1

    def get_has_version(self):
        """Restituisce la lista has_version"""
        return list(self.has_version)
    
    def set_has_version(self, model):
        """Aggiunge un Model a has_version """
        self.has_version.append(model)
    
    def get_is_backward_compatible_with(self):
        """Restituisce la lista is_backward_compatible_with"""
        return list(self.is_backward_compatible_with)
    
    def set_is_backward_compatible_with(self, model):
        """Aggiunge un Model a is_backward_compatible_with"""
        self.is_backward_compatible_with.append(model)
    
    def get_imports(self):
        """Restituisce la lista imports"""
        return list(self.imports)
    
    def set_imports(self, model):
        """Aggiunge un Model a imports"""
        self.imports.append(model)
    
    def get_is_incompatible_with(self):
        """Restituisce la lista is_incompatible_with"""
        return list(self.is_incompatible_with)
    
    def set_is_incompatible_with(self, model):
        """Aggiunge un Model a is_incompatible_with"""
        self.is_incompatible_with.append(model)
    
    def get_has_top_concept(self):
        """Restituisce la lista has_top_concept"""
        return self.has_top_concept
    
    def set_has_top_concept(self, concept):
        """Aggiunge un Concept a has_top_concept"""
        self.has_top_concept = concept

    def get_has_prior_version(self):
        """Restituisce la lista has_prior_version"""
        return self.has_prior_version
    
    def set_has_prior_version(self, model):
        """Aggiunge un Model a has_prior_version"""
        self.has_prior_version = model

