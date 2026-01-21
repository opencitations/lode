# logic.py - LOGICHE SPECIFICHE PER FORMATO
from abc import ABC, abstractmethod
from rdflib import Graph, URIRef, Node, Literal as RDFlibLiteral, BNode
from rdflib.namespace import RDF, RDFS, OWL, SKOS, XSD
from rdflib.collection import Collection as RDFLibCollection
from models import *


# ========== ALLOWED CLASSES PER FORMATO ==========

ALLOWED_CLASSES = {
    'RDF': {
        Statement, Property, Container, Datatype, Literal, Resource
    },
    'RDFS': {
        Statement, Resource, Literal, Property, Container,
        Concept, Relation, Attribute, Datatype, Literal, Property
    },
    'OWL': {
        Statement, Literal, Relation, Property, Container,
        Concept, Attribute, Datatype,
        Individual, Model, Annotation, 
        TruthFunction, Value, OneOf, Quantifier, Cardinality, PropertyConceptRestriction,
        Collection, Restriction, Statement
    },
    'SKOS': {
        Collection, Literal, Container,
        Concept, Model, Resource, Datatype
    }
}


class BaseLogic(ABC):
    """
    Logica base comune per parsing RDF.
    
    Contiene:
    - Popolamento proprietà generico
    - Creazione literal
    - Gestione collections
    - Utilities comuni
    - Risoluzione classi ammesse per formato
    """
    
    def __init__(self, graph: Graph, instance_cache: dict, strategy):
        self.graph = graph
        self._instance_cache = instance_cache
        self._strategy = strategy
        self._property_mapping = strategy.get_property_mapping()
        self._allowed_classes = self._get_allowed_classes()
        self._triples_map = {} # to get the rdf triples - provenance
    
    # ========== METODI ASTRATTI (implementati dalle subclass) ==========
    
    @abstractmethod
    def _get_allowed_classes(self) -> set:
        """Ritorna set di classi ammesse per questo formato"""
        pass
    
    @abstractmethod
    def phase1_classify_from_predicates(self):
        """Classifica blank nodes da predicati"""
        pass
    
    @abstractmethod
    def phase2_create_from_types(self):
        """Crea istanze da rdf:type"""
        pass
    
    @abstractmethod
    def phase3_populate_properties(self):
        """Popola proprietà"""
        pass
    
    @abstractmethod
    def phase4_process_group_axioms(self):
        """Gestisce assiomi di gruppo (es. owl:equivalentClass)"""
        pass

    @abstractmethod
    def phase5_fallback(self):
        """Gestisce fallback per risorse non categorizzate"""
        pass
    
    def phase6_create_statements(self):
        """Crea Statement per triple non mappate"""
        
        if not hasattr(self, '_statements_created'):
            self._statements_created = set()
        
        statements_count = 0
        
        for subj, pred, obj in self.graph:
            if pred not in [ RDF.first, RDF.rest, RDF.nil, OWL.distinctMembers, OWL.members ]:
                if self._is_triple_mapped(subj, pred, obj):
                    continue
                
                self._create_statement_for_triple(subj, pred, obj)
                statements_count += 1
        
        print(f"  Creati {statements_count} Statement")
    
    # ========== RISOLUZIONE CLASSI AMMESSE ==========
    
    def _resolve_allowed_class(self, python_class: type) -> type:
        """
        Risolve classe non ammessa risalendo l'MRO.
        Si ferma alla PRIMA superclasse ammessa trovata.
        """
        # Se già ammessa, ok
        if python_class in self._allowed_classes:
            return python_class
        
        # Risali MRO (escluso object) e fermati alla PRIMA ammessa
        for parent_class in python_class.__mro__[1:]:
            if parent_class in self._allowed_classes:
                print(f"  ↑ {python_class.__name__} → {parent_class.__name__} (formato)")
                return parent_class
        
        # Fallback finale: Resource (solo se nessuna trovata)
        print(f"  ⚠️  {python_class.__name__} → Resource (fallback)")
        return Resource
    # ========== UTILITIES ==========
    
    def _create_literal(self, rdflib_literal):
        """Crea Literal Python da RDFLib Literal"""
        literal_key = f"LITERAL::{rdflib_literal}"
        
        if literal_key in self._instance_cache:
            return next(iter(self._instance_cache[literal_key]))
        
        literal = Literal()
        literal.set_has_value(str(rdflib_literal))
        
        if rdflib_literal.language:
            literal.set_has_language(rdflib_literal.language)
        
        if rdflib_literal.datatype:
            dt = self.get_or_create(rdflib_literal.datatype, Datatype)
            if dt:
                literal.set_has_type(dt)
        
        self._instance_cache[literal_key] = {literal}
        return literal
    
    def _is_rdf_collection(self, node: Node) -> bool:
        """Check se nodo è Collection"""
        return (node, RDF.first, None) in self.graph
    
    def _instance_matches_target(self, instance, target_classes: list) -> bool:
        """Verifica se istanza matcha target_classes (inclusi parent)"""
        instance_class = instance.__class__
        
        if instance_class in target_classes:
            return True
        
        for parent_class in instance_class.__mro__[1:]:
            if parent_class in target_classes:
                return True
        
        return False
    
    def _apply_setters(self, instance, setters_config, obj):
        """Applica lista di setters"""
        for setter_item in setters_config:
            if isinstance(setter_item, dict):
                for setter_name, value_type in setter_item.items():
                    if not hasattr(instance, setter_name):
                        continue
                    
                    setter = getattr(instance, setter_name)
                    
                    if value_type == 'Literal':
                        try:
                            lit_obj = self._create_literal(obj)
                            setter(lit_obj)
                        except:
                            continue
                    elif isinstance(value_type, bool):
                        setter(value_type)
                    elif isinstance(value_type, type):
                        obj_instance = self.get_or_create(obj, value_type)
                        if obj_instance:
                            setter(obj_instance)
                    else:
                        setter(obj)
            else:
                # Setter senza parametri
                if hasattr(instance, setter_item):
                    setter = getattr(instance, setter_item)
                    setter()
    
    def _handle_collection_object(self, instance, predicate, collection_uri):
        """Gestisce Collection come oggetto di proprietà (FALLBACK)"""
        print(f"  -> Collection per {predicate}")
        
        try:
            collection = RDFLibCollection(self.graph, collection_uri)
            items = []
            
            for item in collection:
                if isinstance(item, RDFlibLiteral):
                    items.append(self._create_literal(item))
                else:
                    item_instance = self.get_or_create(item, Resource)
                    if item_instance:
                        items.append(item_instance)
            
            # Cerca setter appropriato
            config = self._property_mapping.get(predicate, {})
            setters = config.get('setters', [])
            
            for setter_item in setters:
                if isinstance(setter_item, dict):
                    for setter_name, _ in setter_item.items():
                        if hasattr(instance, setter_name):
                            setter = getattr(instance, setter_name)
                            setter(items)
                            break
        except Exception as e:
            print(f"Errore Collection: {e}")
    
    def clear_cache(self):
        """Pulisce cache"""
        self._instance_cache.clear()
    
    # ========== FACTORY METHODS (comuni) ==========
    
    def get_or_create(self, id: Node, python_class: type = None):
        """Get or create instance CON RISOLUZIONE AUTOMATICA"""
        try:
            # Literals
            if isinstance(id, RDFlibLiteral):
                return self._create_literal(id)
            
            # ✅ RISOLVI CLASSE AMMESSA
            if python_class:
                python_class = self._resolve_allowed_class(python_class)
            
            # Individual case
            if python_class == Individual and id in self._instance_cache:
                for existing in self._instance_cache[id]:
                    if not isinstance(existing, Individual):
                        return existing
            
            # Check cache
            if id in self._instance_cache:
                if isinstance(id, BNode):
                    return next(iter(self._instance_cache[id]))
                
                if isinstance(id, URIRef):
                    for obj in self._instance_cache[id]:
                        if isinstance(obj, python_class):
                            return obj
            
            # Create
            instance = python_class()
            if id not in self._instance_cache:
                self._instance_cache[id] = set()
            self._instance_cache[id].add(instance)
            
            # Populate
            self.populate_instance(instance, id)
            return instance
            
        except Exception as e:
            print(f"Cannot create {python_class.__name__ if python_class else 'Unknown'} for {id}: {e}")
            return None
    
    def create_empty_instance(self, uri: Node, python_class: type):
        """Crea istanza vuota (senza populate) CON RISOLUZIONE"""
        # ✅ RISOLVI CLASSE
        python_class = self._resolve_allowed_class(python_class)
        
        instance = python_class()
        if uri not in self._instance_cache:
            self._instance_cache[uri] = set()
        self._instance_cache[uri].add(instance)
        return instance
    
    def populate_instance(self, instance, uri: Node):
        """
        Popolamento generico basato su property_mapping.
        
        Logica comune a tutti i formati:
        1. Popola identifier
        2. Itera su tutte le triple (uri, pred, obj)
        3. Applica mapping se presente
        4. ✅ TRACCIA LE TRIPLE
        """
        
        # Step 1: Identifier
        if isinstance(uri, URIRef):
            instance.set_has_identifier(str(uri))
        elif isinstance(uri, BNode):
            instance.has_identifier = str(uri)
        
        # Inizializza set di triple da salvare per questa istanza
        if instance not in self._triples_map:
            self._triples_map[instance] = set()
        
        # Step 2: Itera su proprietà
        for predicate, obj in self.graph.predicate_objects(uri):
            
            # TRACCIA E SALVA LA TRIPLA
            self._triples_map[instance].add((uri, predicate, obj))
            
            # Check mapping
            if predicate in self._property_mapping:
                config = self._property_mapping[predicate]
                
                # Verifica target_classes
                target_classes = config.get('target_classes', [])
                if target_classes and not self._instance_matches_target(instance, target_classes):
                    continue
                
                # Handler custom
                if 'handler' in config:
                    handler_name = config['handler']
                    handler = getattr(self, handler_name, None)
                    if handler:
                        handler(instance, uri, predicate, obj, None)
                    continue
                
                # Setters
                if 'setters' in config:
                    self._apply_setters(instance, config['setters'], obj)
                    continue
            
            # FALLBACK: Collection generica (solo se NON mappata)
            if self._is_rdf_collection(obj):
                self._handle_collection_object(instance, predicate, obj)

    # ========= HELPERS ======================

    def _is_triple_mapped(self, subj, pred, obj) -> bool:
        """Check se tripla già gestita"""
        # rdf:type è sempre mappato (gestito in phase2)
        if pred == RDF.type:
            return True
        
        # Se soggetto non esiste in cache, non è mappato
        if subj not in self._instance_cache:
            return False
        
        # Se predicato è nel property_mapping, è mappato
        if pred in self._property_mapping:
            return True
        
        return False
    
    def _convert_collection_to_container(self, collection_uri):
        """Converte Collection RDF in Container"""
        if collection_uri in self._instance_cache:
            for cached in self._instance_cache[collection_uri]:
                if isinstance(cached, Container):
                    return cached
        
        container = Container()
        container.set_has_identifier(str(collection_uri))
        
        if collection_uri not in self._instance_cache:
            self._instance_cache[collection_uri] = set()
        self._instance_cache[collection_uri].add(container)
        
        try:
            collection = RDFLibCollection(self.graph, collection_uri)
            members = []
            
            for item in collection:
                if isinstance(item, RDFlibLiteral):
                    members.append(self._create_literal(item))
                else:
                    member_instance = self.get_or_create(item, Resource)
                    if member_instance:
                        members.append(member_instance)
            
            container.set_has_members(members)
        except Exception as e:
            print(f"Errore Collection: {e}")
        
        return container
    
    def _create_statement_for_triple(self, subj, pred, obj):
        """Crea Statement per una tripla (usato in phase6)"""
        if not hasattr(self, '_statements_created'):
            self._statements_created = set()
        
        stmt_key = ('TRIPLE', subj, pred, obj)
        
        if stmt_key in self._statements_created:
            return
        
        statement = Statement()
        
        # TRACCIA e salva LA TRIPLA per lo Statement
        if statement not in self._triples_map:
            self._triples_map[statement] = set()
        self._triples_map[statement].add((subj, pred, obj))
        
        # Subject: usa get_or_create con Resource
        subj_obj = self.get_or_create(subj, Resource)
        if subj_obj:
            statement.set_has_subject(subj_obj)
        
        # Predicate: SEMPRE Property
        pred_inst = self.get_or_create(pred, Property)
        if pred_inst:
            statement.set_has_predicate(pred_inst)
        
        # Object: dipende dal tipo
        if self._is_rdf_collection(obj):
            obj_inst = self._convert_collection_to_container(obj)
        elif isinstance(obj, RDFlibLiteral):
            obj_inst = self._create_literal(obj)
        else:
            obj_inst = self.get_or_create(obj, Resource)
        
        if obj_inst:
            statement.set_has_object(obj_inst)
        
        # Cache statement
        if stmt_key not in self._instance_cache:
            self._instance_cache[stmt_key] = set()
        self._instance_cache[stmt_key].add(statement)
        
        self._statements_created.add(stmt_key)
    
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
        
        try:
            collection = RDFLibCollection(self.graph, obj)
            for item in collection:
                concept = self.get_or_create(item, Concept)
                if concept:
                    instance.set_applies_on_concept(concept)
        except Exception as e:
            print(f"Errore intersectionOf: {e}")

    def handle_union(self, instance, uri, predicate, obj, setter=None):
        """Handler per unionOf"""
        instance.set_has_logical_operator("or")
        
        try:
            collection = RDFLibCollection(self.graph, obj)
            for item in collection:
                concept = self.get_or_create(item, Concept)
                if concept:
                    instance.set_applies_on_concept(concept)
        except Exception as e:
            print(f"Errore unionOf: {e}")

    def handle_complement(self, instance, uri, predicate, obj, setter=None):
        """Handler per complementOf"""
        instance.set_has_logical_operator("not")
        concept = self.get_or_create(obj, Concept)
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

    def handle_range(self, instance, uri, predicate, obj, setter=None):
        """
        Handler intelligente per rdfs:range:
        - Relation → crea Concept
        - Property/Attribute → crea Resource
        """
        if isinstance(instance, Relation):
            # Relation vuole Concept
            range_obj = self.get_or_create(obj, Concept)
            if range_obj:
                instance.set_has_range(range_obj)
        
        elif isinstance(instance, (Property, Attribute)):
            # Property/Attribute vuole Resource
            range_obj = self.get_or_create(obj, Resource)
            if range_obj:
                instance.set_has_range(range_obj)


