from rdflib import Graph, URIRef, Node, Literal as RDFlibLiteral, BNode
from rdflib.namespace import RDF, RDFS, OWL, SKOS
from .models import *
from rdflib.collection import Collection as RDFLibCollection


class BaseSemanticFactory():
    """Factory base con logica comune per tutte le interpretazioni"""
    
    def __init__(self, graph: Graph, instance_cache: dict = None):
        self.graph = graph
        self._instance_cache = instance_cache if instance_cache is not None else {}  # cache of the instance

    # utility to decide if to be reused by cache, created and populated on the fly
    def get_or_create(self, id: Node, python_class: type):
        """Get instance from cache or create and populate new one"""
        
        try:
            # Handle literals
            if isinstance(id, RDFlibLiteral):
                return self._create_literal(id)
            
            # Check cache
            if id in self._instance_cache:
                # Per i BNode, ritorna la PRIMA istanza disponibile
                # (ignora il python_class richiesto)
                if isinstance(id, BNode):
                    return next(iter(self._instance_cache[id]))
                
                # Per URIRef, cerca il tipo specifico
                if isinstance(id, URIRef):
                    for obj in self._instance_cache[id]:
                        if isinstance(obj, python_class):
                            return obj
            
            # Create and cache
            instance = python_class()
            if id not in self._instance_cache:
                self._instance_cache[id] = set()
            self._instance_cache[id].add(instance)
            
            # Populate using existing dispatcher
            self.populate_instance(instance, id)
            return instance
            
        except Exception as e:
            print(f"Cannot create {python_class.__name__} for {id}: {e}")
            return None        
    
    def populate_instance(self, instance, uri: Node):
        """Dispatcher: popola istanza in base al tipo"""
        
        # L'ORDINE E' IMPORTANTE
        type_map = {
            Relation: self.populate_relation,     
            Attribute: self.populate_attribute,
            Annotation: self.populate_annotation,
            Datatype: self.populate_datatype,
            Quantifier: self.populate_quantifier,
            Cardinality: self.populate_cardinality,
            OneOf: self.populate_one_of,
            TruthFunction: self.populate_truth_function,
            Value: self.populate_value,
            PropertyConceptRestriction: self.populate_property_concept_restriction,
            Restriction: self.populate_restriction,
            Concept: self.populate_concept,
            Property: self.populate_property,
            Model: self.populate_model,
            Resource: self.populate_resource,
            Individual: self.populate_literals
        }
        
        # Trova il primo match nella gerarchia
        for cls, method in type_map.items():
            if isinstance(instance, cls):
                method(instance, uri)
                return
        
    
    
    # ========== GESTIONE CACHE ==========
    
    # def _get_or_create_instance(self, uri: Node, instance_type: type):
    #     """Pattern cache: restituisce da cache o crea nuova istanza VUOTA (per mapper)"""
    #     if isinstance(uri, RDFlibLiteral):
    #         return self._create_literal(uri)
        
    #     uri = str(uri)
    #     if uri in self._instance_cache:
    #         return self._instance_cache[uri]
        
    #     instance = instance_type()
    #     self._instance_cache[uri] = instance
    #     return instance
    
    def clear_cache(self):
        self._instance_cache.clear()

    def create_empty_instance(self, id: Node, python_class: type):
        """Create empty objects and maps them in cache"""
        
        try:
            if isinstance(id, RDFlibLiteral):
                return self._create_literal(id)
            
            # Usa direttamente id (URIRef/BNode) come chiave, non str(id)
            if id not in self._instance_cache:
                self._instance_cache[id] = set()
            
            # Crea la nuova istanza
            instance = python_class()
            
            # SOLO PER FAR FUNZIONARE LE RESTRICTIONS, MA DA TOGLIERE!!
            instance.has_identifier = str(id)
            
            # Aggiunge l'istanza al set
            self._instance_cache[id].add(instance)
            
            # Restituisce l'istanza appena creata
            return instance
            
        except Exception as e:
            print(f"Warning: impossible create instance for {id}: {e}")
            return None
    
    # ========== METODI DI POPOLAMENTO INTERNI ==========
    
    def populate_resource(self, resource: Resource, uri: Node):
        """Popola base Resource"""
        if isinstance(uri, RDFlibLiteral) or not isinstance(uri, URIRef):
            return
        
        # Attributi semplici
        resource.set_has_identifier(str(uri))
        resource.set_is_deprecated(
            self.graph.value(uri, OWL.deprecated) == RDFlibLiteral(True)
        )
        
        # Relazioni a Literal
        self.populate_literals(resource, uri, RDFS.label, resource.set_has_label)
        self.populate_literals(resource, uri, RDFS.comment, resource.set_has_comment)
        self.populate_literals(resource, uri, SKOS.prefLabel, resource.set_has_preferred_label)
        self.populate_literals(resource, uri, SKOS.altLabel, resource.set_has_alternative_label)
        self.populate_literals(resource, uri, SKOS.hiddenLabel, resource.set_has_hidden_label)
        self.populate_literals(resource, uri, SKOS.definition, resource.set_has_definition)
        self.populate_literals(resource, uri, SKOS.example, resource.set_has_example)
        self.populate_literals(resource, uri, SKOS.note, resource.set_has_note)
        self.populate_literals(resource, uri, SKOS.scopeNote, resource.set_has_scope_note)
        self.populate_literals(resource, uri, SKOS.historyNote, resource.set_has_history_note)
        self.populate_literals(resource, uri, SKOS.editorialNote, resource.set_has_editorial_note)
        self.populate_literals(resource, uri, SKOS.changeNote, resource.set_has_change_note)
        self.populate_literals(resource, uri, SKOS.notation, resource.set_has_notation)
        
        # Relazioni a Resource
        for see_also in self.graph.objects(uri, RDFS.seeAlso):
            res_obj = self.get_or_create(see_also, Resource)
            resource.set_see_also(res_obj)
        
        version_info = self.graph.value(uri, OWL.versionInfo)
        if version_info:
            res_obj = self.get_or_create(version_info, Resource)
            resource.set_has_version_info(res_obj)
        
        # Relazioni a Concept (rdf:type)
        # for type_val in self.graph.objects(uri, RDF.type):
        #     conc_obj = self.get_or_create(type_val, Concept)
        #     resource.set_has_type(conc_obj)
    
    def populate_literals(self, resource, uri, predicate, setter_method):
        """Popola attributi letterali, gestisce valori malformati"""
        for value in self.graph.objects(uri, predicate):
            try:
                lit_obj = self._create_literal(value)
                setter_method(lit_obj)
            except AttributeError:
                # Skip URIRef o altri valori non-Literal malformati
                continue
            except Exception as e:
                # Log altri errori ma continua
                print(f"Warning: impossibile creare literal da {value}: {e}")
                continue
    
    def populate_property(self, prop: Property, uri: URIRef):
        """Popola Property (estende Resource)"""
        self.populate_resource(prop, uri)
        
        prop.set_is_functional(
            bool((uri, RDF.type, OWL.FunctionalProperty) in self.graph)
        )
        
        # Domain
        for domain in self.graph.objects(uri, RDFS.domain):
            conc_obj = self.get_or_create(domain, Concept)
            prop.set_has_domain(conc_obj)
        
        # Range
        for range_val in self.graph.objects(uri, RDFS.range):
            res_obj = self.get_or_create(range_val, Resource)
            prop.set_has_range(res_obj)
        
        # SubProperty
        for sub_prop in self.graph.objects(uri, RDFS.subPropertyOf):
            prop_obj = self.get_or_create(sub_prop, Property)
            prop.set_is_sub_property_of(prop_obj)
        
        # Disjoint/Equivalent
        for disjoint in self.graph.objects(uri, OWL.propertyDisjointWith):
            prop_obj = self.get_or_create(disjoint, Property)
            prop.set_is_disjoint_with(prop_obj)
        
        for equivalent in self.graph.objects(uri, OWL.equivalentProperty):
            prop_obj = self.get_or_create(equivalent, Property)
            prop.set_is_equivalent_to(prop_obj)
    
    def populate_relation(self, relation: Relation, uri: URIRef):
        """Popola Relation (estende Property)"""
        self.populate_property(relation, uri)
        
        relation.set_is_symmetric(bool((uri, RDF.type, OWL.SymmetricProperty) in self.graph))
        relation.set_is_transitive(bool((uri, RDF.type, OWL.TransitiveProperty) in self.graph))
        relation.set_is_reflexive(bool((uri, RDF.type, OWL.ReflexiveProperty) in self.graph))
        relation.set_is_irreflexive(bool((uri, RDF.type, OWL.IrreflexiveProperty) in self.graph))
        relation.set_is_asymmetric(bool((uri, RDF.type, OWL.AsymmetricProperty) in self.graph))
        relation.set_is_inverse_functional(bool((uri, RDF.type, OWL.InverseFunctionalProperty) in self.graph))
        
        # InverseOf
        inverse = self.graph.value(uri, OWL.inverseOf)
        if inverse:
            rel_obj = self.get_or_create(inverse, Relation)
            relation.set_is_inverse_of(rel_obj)

        # PropertyChains handled with Python list of sets
        prop_chain_list = []

        for collection in self.graph.objects(uri, OWL.propertyChainAxiom):
            chain = list(RDFLibCollection(self.graph, collection))
            prop_chain_list.append(chain)

        relation.set_has_property_chain(prop_chain_list)
        print('DEBUGGGG', prop_chain_list)

    def populate_annotation(self, annotation: Annotation, uri: URIRef):
        """Popola Annotation (estende Property)"""
        self.populate_property(annotation, uri)

    def populate_property_concept_restriction(self, prop_conc_rest: PropertyConceptRestriction, uri: BNode):
        """Popola Property Concept Restriction (extends Restriction)"""
        self.populate_restriction(prop_conc_rest, uri)

    def populate_quantifier(self, quant: Quantifier, id: BNode):
        """Popola Quantifier (estende Restriction)"""
        self.populate_property_concept_restriction(quant, id)    

    def populate_cardinality(self, card: Cardinality, id: BNode):
        """Popola Cardinality (estende PropertyConceptRestriction)"""
        self.populate_property_concept_restriction(card, id)  

    def populate_one_of(self, one_of: OneOf, id: BNode):
        """Popola OneOf (estende Restriction)"""
        self.populate_restriction(one_of, id)  

    def populate_truth_function(self, tf: TruthFunction, id: BNode):
        """Popola TruthFunction (estende Restriction)"""
        self.populate_restriction(tf, id)  

    def populate_value(self, val: Value, id: BNode):
        """Popola Value (estende PropertyConceptRestriction)"""
        self.populate_property_concept_restriction(val, id)  
    
    def populate_attribute(self, attribute: Attribute, uri: URIRef):
        """Popola Attribute (estende Property)"""
        self.populate_property(attribute, uri)

        for range_val in self.graph.objects(uri, RDFS.range):
            datatype_obj = self.get_or_create(range_val, Datatype)
            attribute.set_has_range(datatype_obj)
    
    def populate_concept(self, concept: Concept, uri: URIRef):
        """Popola Concept (estende Resource)"""
        self.populate_resource(concept, uri)
        
        # Gerarchie
        for broader in self.graph.objects(uri, RDFS.subClassOf):
            concept_obj = self.get_or_create(broader, Concept)
            concept.set_is_sub_concept_of(concept_obj)
        
        for broader in self.graph.objects(uri, SKOS.broader):
            concept_obj = self.get_or_create(broader, Concept)
            concept.set_is_sub_concept_of(concept_obj)
        
        # Logiche
        for disjoint in self.graph.objects(uri, OWL.disjointWith):
            concept_obj = self.get_or_create(disjoint, Concept)
            concept.set_is_disjoint_with(concept_obj)
        
        for equivalent in self.graph.objects(uri, OWL.equivalentClass):
            concept_obj = self.get_or_create(equivalent, Concept)
            concept.set_is_equivalent_to(concept_obj)
        
        # SKOS
        for related in self.graph.objects(uri, SKOS.related):
            concept_obj = self.get_or_create(related, Concept)
            concept.set_is_related_to(concept_obj)
        
        self.populate_skos_matches(concept, uri)

    def populate_model(self, model: Model, uri: URIRef):
        """Popola Model (estende Resource)"""
        self.populate_resource(model, uri)
        
        # has_version [0..*]
        for version in self.graph.objects(uri, OWL.versionIRI):
            model_obj = self.get_or_create(version, Model)
            model.set_has_version(model_obj)
        
        # is_backward_compatible_with [0..*]
        for compatible in self.graph.objects(uri, OWL.backwardCompatibleWith):
            model_obj = self.get_or_create(compatible, Model)
            model.set_is_backward_compatible_with(model_obj)
        
        # imports [0..*]
        for imported in self.graph.objects(uri, OWL.imports):
            model_obj = self.get_or_create(imported, Model)
            model.set_imports(model_obj)
        
        # is_incompatible_with [0..*]
        for incompatible in self.graph.objects(uri, OWL.incompatibleWith):
            model_obj = self.get_or_create(incompatible, Model)
            model.set_is_incompatible_with(model_obj)
        
        # has_prior_version [0..1]
        prior_version = self.graph.value(uri, OWL.priorVersion)
        if prior_version:
            model_obj = self.get_or_create(prior_version, Model)
            model.set_has_prior_version(model_obj)
        
        # has_top_concept [0..*]
        for top_concept in self.graph.objects(uri, SKOS.hasTopConcept):
            concept_obj = self.get_or_create(top_concept, Concept)
            model.set_has_top_concept(concept_obj)
    
    def populate_skos_matches(self, concept: Concept, uri: URIRef):
        """Helper per relazioni SKOS match"""
        match_mappings = [
            (SKOS.broadMatch, concept.set_has_broad_match),
            (SKOS.narrowMatch, concept.set_has_narrow_match),
            (SKOS.relatedMatch, concept.set_has_related_match),
            (SKOS.exactMatch, concept.set_has_exact_match),
            (SKOS.closeMatch, concept.set_has_close_match),
        ]
        
        for predicate, setter in match_mappings:
            for match in self.graph.objects(uri, predicate):
                concept_obj = self.get_or_create(match, Concept)
                setter(concept_obj)
    
    def populate_datatype(self, datatype: Datatype, uri: URIRef):
        """Popola Datatype (estende Concept)"""
        self.populate_concept(datatype, uri)

    def _create_literal(self, rdflib_lit: RDFlibLiteral, datatype=None, lang=None) -> Literal:
        """I Literal vanno in cache con chiave composita"""
        value = str(rdflib_lit)
        lang = rdflib_lit.language or ""
        datatype = str(rdflib_lit.datatype) if rdflib_lit.datatype else ""
        
        cache_key = f"LITERAL::{value}::{lang}::{datatype}"
        
        if cache_key in self._instance_cache:
            return self._instance_cache[cache_key]
        
        lit = Literal()
        lit.set_has_value(value)
        lit.set_has_language(rdflib_lit.language)
        
        # if rdflib_lit.datatype:
        #     datatype_obj = self.get_or_create(rdflib_lit.datatype, Datatype)
        #     lit.set_has_type(datatype_obj)
        
        self._instance_cache[cache_key] = lit
        return lit
    
    def create_literal_instance(self, rdflib_lit: RDFlibLiteral, datatype=None, lang=None) -> Literal:
        """Metodo pubblico per creare Literal"""
        return self._create_literal(rdflib_lit)
    
    def populate_restriction(self, restriction: Restriction, uri: Node):
        """Popola Restriction (estende Concept)"""
        self.populate_concept(restriction, uri)

    def populate_individual(self, individual: Individual, uri: URIRef):
        """Popola Individual (estende Resource)"""
        self.populate_resource(individual, uri)
        
        # OWL individual relations
        individual_mappings = [
            (OWL.sameAs, individual.set_is_same_as),
            (OWL.differentFrom, individual.set_is_different_from),
            (RDF.type, individual.set_has_type),
        ]

        
        for predicate, setter in individual_mappings:
            for obj in self.graph.objects(uri, predicate):
                individual_obj = self.get_or_create(obj, Individual)
                setter(individual_obj)


