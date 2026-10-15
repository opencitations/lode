"""Root of the LODE model: the RDF resource every other entity extends."""


class Resource():
    """An RDF resource, with its annotations (labels, notes, ...) and links to other resources.

    Cardinalities are noted next to each field in __init__. Multi-valued fields
    are plain lists filled by the setters; most getters return a copy so callers
    cannot alter the model by accident.
    """

    def __init__(self):
        """Create an empty resource: no identifier, not deprecated, all lists empty."""
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
        self.also_defined_as = []

        # Relation with Concepts (0..*)
        self.has_type = []

        # Relation with Models (1..*)
        self.is_included_in = [] # NEEDS TO BE CHECKED

        # Relation with Resources (0..*)
        self.is_in_range_of = []

    def set_has_identifier(self, value):
        """Set has_identifier."""
        self.has_identifier = value
    
    def get_has_identifier(self):
        """Return has_identifier."""
        return self.has_identifier

    def set_is_deprecated(self, value):
        """Set is_deprecated."""
        self.is_deprecated = value
    
    def get_is_deprecated(self):
        """Return is_deprecated."""
        return self.is_deprecated

    def set_has_comment(self, literal):
        """Add a literal to has_comment."""
        self.has_comment.append(literal)
    
    def get_has_comment(self):
        """Return a de-duplicated copy of has_comment, in insertion order."""
        return list(dict.fromkeys(self.has_comment))

    def set_has_label(self, literal):
        """Add a literal to has_label."""
        self.has_label.append(literal)
    
    def get_has_label(self):
        """Return a de-duplicated copy of has_label, in insertion order."""
        return list(dict.fromkeys(self.has_label))

    def set_has_preferred_label(self, literal):
        """Add a literal to has_preferred_label."""
        self.has_preferred_label.append(literal)
    
    def get_has_preferred_label(self):
        """Return a de-duplicated copy of has_preferred_label, in insertion order."""
        return list(dict.fromkeys(self.has_preferred_label))

    def set_has_alternative_label(self, literal):
        """Add a literal to has_alternative_label."""
        self.has_alternative_label.append(literal)
    
    def get_has_alternative_label(self):
        """Return a de-duplicated copy of has_alternative_label, in insertion order."""
        return list(dict.fromkeys(self.has_alternative_label))

    def set_has_hidden_label(self, literal):
        """Add a literal to has_hidden_label."""
        self.has_hidden_label.append(literal)
    
    def get_has_hidden_label(self):
        """Return a de-duplicated copy of has_hidden_label, in insertion order."""
        return list(dict.fromkeys(self.has_hidden_label))

    def set_has_notation(self, literal):
        """Add a literal to has_notation."""
        self.has_notation.append(literal)
    
    def get_has_notation(self):
        """Return a de-duplicated copy of has_notation, in insertion order."""
        return list(dict.fromkeys(self.has_notation))

    def set_has_note(self, literal):
        """Add a literal to has_note."""
        self.has_note.append(literal)
    
    def get_has_note(self):
        """Return a de-duplicated copy of has_note, in insertion order."""
        return list(dict.fromkeys(self.has_note))

    def set_has_change_note(self, literal):
        """Add a literal to has_change_note."""
        self.has_change_note.append(literal)
    
    def get_has_change_note(self):
        """Return a de-duplicated copy of has_change_note, in insertion order."""
        return list(dict.fromkeys(self.has_change_note))

    def set_has_definition(self, literal):
        """Add a literal to has_definition."""
        self.has_definition.append(literal)
    
    def get_has_definition(self):
        """Return a de-duplicated copy of has_definition, in insertion order."""
        return list(dict.fromkeys(self.has_definition))

    def set_has_editorial_note(self, literal):
        """Add a literal to has_editorial_note."""
        self.has_editorial_note.append(literal)
    
    def get_has_editorial_note(self):
        """Return a de-duplicated copy of has_editorial_note, in insertion order."""
        return list(dict.fromkeys(self.has_editorial_note))

    def set_has_example(self, literal):
        """Add a literal to has_example."""
        self.has_example.append(literal)
    
    def get_has_example(self):
        """Return a de-duplicated copy of has_example, in insertion order."""
        return list(dict.fromkeys(self.has_example))

    def set_has_history_note(self, literal):
        """Add a literal to has_history_note."""
        self.has_history_note.append(literal)
    
    def get_has_history_note(self):
        """Return a de-duplicated copy of has_history_note, in insertion order."""
        return list(dict.fromkeys(self.has_history_note))

    def set_has_scope_note(self, literal):
        """Add a literal to has_scope_note."""
        self.has_scope_note.append(literal)
    
    def get_has_scope_note(self):
        """Return a de-duplicated copy of has_scope_note, in insertion order."""
        return list(dict.fromkeys(self.has_scope_note))

    def set_see_also(self, resource):
        """Add a resource to see_also."""
        self.see_also.append(resource)
    
    def get_see_also(self):
        """Return a de-duplicated copy of see_also, in insertion order."""
        return list(dict.fromkeys(self.see_also))

    def set_is_defined_by(self, resource):
        """Add a resource to is_defined_by."""
        self.is_defined_by.append(resource)
    
    def get_is_defined_by(self):
        """Return a de-duplicated copy of is_defined_by, in insertion order."""
        return list(dict.fromkeys(self.is_defined_by))

    def set_has_version_info(self, resource):
        """Add a resource to has_version_info."""
        self.has_version_info.append(resource)
    
    def get_has_version_info(self):
        """Return a de-duplicated copy of has_version_info, in insertion order."""
        return list(dict.fromkeys(self.has_version_info))

    def set_has_type(self, concept):
        """Add a concept to has_type, ignoring duplicates."""
        if concept not in self.has_type:
            self.has_type.append(concept)

    def get_has_type(self):
        """Return a copy of has_type."""
        return list(self.has_type)

    def set_is_included_in(self, model):
        """Add a model to is_included_in."""
        self.is_included_in.append(model)
    
    def get_is_included_in(self):
        """Return a de-duplicated copy of is_included_in, in insertion order."""
        return list(dict.fromkeys(self.is_included_in))
    
    def get_also_defined_as(self):
        """Return a copy of also_defined_as."""
        return list(self.also_defined_as)
    
    def set_also_defined_as(self, resource):
        """Add a resource to also_defined_as."""
        self.also_defined_as.append(resource)

    def set_is_in_range_of(self, prop):
        """Add a property to is_in_range_of, ignoring duplicates."""
        if prop not in self.is_in_range_of:
            self.is_in_range_of.append(prop)

    def get_is_in_range_of(self):
        """Return a copy of is_in_range_of."""
        return list(self.is_in_range_of)