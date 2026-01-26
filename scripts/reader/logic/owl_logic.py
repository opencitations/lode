# logic.py - LOGICHE SPECIFICHE PER FORMATO
from rdflib import Graph, URIRef, Node, Literal as RDFlibLiteral, BNode
from rdflib.namespace import RDF, RDFS, OWL, SKOS, XSD
from rdflib.collection import Collection as RDFLibCollection

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from models import *
from .base_logic import BaseLogic, ALLOWED_CLASSES

class OwlLogic(BaseLogic):
    """
    Logica specifica OWL.
    
    Differenze:
    - Domain/Range default a owl:Thing
    - Gestione restrictions (onProperty, someValuesFrom, etc.)
    - Equivalenze e disgiunzioni
    - Classi ammesse: tutte
    """
    
    def _get_allowed_classes(self) -> set:
        """OWL ammette tutte le classi"""
        return ALLOWED_CLASSES['OWL']
    
    def _get_allowed_namespaces(self) -> set:
        return {str(RDF), str(RDFS), str(OWL)}
    
    def phase1_classify_from_predicates(self):
        """Classifica blank nodes OWL"""
        print("\n--- FASE 1: Classificazione OWL ---")
        
        classifier_preds = self._strategy.get_classifier_predicates()
        if not classifier_preds:
            print("  Nessun classificatore")
            return
        
        classified = {}
        
        for pred in classifier_preds:
            for uri in self.graph.subjects(pred, None):
                if isinstance(uri, BNode) and uri not in classified:
                    python_class = self._strategy.classify_by_predicate(uri, self.graph)
                    if python_class:
                        classified[uri] = python_class
        
        # Ricorsione per liste
        self._classify_nested(classified, classifier_preds)
        
        # Crea istanze
        for uri, py_class in classified.items():
            self.create_empty_instance(uri, py_class)
        
        print(f"  Classificate: {len(classified)}")
    
    def phase2_create_from_types(self):
        """Crea da rdf:type + applica default OWL"""
        print("\n--- FASE 2: Types OWL ---")
        
        type_mapping = self._strategy.get_type_mapping()
        created = 0
        
        for rdf_type, config in type_mapping.items():
            py_class = config.get('target_class')
            if not py_class:
                continue
            
            for uri in self.graph.subjects(RDF.type, rdf_type):
                # Crea istanza solo se non esiste
                if uri not in self._instance_cache:
                    self.create_empty_instance(uri, py_class)
                    created += 1
                
                # APPLICA SETTERS SEMPRE (anche se istanza già esisteva)
                if 'setters' in config:
                    instances = self._instance_cache[uri]
                    for instance in instances:
                        self._apply_setters_immediate(instance, config['setters'])
            
    def phase3_populate_properties(self):
        """Popola proprietà OWL + applica default domain/range + default type per Individual"""
        print("\n--- FASE 3: Popolamento OWL ---")
        
        for uri in list(self._instance_cache.keys()):
            for instance in list(self._instance_cache[uri]):
                self.populate_instance(instance, uri)
                
                # LOGICA OWL: default domain/range solo per Property/Relation/Attribute
                if isinstance(instance, (Property, Relation, Attribute)):
                    self._apply_owl_defaults(instance)

                # LOGICA OWL: default type per Individual
                if isinstance(instance, Individual):
                    try:
                        if instance.get_has_type() == []:
                            owl_thing = self.get_or_create(OWL.Thing, Concept)
                            instance.set_has_type([owl_thing])
                    except:
                        # Se get_has_type fallisce, assegna comunque owl:Thing
                        owl_thing = self.get_or_create(OWL.Thing, Concept)
                        instance.set_has_type([owl_thing])

            
    def _resolve_allowed_class(self, python_class: type, id: Node = None) -> type:
        """
        Sovrascrive il base, non risale l'MRO ma decide come assegnare le classi non ammesse
        basandosi su rdf:type o sul tipo del parent più vicino nella gerarchia
        """
        # Se già ammessa, ok
        if python_class in self._allowed_classes:
            return python_class
        
        # SE GIÀ IN CACHE: usa il tipo esistente (è già stato risolto correttamente)
        if id and id in self._instance_cache:
            for existing in self._instance_cache[id]:
                existing_type = type(existing)
                # Ritorna il tipo più specifico trovato (non Individual)
                if existing_type != Individual:
                    return existing_type
        
        # LOGICA DI RISOLUZIONE (solo se NON in cache o solo Individual)
        if id is not None and python_class == Property:
            
            # STEP 1: Controlla rdf:type diretto
            for _, _, rdf_type in self.graph.triples((id, RDF.type, None)):
                if rdf_type == OWL.ObjectProperty:
                    return Relation
                elif rdf_type == OWL.DatatypeProperty:
                    return Attribute
                elif rdf_type == OWL.AnnotationProperty:
                    return Annotation
            
            # STEP 2: Cerca parent nella cache
            for parent_uri, _, _ in self.graph.triples((None, RDFS.subPropertyOf, id)):
                if parent_uri in self._instance_cache:
                    instances = self._instance_cache[parent_uri]
                    for instance in instances:
                        if isinstance(instance, Relation):
                            return Relation
                        elif isinstance(instance, Attribute):
                            return Attribute
                        # Annotation continua a cercare parent più specifici
            
            # STEP 3: Ricorsione sul parent non in cache
            for _, _, parent_uri in self.graph.triples((id, RDFS.subPropertyOf, None)):
                # Salta parent già processati nello STEP 2
                if parent_uri not in self._instance_cache:
                    # Ricorsione: chiedi di risolvere il parent
                    resolved = self._resolve_allowed_class(Property, parent_uri)
                    if resolved != Annotation:
                        return resolved
                    
            # STEP 4: Controlla OWL.onProperty nelle restritions
            for restriction_uri in self.graph.subjects(OWL.onProperty, id):
                # È usata in una restriction → deve essere Relation
                return Relation
            
            # Default: Annotation
            return Annotation
        
        elif python_class == Resource:
            return Individual
        
        # Fallback per altri casi
        return python_class

    def _apply_owl_defaults(self, property_instance):
        """Applica owl:Thing se domain/range mancano risalendo la gerarchia"""
        
        owl_thing = None  # Lazy creation
        
        # Check domain (con risalita gerarchia)
        inherited_domain = self._get_inherited_domain(property_instance)
        if not inherited_domain:
            owl_thing = self.get_or_create(OWL.Thing, Concept)
            property_instance.set_has_domain(owl_thing)
            print(property_instance, property_instance.get_has_domain())
        
        # Check range (con risalita gerarchia)
        inherited_range = self._get_inherited_range(property_instance)
        if not inherited_range:
            owl_thing = self.get_or_create(OWL.Thing, Concept)
            property_instance.set_has_range(owl_thing)
            print(property_instance, property_instance.get_has_range())

    def _get_inherited_domain(self, property_instance):
        """Risale rdfs:subPropertyOf per trovare domain"""
        visited = set()
        queue = [property_instance]
        
        while queue:
            current = queue.pop(0)
            if id(current) in visited:
                continue
            visited.add(id(current))
            
            # Check domain diretto
            try:
                domain = current.get_has_domain()
                if domain and (isinstance(domain, list) and len(domain) > 0 or domain):
                    return domain
            except:
                pass
            
            # Risali ai super-properties
            try:
                supers = current.get_subproperty_of()
                if supers:
                    if not isinstance(supers, list):
                        supers = [supers]
                    queue.extend(supers)
            except:
                pass
        
        return None

    def _get_inherited_range(self, property_instance):
        """Risale rdfs:subPropertyOf per trovare range"""
        visited = set()
        queue = [property_instance]
        
        while queue:
            current = queue.pop(0)
            if id(current) in visited:
                continue
            visited.add(id(current))
            
            # Check range diretto
            try:
                range_val = current.get_has_range()
                if range_val and (isinstance(range_val, list) and len(range_val) > 0 or range_val):
                    return range_val
            except:
                pass
            
            # Risali ai super-properties
            try:
                supers = current.get_subproperty_of()
                if supers:
                    if not isinstance(supers, list):
                        supers = [supers]
                    queue.extend(supers)
            except:
                pass
        
        return None



    def phase4_process_group_axioms(self):
        """Processa assiomi OWL (equivalentClass, etc.)"""
        print("\n--- FASE 4: Axioms OWL ---")
        
        axioms = self._strategy.get_group_axioms()
        for axiom_type, handler_name in axioms.items():
            for uri in self.graph.subjects(RDF.type, axiom_type):
                handler = getattr(self, handler_name, None)
                if handler:
                    handler(uri)
    
    def _classify_nested(self, classified, predicates):
        """Classifica ricorsivamente dentro liste OWL"""
        list_preds = [OWL.intersectionOf, OWL.unionOf, OWL.oneOf]
        
        for bnode in list(classified.keys()):
            for pred, obj in self.graph.predicate_objects(bnode):
                if pred in list_preds:
                    try:
                        collection = RDFLibCollection(self.graph, obj)
                        for item in collection:
                            if isinstance(item, BNode) and item not in classified:
                                py_class = self._strategy.classify_by_predicate(item, self.graph)
                                if py_class:
                                    classified[item] = py_class
                    except:
                        pass
    
    def _apply_setters_immediate(self, instance, setters_config):
        """Applica setters configurati"""
        for setter_item in setters_config:
            if isinstance(setter_item, dict):
                for setter_name, value in setter_item.items():
                    if hasattr(instance, setter_name):
                        setter = getattr(instance, setter_name)
                        setter(value)
            else:
                if hasattr(instance, setter_item):
                    setter = getattr(instance, setter_item)
                    setter()

    def phase5_fallback(self):
        """
        Fallback OWL:
        - Proprietà non definite → Annotation
        - Oggetti di proprietà → Individual
        - Triple non parsate → Statement
        """
        print("\n--- FASE 5: Fallback OWL ---")
        
        # 1. Proprietà usate ma non definite → Annotation
        all_predicates = set(self.graph.predicates())
        annotation_count = 0
        
        for pred in all_predicates:
            if pred not in self._instance_cache and isinstance(pred, BNode):
                self.create_empty_instance(pred, Annotation)
                annotation_count += 1
                
        # 2. Soggetti non categorizzati → Individual
        all_subjects = set(self.graph.subjects())
        individual_count = 0
        
        for subj in all_subjects:
            if subj not in self._instance_cache and isinstance(subj, RDFLibCollection) :
                self.get_or_create(subj, Individual)
                individual_count += 1
                
        # 3. Oggetti di proprietà non categorizzati → Individual
        for s, p, o in self.graph:
            if not isinstance(o, RDFlibLiteral) and o not in self._instance_cache:
                if not self._is_rdf_collection(o):
                    # Controlla se l'URI appartiene a namespace che va escluso
                    exclude_namespaces = [OWL, RDF, RDFS, SKOS]
                    if not any(str(o).startswith(str(ns)) for ns in exclude_namespaces):
                        self.get_or_create(o, Individual)
                        individual_count += 1
            
    # Handler group axioms
    def process_all_disjoint_classes(self, uri: Node):
        """Processa owl:AllDisjointClasses"""
        members_list = self.graph.value(uri, OWL.members)
        if not members_list:
            return
        
        try:
            collection = RDFLibCollection(self.graph, members_list)
            members = list(collection)
            
            for i, class_a_uri in enumerate(members):
                class_a = self.get_or_create(class_a_uri, Concept)
                
                for class_b_uri in members[i+1:]:
                    class_b = self.get_or_create(class_b_uri, Concept)
                    
                    class_a.set_is_disjoint_with(class_b)
                    class_b.set_is_disjoint_with(class_a)
        except Exception as e:
            print(f"Errore AllDisjointClasses: {e}")

    def process_all_different(self, uri: Node):
        """Processa owl:AllDifferent"""
        members_list = self.graph.value(uri, OWL.distinctMembers)
        if not members_list:
            return
        
        try:
            collection = RDFLibCollection(self.graph, members_list)
            members = list(collection)
            
            for i, individual_a_uri in enumerate(members):
                individual_a = self.get_or_create(individual_a_uri, Individual)
                
                for individual_b_uri in members[i+1:]:
                    individual_b = self.get_or_create(individual_b_uri, Individual)
                    
                    individual_a.set_is_different_from(individual_b)
                    individual_b.set_is_different_from(individual_a)
        except Exception as e:
            print(f"Errore AllDifferent: {e}")

    def process_all_disjoint_properties(self, uri: Node):
        """Processa owl:AllDisjointProperties"""
        members_list = self.graph.value(uri, OWL.members)
        if not members_list:
            return
        
        try:
            collection = RDFLibCollection(self.graph, members_list)
            members = list(collection)
            
            for i, prop_a_uri in enumerate(members):
                prop_a = self.get_or_create(prop_a_uri, Property)
                
                for prop_b_uri in members[i+1:]:
                    prop_b = self.get_or_create(prop_b_uri, Property)
                    
                    prop_a.set_is_disjoint_with(prop_b)
                    prop_b.set_is_disjoint_with(prop_a)
        except Exception as e:
            print(f"Errore AllDisjointProperties: {e}")

        
    # def _is_triple_mapped(self, subj, pred, obj) -> bool:
    #     """Check se tripla già gestita"""
    #     # rdf:type è sempre mappato (gestito in phase2)
    #     if pred == RDF.type:
    #         return True
        
    #     # Se soggetto non esiste in cache, non è mappato
    #     if subj not in self._instance_cache:
    #         return False
        
    #     # Se predicato è nel property_mapping, è mappato
    #     if pred in self._property_mapping:
    #         return True
        
        # return False
    
    def _create_statement_for_triple(self, subj, pred, obj):
        """Crea Statement"""
        stmt_key = ('TRIPLE', subj, pred, obj)
        
        if stmt_key in self._statements_created:
            return
        
        statement = Statement()

        if pred != RDF.type:
            # Subject: usa get_or_create con Resource
            subj_obj = self.get_or_create(subj, Individual)
            statement.set_has_subject(subj_obj)
            
            # Object: dipende dal tipo
            if self._is_rdf_collection(obj):
                obj_inst = self._convert_collection_to_container(obj)
                pred_inst = self.get_or_create(pred, Relation)
                statement.set_has_predicate(pred_inst)
            elif isinstance(obj, RDFlibLiteral):
                obj_inst = self._create_literal(obj)
                pred_inst = self.get_or_create(pred, Annotation)
                statement.set_has_predicate(pred_inst)
            else:
                obj_inst = self.get_or_create(obj, Individual)
                pred_inst = self.get_or_create(pred, Relation)
                statement.set_has_predicate(pred_inst)

            statement.set_has_object(obj_inst)
            
            # Cache statement
            if stmt_key not in self._instance_cache:
                self._instance_cache[stmt_key] = set()
            self._instance_cache[stmt_key].add(statement)
            
            self._statements_created.add(stmt_key)

            # Saves the triple in triples_map
            if statement not in self._triples_map:
                self._triples_map[statement] = set()
            self._triples_map[statement].add((subj, pred, obj))

    # ========== HANDLER Restriction ==========
    
    def handle_property_chain(self, instance, uri, predicate, obj, setter=None):
        """Handler per owl:propertyChainAxiom"""
        try:
            collection = RDFLibCollection(self.graph, obj)
            chain_instances = []
            for chain_uri in collection:
                chain_instance = self.get_or_create(chain_uri, Relation)
                chain_instances.append(chain_instance)
            instance.set_has_property_chain(chain_instances)
        except Exception as e:
            print(f"Errore propertyChain: {e}")

    def handle_quantifier_exist(self, instance, uri, predicate, obj, setter=None):
        """Handler per someValuesFrom"""
        instance.set_has_quantifier_type("exist")
        concept = self.get_or_create(obj, Concept)
        if concept:
            instance.set_applies_on_concept(concept)

    def handle_quantifier_all(self, instance, uri, predicate, obj, setter=None):
        """Handler per allValuesFrom"""
        instance.set_has_quantifier_type("all")
        concept = self.get_or_create(obj, Concept)
        if concept:
            instance.set_applies_on_concept(concept)

    def handle_cardinality_exact(self, instance, uri, predicate, obj, setter=None):
        """Handler per cardinality"""
        instance.set_has_cardinality_type("exact")
        instance.set_has_cardinality(obj)

    def handle_cardinality_min(self, instance, uri, predicate, obj, setter=None):
        """Handler per minCardinality"""
        instance.set_has_cardinality_type("min")
        instance.set_has_cardinality(obj)

    def handle_cardinality_max(self, instance, uri, predicate, obj, setter=None):
        """Handler per maxCardinality"""
        instance.set_has_cardinality_type("max")
        instance.set_has_cardinality(obj)

    def handle_cardinality_exact_qualified(self, instance, uri, predicate, obj, setter=None):
        """Handler per qualifiedCardinality"""
        instance.set_has_cardinality_type("exact")
        
        on_class = self.graph.value(uri, OWL.onClass)
        if on_class:
            concept = self.get_or_create(on_class, Concept)
            if concept:
                instance.set_applies_on_concept(concept)
        instance.set_has_cardinality(obj)

    def handle_cardinality_min_qualified(self, instance, uri, predicate, obj, setter=None):
        """Handler per minQualifiedCardinality"""
        instance.set_has_cardinality_type("min")
        
        on_class = self.graph.value(uri, OWL.onClass)
        if on_class:
            concept = self.get_or_create(on_class, Concept)
            if concept:
                instance.set_applies_on_concept(concept)
        
        instance.set_has_cardinality(obj)

    def handle_cardinality_max_qualified(self, instance, uri, predicate, obj, setter=None):
        """Handler per maxQualifiedCardinality"""
        instance.set_has_cardinality_type("max")
        
        on_class = self.graph.value(uri, OWL.onClass)
        if on_class:
            concept = self.get_or_create(on_class, Concept)
            if concept:
                instance.set_applies_on_concept(concept)
        
        instance.set_has_cardinality(obj)

    def handle_intersection(self, instance, uri, predicate, obj, setter=None):
        """Handler per intersectionOf"""
        instance.set_has_logical_operator("and")

        is_datatype = (uri, RDF.type, RDFS.Datatype) in self.graph

        try:
            collection = RDFLibCollection(self.graph, obj)
            for item in collection:
                if is_datatype:
                    datatype = self.get_or_create(item, Datatype)
                    if datatype:
                        instance.set_applies_on_concept(datatype)
                else:
                    concept = self.get_or_create(item, Concept)
                    if concept:
                        instance.set_applies_on_concept(concept)
        except Exception as e:
            print(f"Errore intersectionOf: {e}")

    def handle_union(self, instance, uri, predicate, obj, setter=None):
        """Handler per unionOf"""
        instance.set_has_logical_operator("or")

        is_datatype = (uri, RDF.type, RDFS.Datatype) in self.graph
        
        try:
            collection = RDFLibCollection(self.graph, obj)
            for item in collection:
                if is_datatype:
                    datatype = self.get_or_create(item, Datatype)
                    if datatype:
                        instance.set_applies_on_concept(datatype)
                else:
                    concept = self.get_or_create(item, Concept)
                    if concept:
                        instance.set_applies_on_concept(concept)
        except Exception as e:
            print(f"Errore unionOf: {e}")

    def handle_complement(self, instance, uri, predicate, obj, setter=None):
        """Handler per complementOf"""
        instance.set_has_logical_operator("not")

        is_datatype = (uri, RDF.type, RDFS.Datatype) in self.graph

        if is_datatype:
            datatype = self.get_or_create(uri, Datatype)
            if datatype:
                instance.set_applies_on_concept(datatype)
        else:
            concept = self.get_or_create(uri, Concept)
            if concept:
                instance.set_applies_on_concept(concept)

    def handle_one_of(self, instance, uri, predicate, obj, setter=None):
        """Handler per oneOf"""
        try:
            collection = RDFLibCollection(self.graph, obj)
            for item in collection:
                resource = self.get_or_create(item, Resource)
                if resource:
                    instance.set_applies_on_resource(resource)
        except Exception as e:
            print(f"Errore oneOf: {e}")


            