# ========== OWL LOGIC ==========

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
        """Popola proprietà OWL + applica default domain/range"""
        print("\n--- FASE 3: Popolamento OWL ---")
        
        for uri in list(self._instance_cache.keys()):
            for instance in list(self._instance_cache[uri]):
                self.populate_instance(instance, uri)
                
                # LOGICA OWL: default domain/range solo per Property/Relation/Attribute
                if isinstance(instance, (Property, Relation, Attribute)):
                    self._apply_owl_defaults(instance)
        
        print(f"  Popolate: {len(self._instance_cache)}")
    
    def _apply_owl_defaults(self, property_instance):
        """Applica owl:Thing se domain/range mancano"""
        
        owl_thing = None  # Lazy creation
        
        # Check domain
        needs_domain = True
        try:
            domain = property_instance.get_has_domain()
            # Se ritorna qualcosa di non vuoto, ha già domain
            if domain and (isinstance(domain, list) and len(domain) > 0 or not isinstance(domain, list)):
                needs_domain = False
        except:
            pass
        
        if needs_domain and hasattr(property_instance, 'set_has_domain'):
            if owl_thing is None:
                owl_thing = self.get_or_create(OWL.Thing, Concept)
            property_instance.set_has_domain([owl_thing])
        
        # Check range
        needs_range = True
        try:
            range_val = property_instance.get_has_range()
            # Se ritorna qualcosa di non vuoto, ha già range
            if range_val and (isinstance(range_val, list) and len(range_val) > 0 or not isinstance(range_val, list)):
                needs_range = False
        except:
            pass
        
        if needs_range and hasattr(property_instance, 'set_has_range'):
            if owl_thing is None:
                owl_thing = self.get_or_create(OWL.Thing, Concept)
            property_instance.set_has_range([owl_thing])

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
            if pred not in self._instance_cache and pred not in [RDF.type] and isinstance(pred, BNode):
                self.create_empty_instance(pred, Annotation)
                annotation_count += 1
        
        print(f"  Annotation: {annotation_count}")
        
        # 2. Soggetti non categorizzati → Individual
        all_subjects = set(self.graph.subjects())
        individual_count = 0
        
        for subj in all_subjects:
            if subj not in self._instance_cache and isinstance(subj, RDFLibCollection) :
                self.get_or_create(subj, Individual)
                individual_count += 1
        
        print(f"  Individual: {individual_count}")
        
        # 3. Oggetti di proprietà non categorizzati → Individual
        for s, p, o in self.graph:
            if not isinstance(o, RDFlibLiteral) and o not in self._instance_cache:
                if not self._is_rdf_collection(o):
                    # Controlla se l'URI appartiene a namespace che va escluso
                    exclude_namespaces = [OWL, RDF, RDFS, SKOS]
                    if not any(str(o).startswith(str(ns)) for ns in exclude_namespaces):
                        self.get_or_create(o, Individual)
                        individual_count += 1
        
        print(f"  Totale Individual: {individual_count}")
    
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

        
    def _is_triple_mapped(self, subj, pred, obj) -> bool:
        """Check se tripla già gestita"""
        # rdf:type è sempre mappato (gestito in phase2)
        if pred == RDF.type:
            return True
        
        # Se soggetto non esiste in cache, non è mappato
        if subj not in self._instance_cache:
            return False
        
        # Se predicato è nel property_mapping, è mappato
        if pred in self._property_mapping:
            return True
        
        return False
    
    def _create_statement_for_triple(self, subj, pred, obj):
        """Crea Statement"""
        stmt_key = ('TRIPLE', subj, pred, obj)
        
        if stmt_key in self._statements_created:
            return
        
        statement = Statement()
        
        # Subject: usa get_or_create con Resource
        subj_obj = self.get_or_create(subj, Individual)
        if subj_obj:
            statement.set_has_subject(subj_obj)
        
        # Predicate: SEMPRE Property
        pred_inst = self.get_or_create(pred, Property)
        if pred_inst:
            statement.set_has_predicate(pred_inst)
        
        # Object: dipende dal tipo
        if self._is_rdf_collection(obj):
            obj_inst = self._convert_collection_to_container(obj)
        elif isinstance(obj, RDFlibLiteral):
            obj_inst = self._create_literal(obj)
        else:
            obj_inst = self.get_or_create(obj, Individual)
        
        if obj_inst:
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


