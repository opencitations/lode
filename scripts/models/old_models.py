# reader/Models.py

# UTILS

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
    
class Property(Resource):
    """Represents an RDF Property"""

    def __init__(self, **kwargs):
        
        super().__init__(**kwargs)
        
        # Attributes
        self.is_functional = False  # bool [1]
        
        # Relations with Properties (0..*)
        self._is_sub_property_of = []
        self._is_disjoint_with = []
        self._is_equivalent_to = []
        
        # Relation with Resource (1..*) 
        # Nell'extractor - default per OWL ontologies = OWL.Thing
        self._has_range = []  
        
        # Relations with Concept (1..*)
        # Nell'extractor - default per OWL ontologies = OWL.Thing
        self._has_domain = []  

    # Metodi per is_functional
    def set_is_functional(self, bool):
        """Imposta is_functional"""
        self.is_functional = bool
    
    def get_is_functional(self):
        """Restituisce is_functional"""
        return self.is_functional

    # Metodi per is_sub_property_of
    def set_is_sub_property_of(self, property_obj):
        """Aggiunge una property a is_sub_property_of"""
        self._is_sub_property_of.append(property_obj)
    
    def get_is_sub_property_of(self):
        """Restituisce una copia della lista is_sub_property_of"""
        return list(set(self._is_sub_property_of))

    # Metodi per is_disjoint_with
    def set_is_disjoint_with(self, property_obj):
        """Aggiunge una property a is_disjoint_with"""
        self._is_disjoint_with.append(property_obj)
    
    def get_is_disjoint_with(self):
        """Restituisce una copia della lista is_disjoint_with"""
        return list(set(self._is_disjoint_with))

    # Metodi per is_equivalent_to
    def set_is_equivalent_to(self, property_obj):
        """Aggiunge una property a is_equivalent_to"""
        self._is_equivalent_to.append(property_obj)
    
    def get_is_equivalent_to(self):
        """Restituisce una copia della lista is_equivalent_to"""
        return list(set(self._is_equivalent_to))

    # Metodi per has_range
    def set_has_range(self, resource):
        """Aggiunge una risorsa a has_range"""
        self._has_range.append(resource)
    
    def get_has_range(self):
        """Restituisce una copia della lista has_range"""
        return list(set(self._has_range))

    # Metodi per has_domain
    def set_has_domain(self, concept):
        """Aggiunge un concept a has_domain"""
        self._has_domain.append(concept)
    
    def get_has_domain(self):
        """Restituisce una copia della lista has_domain"""
        return list(set(self._has_domain))


class Relation(Property):
    """Rappresenta una Object Property RDF"""

    def __init__(self, **kwargs):
        # Chiama il costruttore della classe padre
        super().__init__(**kwargs)
        
        # Attributes
        self.is_asymmetric = False  # [1]
        self.is_inverse_functional = False  # [1]
        self.is_irreflexive = False  # [1]
        self.is_reflexive = False  # [1]
        self.is_symmetric = False  # [1]
        self.is_transitive = False  # [1]
        
        # Relations with Relations
        self.is_inverse_of = None  # 0..1 Relation
        self._has_property_chain = []  # 1..*

        # Relation with Concept
        self.has_range = [] # 1..*

    # Metodi per is_asymmetric
    def set_is_asymmetric(self, value):
        """Imposta is_asymmetric"""
        self.is_asymmetric = value
    
    def get_is_asymmetric(self):
        """Restituisce is_asymmetric"""
        return self.is_asymmetric

    # Metodi per is_inverse_functional
    def set_is_inverse_functional(self, value):
        """Imposta is_inverse_functional"""
        self.is_inverse_functional = value
    
    def get_is_inverse_functional(self):
        """Restituisce is_inverse_functional"""
        return self.is_inverse_functional

    # Metodi per is_irreflexive
    def set_is_irreflexive(self, value):
        """Imposta is_irreflexive"""
        self.is_irreflexive = value
    
    def get_is_irreflexive(self):
        """Restituisce is_irreflexive"""
        return self.is_irreflexive

    # Metodi per is_reflexive
    def set_is_reflexive(self, value):
        """Imposta is_reflexive"""
        self.is_reflexive = value
    
    def get_is_reflexive(self):
        """Restituisce is_reflexive"""
        return self.is_reflexive

    # Metodi per is_symmetric
    def set_is_symmetric(self, value):
        """Imposta is_symmetric"""
        self.is_symmetric = value
    
    def get_is_symmetric(self):
        """Restituisce is_symmetric"""
        return self.is_symmetric

    # Metodi per is_transitive
    def set_is_transitive(self, value):
        """Imposta is_transitive"""
        self.is_transitive = value
    
    def get_is_transitive(self):
        """Restituisce is_transitive"""
        return self.is_transitive

    # Metodi per is_inverse_of (0..1 - singolo valore)
    def set_is_inverse_of(self, relation):
        """Imposta is_inverse_of"""
        self.is_inverse_of = relation
    
    def get_is_inverse_of(self):
        """Restituisce is_inverse_of"""
        return self.is_inverse_of

    # Metodi per has_property_chain
    def set_has_property_chain(self, relation):
        """Aggiunge una relation a has_property_chain"""
        self._has_property_chain.append(relation)
    
    def get_has_property_chain(self):
        """Restituisce una copia della lista has_property_chain"""
        return list(set(self._has_property_chain))
    
    # def set_has_range(self, concept):
    #     """Imposta has_range"""
    #     self.has_range = concept
    
    # def get_has_range(self):
    #     """Restituisce has_range"""
    #     return list(self.has_range)
    

