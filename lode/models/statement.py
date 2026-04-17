from .resource import Resource

class Statement(Resource):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.is_positive_statement = True # bool [1]
        self.has_subject = None # Resource [1]
        self.has_object = None # Resource [1]
        self.has_predicate = None # Property [1]
        
    # Attributes
    def get_is_positive_statement(self):
        """Restituisce il valore is_positive_statement [1]"""
        return self.is_positive_statement
    
    def set_is_positive_statement(self, statement):
        """Setta il valore di a is_positive_statement [1]"""
        self.is_positive_statement = statement

    # Relations with Resource
    def get_has_subject(self):
        """Restituisce il valore has_subject [1]"""
        return self.has_subject
    
    def set_has_subject(self, statement):
        """Setta il valore di a has_subject [1]"""
        self.has_subject = statement

    def get_has_object(self):
        """Restituisce il valore has_object [1]"""
        return self.has_object
    
    def set_has_object(self, statement):
        """Setta il valore di a has_object [1]"""
        self.has_object = statement

    # Relation with Property
    def get_has_predicate(self):
        """Restituisce il valore has_predicate [1]"""
        return self.has_predicate
    
    def set_has_predicate(self, statement):
        """Setta il valore di a has_predicate [1]"""
        self.has_predicate = statement