# ========== RDFS LOGIC ==========

class RdfsLogic(BaseLogic):
    """
    Logica RDFS.
    
    Differenze:
    - NO default domain/range
    - Inferenze più semplici
    - NO Restriction, Individual, CompositeClass
    """
    
    def _get_allowed_classes(self) -> set:
        """RDFS ammette solo classi base"""
        return ALLOWED_CLASSES['RDFS']
    
    def phase1_classify_from_predicates(self):
        print("\n--- FASE 1: Classificazione RDFS ---")
        print("  Skip (RDFS non ha classificatori)")
    
    def phase2_create_from_types(self):
        print("\n--- FASE 2: Types RDFS ---")
        
        type_mapping = self._strategy.get_type_mapping()
        created = 0
        
        for rdf_type, config in type_mapping.items():
            py_class = config.get('target_class')
            if not py_class:
                continue
            
            for uri in self.graph.subjects(RDF.type, rdf_type):
                if uri not in self._instance_cache:
                    self.create_empty_instance(uri, py_class)
                    created += 1
        
        print(f"  Create: {created}")
    
    def phase3_populate_properties(self):
        print("\n--- FASE 3: Popolamento RDFS ---")
        
        for uri in list(self._instance_cache.keys()):
            for instance in list(self._instance_cache[uri]):
                self.populate_instance(instance, uri)
        
        print(f"  Popolate: {len(self._instance_cache)}")
    
    def phase4_process_group_axioms(self):
        print("\n--- FASE 4: Axioms RDFS ---")
        print("  Nessun axiom RDFS")

    def phase5_fallback(self):
        print("\n--- FASE 5: FALLBACK ---")
        print("TO BE IMPLEMENTED SOON")