class Annotation(Property):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class Attribute(Property):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Relation with Literal
        self.has_range = [] # GIà definita in parent class, card 1..*
        self.has_type = [] # [1..*]

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
    
class Datatype(Concept):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class Restriction(Concept):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.applies_on_concept = [] # 1..*

    def get_applies_on_concept(self):
        """Restituisce la lista applies on concept"""
        return list(self.applies_on_concept)
        
    def set_applies_on_concept(self, concept):
        """Aggiunge un Concept a applies_on_concept """
        self.applies_on_concept.append(concept)


class TruthFunction(Restriction):

    # the has_cardinality_type can have one of three values: "max", "min", and "exact". Any other string will be interpreted as "exact".
    # fallback = exact
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.has_logical_operator = None # string[1]

    def get_has_logical_operator(self):
        """Restituisce la stringa per has_logical_operator"""
        return self.has_logical_operator
        
    def set_has_logical_operator(self, literal):
        """Aggiunge una str a as_logical_operator"""
        self.has_logical_operator = literal

class OneOf(Restriction):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.applies_on_resource = [] # 1..*

    def get_applies_on_resource(self):
        """Restituisce la lista applies on resource"""
        return list(self.applies_on_resource)
        
    def set_applies_on_resource(self, resource):
        """Aggiunge un Resource a applies_on_resource """
        self.applies_on_resource.append(resource)

class PropertyConceptRestriction(Restriction):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.applies_on_property = None # 1
        self.applies_on_concept = None # 1

    def get_applies_on_property(self):
        """Restituisce il valore applies on property"""
        return self.applies_on_property
        
    def set_applies_on_property(self, property):
        """Aggiunge un Property a applies_on_property """
        self.applies_on_property = property

    def get_applies_on_concept(self):
        """Restituisce la lista applies on concept"""
        return self.applies_on_concept
        
    def set_applies_on_concept(self, concept):
        """Aggiunge un Concept a applies_on_concept """
        self.applies_on_concept = concept

class Value(PropertyConceptRestriction):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.applies_on_resource = None # 1

    def get_applies_on_resource(self):
        """Restituisce la lista applies on resource"""
        return self.applies_on_resource
        
    def set_applies_on_resource(self, resource):
        """Aggiunge un Resource a applies_on_resource """
        self.applies_on_resource = resource

class Quantifier(PropertyConceptRestriction):
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.has_quantifier_type = None # str[1]
    
    def get_has_quantifier_type(self):
        """Restituisce il valore has_quantifier_type"""
        return self.has_quantifier_type
        
    def set_has_quantifier_type(self, string):
        """Aggiunge una string a has_quantifier_type"""
        self.has_quantifier_type = string


class Cardinality(PropertyConceptRestriction):
            
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.has_cardinality = None # int[1]
        self.has_cardinality_type  = None # str[1]

    def get_has_cardinality(self):
        """Restituisce il valore has_cardinality"""
        return self.has_cardinality
        
    def set_has_cardinality(self, var):
        """Aggiunge un integer a has_cardinality"""
        self.has_cardinality = int(var)
    
    def get_has_cardinality_type(self):
        """Restituisce il valore has_cardinality_type"""
        return self.has_cardinality_type
        
    def set_has_cardinality_type(self, string):
        """Aggiunge una string a has_cardinality_type"""
        self.has_cardinality_type = string


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

class Individual(Resource):
    """
    Rappresenta un'istanza individuale di una classe (owl:NamedIndividual).
    Estende Resource con relazioni specifiche per individui OWL.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Relations with Individual
        self.is_same_as = []         # 0..*
        self.is_different_from = []  # 0..*
        # Relations with Concept (ereditato ma qui esplicitato, perchè cambia la cardinalità)
        self.has_type = []  # 1..* 

    def get_has_type(self):
        return list(self.has_type)
    
    def set_has_type(self, concept):
        self.has_type.append(concept)
    
    def get_is_same_as(self):
        """Restituisce la lista is_same_as [0..*]"""
        return list(self.is_same_as)
    
    def set_is_same_as(self, individual):
        """Aggiunge un Individual a is_same_as [0..*]"""
        self.is_same_as.append(individual)
    
    def get_is_different_from(self):
        """Restituisce la lista is_different_from [0..*]"""
        return list(self.is_different_from)
    
    def set_is_different_from(self, individual):
        """Aggiunge un Individual a is_different_from [0..*]"""
        self.is_different_from.append(individual)

class Statement(Resource):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.is_positive_statement = None #[1]
        self.has_subject = None #[1]
        self.has_object = None #[1]
        self.has_predicate = None #[1]
        
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

class Container(Resource):
    """RDF Container (Bag, Seq, Alt, List)"""
    
    def __init__(self):
        super().__init__()
        self._members = []
    
    def set_has_member(self, member):
        """Aggiunge un singolo membro"""
        if member not in self._members:
            self._members.append(member)
    
    def set_has_members(self, members: list):
        """Imposta tutti i membri in una volta"""
        self._members = members.copy()
    
    def get_has_members(self):
        """Ritorna la lista dei membri"""
        return self._members.copy()


class Collection(Resource):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.is_ordered= False # bool[1]
        self.has_member= [] # [0..*]

    def get_is_ordered(self):
        """Restituisce il valore is_ordered bool[1]"""
        return self.is_ordered
    
    def set_is_ordered(self, bool):
        """Setta il valore di is_ordered bool [1]"""
        self.is_ordered = bool

    def get_has_member(self):
        """Restituisce il valore has_member [0..*]"""
        return list(self.has_member)
    
    def set_has_member(self, concept_or_collection):
        """Setta il valore di has_member [0..*]"""
        self.has_member.append(concept_or_collection)
    