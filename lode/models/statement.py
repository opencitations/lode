"""Statement: a reified RDF triple."""
from .resource import Resource

class Statement(Resource):
    """An RDF triple (subject, predicate, object) described as a resource, so it can be documented."""

    def __init__(self, **kwargs):
        """Create a positive statement with no subject, predicate or object."""
        super().__init__(**kwargs)

        self.is_positive_statement = True # bool [1]
        self.has_subject = None # Resource [1]
        self.has_object = None # Resource [1]
        self.has_predicate = None # Property [1]
        
    # Attributes
    def get_is_positive_statement(self):
        """Return is_positive_statement."""
        return self.is_positive_statement
    
    def set_is_positive_statement(self, statement):
        """Set is_positive_statement."""
        self.is_positive_statement = statement

    # Relations with Resource
    def get_has_subject(self):
        """Return has_subject."""
        return self.has_subject
    
    def set_has_subject(self, statement):
        """Set has_subject."""
        self.has_subject = statement

    def get_has_object(self):
        """Return has_object."""
        return self.has_object
    
    def set_has_object(self, statement):
        """Set has_object."""
        self.has_object = statement

    # Relation with Property
    def get_has_predicate(self):
        """Return has_predicate."""
        return self.has_predicate
    
    def set_has_predicate(self, statement):
        """Set has_predicate."""
        self.has_predicate = statement