# ========== RDF LOGIC ==========

# ========== RDF LOGIC ==========

class RdfLogic(BaseLogic):
    """
    Logica RDF pura.
    
    Differenze:
    - Tutto è Resource (default)
    - USA type_mapping per rdf:Property e altri types
    - Crea Statement per ogni tripla
    - Solo classi base: Statement, Resource, Literal, Property, Container
    """
    
    def __init__(self, graph, instance_cache, strategy):
        super().__init__(graph, instance_cache, strategy)
        self._statements_created = set()
    
    def _get_allowed_classes(self) -> set:
        """RDF puro ammette solo classi essenziali"""
        return ALLOWED_CLASSES['RDF']
        
    
    def phase1_classify_from_predicates(self):
        print("\n--- FASE 1: Classificazione RDF ---")
        print("  Skip (RDF puro)")
    
    def phase2_create_from_types(self):
        print("\n--- FASE 2: Types RDF ---")
        
        # ✅ USA TYPE MAPPING per creare classi specifiche
        type_mapping = self._strategy.get_type_mapping()
        created = 0
        
        for subj, pred, obj in self.graph.triples((None, RDF.type, None)):
            if subj in self._instance_cache:
                continue
            
            # Check se c'è mapping specifico per questo type
            if obj in type_mapping:
                config = type_mapping[obj]
                py_class = config.get('target_class', Resource)
            else:
                # Default: Resource
                py_class = Resource
            
            self.create_empty_instance(subj, py_class)
            created += 1
        
        print(f"  Create: {created}")
    
    def phase3_populate_properties(self):
        print("\n--- FASE 3: Popolamento RDF ---")
        
        for uri in list(self._instance_cache.keys()):
            for instance in list(self._instance_cache[uri]):
                self.populate_instance(instance, uri)
        
        print(f"  Popolate: {len(self._instance_cache)}")
    
    def phase4_process_group_axioms(self):
        print("\n--- FASE 4: Axioms RDF ---")
        print("  Nessun axiom RDF")

    def phase5_fallback(self):
        print("\n--- FASE 5: FALLBACK ---")
        print("TO BE IMPLEMENTED SOON")
    
    def phase6_create_statements(self):
        """Crea Statement per triple non mappate"""
        print("\n--- FASE 6: Statements RDF ---")
        
        statements_count = 0
        
        for subj, pred, obj in self.graph:
            if self._is_triple_mapped(subj, pred, obj):
                continue
            
            self._create_statement_for_triple(subj, pred, obj)
            statements_count += 1
        
        print(f"  Creati {statements_count} Statement")
    
