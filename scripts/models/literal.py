from .resource import Resource

class Literal(Resource): 

    def __init__(self, **kwargs):
        
        super().__init__(**kwargs)
        
        # Attributes
        self.has_language = None
        self.has_value = None     
        # Relation with Datatypes
        self.has_type = None   

    def set_has_language(self, literal):
        """Imposta has_language"""
        self.has_language = literal
    
    def get_has_language(self):
        """Restituisce has_language"""
        return self.has_language 

    def set_has_value(self, literal):
        """Imposta has_value"""
        self.has_value = literal
    
    def get_has_value(self):
        """Restituisce has_value"""
        return self.has_value 
    
    def set_has_type(self, datatype):
        self.has_type = datatype

    def get_has_type(self):
        return self.has_type
