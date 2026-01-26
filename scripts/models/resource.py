class Resource():
    """Rappresenta una Risorsa RDF"""

    def __init__(self):
        # Init Attributes
        self.has_identifier = None 
        self.is_deprecated = False 
        
        # Relations with Literals (0..*)
        self.has_comment = []
        self.has_label = []
        self.has_preferred_label = []
        self.has_alternative_label = []
        self.has_hidden_label = []
        self.has_notation = []
        self.has_note = []
        self.has_change_note = []
        self.has_definition = []
        self.has_editorial_note = []
        self.has_example = []
        self.has_history_note = []
        self.has_scope_note = []
        
        # Relations with Resources (0..*)
        self.see_also = []
        self.is_defined_by = []
        self.has_version_info = []

        # Relation with Concepts (0..*)
        self.has_type = []

        # Relation with Models (1..*)
        self.is_included_in = [] # NEEDS TO BE CHECKED

    def set_has_identifier(self, value):
        """Imposta has_identifier"""
        self.has_identifier = value
    
    def get_has_identifier(self):
        """Restituisce has_identifier"""
        return self.has_identifier

    def set_is_deprecated(self, value):
        """Imposta is_deprecated"""
        self.is_deprecated = value
    
    def get_is_deprecated(self):
        """Restituisce is_deprecated"""
        return self.is_deprecated

    def set_has_comment(self, literal):
        """Aggiunge un literal a has_comment"""
        self.has_comment.append(literal)
    
    def get_has_comment(self):
        """Restituisce una copia della lista has_comment"""
        return list(set(self.has_comment))

    def set_has_label(self, literal):
        """Aggiunge un literal a has_label"""
        self.has_label.append(literal)
    
    def get_has_label(self):
        """Restituisce una copia della lista has_label"""
        return list(set(self.has_label))

    def set_has_preferred_label(self, literal):
        """Aggiunge un literal a has_preferred_label"""
        self.has_preferred_label.append(literal)
    
    def get_has_preferred_label(self):
        """Restituisce una copia della lista has_preferred_label"""
        return list(set(self.has_preferred_label))

    def set_has_alternative_label(self, literal):
        """Aggiunge un literal a has_alternative_label"""
        self.has_alternative_label.append(literal)
    
    def get_has_alternative_label(self):
        """Restituisce una copia della lista has_alternative_label"""
        return list(set(self.has_alternative_label))

    def set_has_hidden_label(self, literal):
        """Aggiunge un literal a has_hidden_label"""
        self.has_hidden_label.append(literal)
    
    def get_has_hidden_label(self):
        """Restituisce una copia della lista has_hidden_label"""
        return list(set(self.has_hidden_label))

    def set_has_notation(self, literal):
        """Aggiunge un literal a has_notation"""
        self.has_notation.append(literal)
    
    def get_has_notation(self):
        """Restituisce una copia della lista has_notation"""
        return list(set(self.has_notation))

    def set_has_note(self, literal):
        """Aggiunge un literal a has_note"""
        self.has_note.append(literal)
    
    def get_has_note(self):
        """Restituisce una copia della lista has_note"""
        return list(set(self.has_note))

    def set_has_change_note(self, literal):
        """Aggiunge un literal a has_change_note"""
        self.has_change_note.append(literal)
    
    def get_has_change_note(self):
        """Restituisce una copia della lista has_change_note"""
        return list(set(self._has_change_note))

    def set_has_definition(self, literal):
        """Aggiunge un literal a has_definition"""
        self.has_definition.append(literal)
    
    def get_has_definition(self):
        """Restituisce una copia della lista has_definition"""
        return list(set(self.has_definition))

    def set_has_editorial_note(self, literal):
        """Aggiunge un literal a has_editorial_note"""
        self.has_editorial_note.append(literal)
    
    def get_has_editorial_note(self):
        """Restituisce una copia della lista has_editorial_note"""
        return list(set(self.has_editorial_note))

    def set_has_example(self, literal):
        """Aggiunge un literal a has_example"""
        self.has_example.append(literal)
    
    def get_has_example(self):
        """Restituisce una copia della lista has_example"""
        return list(set(self.has_example))

    def set_has_history_note(self, literal):
        """Aggiunge un literal a has_history_note"""
        self.has_history_note.append(literal)
    
    def get_has_history_note(self):
        """Restituisce una copia della lista has_history_note"""
        return list(set(self.has_history_note))

    def set_has_scope_note(self, literal):
        """Aggiunge un literal a has_scope_note"""
        self.has_scope_note.append(literal)
    
    def get_has_scope_note(self):
        """Restituisce una copia della lista has_scope_note"""
        return list(set(self.has_scope_note))

    def set_see_also(self, resource):
        """Aggiunge una risorsa a see_also"""
        self.see_also.append(resource)
    
    def get_see_also(self):
        """Restituisce una copia della lista see_also"""
        return list(set(self.see_also))

    def set_is_defined_by(self, resource):
        """Aggiunge una risorsa a is_defined_by"""
        self.is_defined_by.append(resource)
    
    def get_is_defined_by(self):
        """Restituisce una copia della lista is_defined_by"""
        return list(set(self.is_defined_by))

    def set_has_version_info(self, resource):
        """Aggiunge una risorsa a has_version_info"""
        self.has_version_info.append(resource)
    
    def get_has_version_info(self):
        """Restituisce una copia della lista has_version_info"""
        return list(set(self.has_version_info))

    def set_has_type(self, concept):
        """Aggiunge un concept a has_type"""
        self.has_type.append(concept)
    
    def get_has_type(self):
        """Restituisce una copia della lista has_type"""
        return list(set(self.has_type))

    def set_is_included_in(self, model):
        """Aggiunge un model a is_included_in"""
        self.is_included_in.append(model)
    
    def get_is_included_in(self):
        """Restituisce una copia della lista is_included_in"""
        return list(set(self.is_included_in))