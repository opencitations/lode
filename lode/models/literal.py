"""Literal: an RDF literal with its value, language and datatype."""
from .resource import Resource

class Literal(Resource):
    """An RDF literal: a lexical value with an optional language tag and datatype."""

    def __init__(self, **kwargs):
        """Create an empty literal: no value, language or datatype."""

        super().__init__(**kwargs)
        
        # Attributes
        self.has_language = None
        self.has_value = None     
        # Relation with Datatypes
        self.has_type = None   

    def set_has_language(self, literal):
        """Set has_language."""
        self.has_language = literal
    
    def get_has_language(self):
        """Return has_language."""
        return self.has_language 

    def set_has_value(self, literal):
        """Set has_value."""
        self.has_value = literal
    
    def get_has_value(self):
        """Return has_value."""
        return self.has_value 
    
    def set_has_type(self, datatype):
        """Set has_type, the datatype of the literal."""
        self.has_type = datatype

    def get_has_type(self):
        """Return has_type, the datatype of the literal."""
        return self.has_type