# ========== SKOS LOGIC ==========

class SkosLogic(BaseLogic):
    """
    Logica SKOS.
    
    Differenze:
    - Focus su Concept/ConceptScheme
    - Relazioni skos:broader/narrower
    - NO default domain/range
    - NO Restriction, Individual, CompositeClass, Datatype, Attribute
    """
    
    def _get_allowed_classes(self) -> set:
        """SKOS ammette solo classi orientate ai thesauri"""
        return ALLOWED_CLASSES['SKOS']
    
    def phase1_classify_from_predicates(self):
        print("\n--- FASE 1: Classificazione SKOS ---")
        print("  Skip (SKOS usa solo types)")
    
    def phase2_create_from_types(self):
        print("\n--- FASE 2: Types SKOS ---")
        
        type_mapping = self._strategy.get_type_mapping()
        created = 0
        
        for rdf_type, config in type_mapping.items():
            py_class = config.get('target_class')
            if not py_class:
                continue
            
            for uri in self.graph.subjects(RDF.type, rdf_type):
                if uri not in self._instance_cache:
                    self.create_empty_instance(uri, py_class)
                    created += 1
        
        print(f"  Create: {created}")
    
    def phase3_populate_properties(self):
        print("\n--- FASE 3: Popolamento SKOS ---")
        
        for uri in list(self._instance_cache.keys()):
            for instance in list(self._instance_cache[uri]):
                self.populate_instance(instance, uri)
        
        print(f"  Popolate: {len(self._instance_cache)}")
    
    def phase4_process_group_axioms(self):
        print("\n--- FASE 4: Axioms SKOS ---")
        print("  Nessun axiom SKOS")

    def phase5_fallback(self):
        print("\n--- FASE 5: FALLBACK ---")
        print("TO BE IMPLEMENTED SOON")
    
    # Handler specifici SKOS
    def handle_membership(self, instance, uri, predicate, obj, value):
        """Gestisce skos:member"""
        if not isinstance(instance, Collection):
            return
        
        for obj_uri in self.graph.objects(uri, predicate):
            member_obj = self._instance_cache.get(obj_uri)
            
            if isinstance(member_obj, set):
                member_obj = next(iter(member_obj), None)
            
            if member_obj and isinstance(member_obj, (Model, Concept)):
                instance.set_has_member(member_obj)
    
    def handle_narrower(self, instance, uri, predicate, obj, value):
        """Gestisce skos:narrower (inverso)"""
        if not isinstance(instance, Concept):
            return
        
        for subj_uri in self.graph.subjects(predicate, uri):
            broader_obj = self._instance_cache.get(subj_uri)
            
            if isinstance(broader_obj, set):
                broader_obj = next(iter(broader_obj), None)
            
            if broader_obj and isinstance(broader_obj, Concept):
                instance.set_is_sub_concept_of(broader_obj)