class OwlFactory(BaseSemanticFactory):
    """Factory OWL con:
    - inferenza domain/range da superproprietà a Thing
    - Classificazione delle Restrizioni"""
    
    def populate_property(self, prop: Property, uri: URIRef):
        """Override: popola Property + inferisce domain/range dalle superproprietà"""
        super().populate_property(prop, uri)
        
        # Se manca domain, cerca nelle superproprietà
        if not prop.get_has_domain():
            inherited_domains = self._find_inherited_domains(prop)
            if inherited_domains:
                for domain in inherited_domains:
                    prop.set_has_domain(domain)
            else:
                # Nessun domain trovato → usa owl:Thing
                thing = self.get_or_create(OWL.Thing, Concept)
                prop.set_has_domain(thing)
        
        # Se manca range, cerca nelle superproprietà
        if not prop.get_has_range():
            inherited_ranges = self._find_inherited_ranges(prop)
            if inherited_ranges:
                for range_val in inherited_ranges:
                    prop.set_has_range(range_val)
            else:
                # Nessun range trovato → usa owl:Thing
                thing = self.get_or_create(OWL.Thing, Concept)
                prop.set_has_range(thing)
    
    def _find_inherited_domains(self, prop: Property) -> list:
        """Cerca ricorsivamente domain nelle superproprietà"""
        domains = []
        
        for super_prop in prop.get_is_sub_property_of():
            super_domains = super_prop.get_has_domain()
            if super_domains:
                domains.extend(super_domains)
            else:
                domains.extend(self._find_inherited_domains(super_prop))
        
        return domains
    
    def _find_inherited_ranges(self, prop: Property) -> list:
        """Cerca ricorsivamente range nelle superproprietà"""
        ranges = []
        
        for super_prop in prop.get_is_sub_property_of():
            super_ranges = super_prop.get_has_range()
            if super_ranges:
                ranges.extend(super_ranges)
            else:
                ranges.extend(self._find_inherited_ranges(super_prop))
        
        return ranges
    
    def populate_restriction(self, restriction: Restriction, uri: Node):
        """Popola Restriction base + specializzazioni"""
        # Base Concept
        super().populate_restriction(restriction, uri)
        
        # onConcept
        on_class = self.graph.value(uri, OWL.onClass)
        if on_class and isinstance(on_class, URIRef):
            concept = self.get_or_create(on_class, Concept)
            restriction.set_applies_on_concept(concept)

    def populate_truth_function(self, tf: TruthFunction, uri: BNode):
        """Popola TruthFunction (operatori booleani OWL)"""
        self.populate_restriction(tf, uri)
        
        # intersectionOf
        intersection = self.graph.value(uri, OWL.intersectionOf)
        if intersection:
            tf.set_has_logical_operator("and")
            for item in self.graph.items(intersection):
                concept = self.get_or_create(item, Concept)
                tf.set_applies_on_concept(concept)
        
        # unionOf
        union = self.graph.value(uri, OWL.unionOf)
        if union:
            tf.set_has_logical_operator("or")
            for item in self.graph.items(union):
                concept = self.get_or_create(item, Concept)
                tf.set_applies_on_concept(concept)
        
        # complementOf
        complement = self.graph.value(uri, OWL.complementOf)
        if complement:
            tf.set_has_logical_operator("not")
            concept = self.get_or_create(complement, Concept)
            tf.set_applies_on_concept(concept)
      

    def populate_quantifier(self, quant: Quantifier, uri: Node):
        """Popola Quantifier"""

        self.populate_property_concept_restriction(quant, uri)
        
        # someValuesFrom
        some_values = self.graph.value(uri, OWL.someValuesFrom)
        if some_values:
            quant.set_has_quantifier_type("exist")
            concept = self.get_or_create(some_values, Concept)
            quant.set_applies_on_concept(concept)
        
        # allValuesFrom
        all_values = self.graph.value(uri, OWL.allValuesFrom)
        if all_values:
            quant.set_has_quantifier_type("all")
            concept = self.get_or_create(all_values, Concept)
            quant.set_applies_on_concept(concept)
    
    def populate_property_concept_restriction(self, pcr: PropertyConceptRestriction, uri: Node):
        """Popola PropertyConceptRestriction (base per Quantifier e Cardinality)"""

        self.populate_restriction(pcr, uri)
        
        # onProperty
        on_property = self.graph.value(uri, OWL.onProperty)
        if on_property:
            prop_obj = self.get_or_create(on_property, Property)
            pcr.set_applies_on_property(prop_obj)

    def populate_cardinality(self, card: Cardinality, uri: Node):
        """Popola Cardinality"""
        
        # Mappa tipo → valore
        card_mappings = [
            (OWL.cardinality, "exact"),
            (OWL.minCardinality, "min"),
            (OWL.maxCardinality, "max"),
            (OWL.qualifiedCardinality, "exactQualified"),
            (OWL.minQualifiedCardinality, "minQualified"),
            (OWL.maxQualifiedCardinality, "maxQualified"),
        ]
        
        for predicate, card_type in card_mappings:
            value = self.graph.value(uri, predicate)
            if value:
                card.set_has_cardinality_type(card_type)
                card.set_has_cardinality_integer(int(value))
                break
    
    def populate_one_of(self, one_of: OneOf, uri: Node):
        """Popola OneOf"""

        self.populate_restriction(one_of, uri)

        one_of_list = self.graph.value(uri, OWL.oneOf)
        if one_of_list:
            for item in self.graph.items(one_of_list):
                if isinstance(item, Node):
                    resource = self.get_or_create(item, Resource)
                    one_of.set_applies_on_resource(resource)
    
    def populate_value(self, value: Value, id: BNode):
        """Popola Value"""
        self.populate_property_concept_restriction(value, id)

        has_value = self.graph.value(id, OWL.hasValue)
        if has_value and isinstance(has_value, Node):
            resource = self.get_or_create(has_value, Resource)
            value.set_applies_on_resource(resource)

class RdfFactory(BaseSemanticFactory):
    """Factory RDF"""
    pass

class RdfsFactory(BaseSemanticFactory):
    """Factory RDFS"""
    pass


class SkosFactory(BaseSemanticFactory):
    """Factory SKOS"""
    pass


# Alias per retrocompatibilità
# SemanticArtifactFactory = OwlFactory