"""Model: the documented ontology (or vocabulary) itself, with its versions and imports."""
from .resource import Resource

class Model(Resource):
    """An ontology or vocabulary: versioning, compatibility, imports and namespaces."""

    def __init__(self, **kwargs):
        """Create a model with no versions, imports or namespaces."""
        super().__init__(**kwargs)
        self.has_version = []                  # 0..*
        self.is_backward_compatible_with = []  # 0..* 
        self.imports = []                      # 0..*
        self.is_incompatible_with = []         # 0..*
        self.has_top_concept = None            # 0..1
        self.has_prior_version = None          # 0..1
        self.has_namespaces = {}               # 1 (prefix -> URI)

    def get_has_version(self):
        """Return a copy of has_version."""
        return list(self.has_version)
    
    def set_has_version(self, model):
        """Add a model to has_version."""
        self.has_version.append(model)
    
    def get_is_backward_compatible_with(self):
        """Return a copy of is_backward_compatible_with."""
        return list(self.is_backward_compatible_with)
    
    def set_is_backward_compatible_with(self, model):
        """Add a model to is_backward_compatible_with."""
        self.is_backward_compatible_with.append(model)
    
    def get_imports(self):
        """Return a copy of imports."""
        return list(self.imports)
    
    def set_imports(self, model):
        """Add a model to imports."""
        self.imports.append(model)
    
    def get_is_incompatible_with(self):
        """Return a copy of is_incompatible_with."""
        return list(self.is_incompatible_with)
    
    def set_is_incompatible_with(self, model):
        """Add a model to is_incompatible_with."""
        self.is_incompatible_with.append(model)
    
    def get_has_top_concept(self):
        """Return has_top_concept (a single concept, or None)."""
        return self.has_top_concept
    
    def set_has_top_concept(self, concept):
        """Set has_top_concept, replacing any previous value."""
        self.has_top_concept = concept

    def get_has_prior_version(self):
        """Return has_prior_version (a single model, or None)."""
        return self.has_prior_version
    
    def set_has_prior_version(self, model):
        """Set has_prior_version, replacing any previous value."""
        self.has_prior_version = model

    def get_has_namespaces(self):
        """Return a copy of the prefix -> URI dictionary."""
        return dict(self.has_namespaces)

    def set_has_namespaces(self, namespaces: dict):
        """Set the prefix -> URI dictionary of the namespaces."""
        self.has_namespaces = namespaces
    