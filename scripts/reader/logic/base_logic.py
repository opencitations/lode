# logic.py - LOGICHE SPECIFICHE PER FORMATO
from abc import ABC, abstractmethod
from rdflib import Graph, URIRef, Node, Literal as RDFlibLiteral, BNode
from rdflib.namespace import RDF, RDFS, OWL, SKOS, XSD
from rdflib.collection import Collection as RDFLibCollection

from models import *

# ========== ALLOWED CLASSES PER FORMATO ==========

ALLOWED_CLASSES = {
    'RDF': {
        Statement, Property, Container, Datatype, Literal, Resource, Concept
    },
    # 'RDFS': {
    #     Statement, Resource, Literal, Property, Container,
    #     Concept, Relation, Attribute, Datatype, Literal, Property
    # },
    'OWL': {
        Statement, Literal, Relation, Container,
        Concept, Attribute, Datatype,
        Individual, Model, Annotation, 
        TruthFunction, Value, OneOf, Quantifier, Cardinality, PropertyConceptRestriction,
        Collection, Restriction
    },
    'SKOS': {
        Collection, Literal, Resource,
        Concept, Model, Datatype
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
        self._triples_map = {}
        self._allowed_namespaces = self._get_allowed_namespaces() 
    
    # ========== METODI ASTRATTI (implementati dalle subclass) ==========
    
    @abstractmethod
    def _get_allowed_classes(self) -> set:
        """Ritorna set di classi ammesse per questo formato"""
        pass

    @abstractmethod
    def _get_allowed_namespaces(self) -> set:
        """Ritorna set di namespaces ammessi per questo formato"""
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
        
        for subj, pred, obj in self.graph:
            if pred not in [ RDF.first, RDF.rest, RDF.nil, OWL.distinctMembers, OWL.members ]:
                if self._is_triple_mapped(subj, pred, obj):
                    continue
                
                self._create_statement_for_triple(subj, pred, obj)
            
    # ========== RISOLUZIONE base CLASSI AMMESSE ==========
    
    def _resolve_allowed_class(self, python_class: type, id: Node = None) -> type:
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
    
    # ========== LOGIC CORE METHODS (comuni) ==========
    
    def get_or_create(self, id: Node, python_class: type = None, populate: bool = True):
        """Get or create instance CON RISOLUZIONE AUTOMATICA"""
        try:
            # Literals
            if isinstance(id, RDFlibLiteral):
                return self._create_literal(id)
            
            # RISOLVI CLASSE AMMESSA
            if python_class:
                python_class = self._resolve_allowed_class(python_class, id)

            # Skips all entities which share the structural namespaces declared in self._allowed_namespaces
            if isinstance(id, URIRef):
                uri_str = str(id)
                for ns in self._allowed_namespaces:
                    if uri_str.startswith(ns):
                        return None

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
            
            # Populate (opzionale)
            if populate:
                self.populate_instance(instance, id)
            
            return instance
        
        except Exception as e:
            print(f"Cannot create {python_class.__name__ if python_class else 'Unknown'} for {id}: {e}")
            return None
    
    def populate_instance(self, instance, uri: Node):
        """
        Popolamento generico basato su property_mapping.
        Popola SOLO predicati dei namespace ammessi.
        Traccia SOLO le triple effettivamente applicate.
        """
        
        # Step 1: Identifier
        if isinstance(uri, URIRef):
            instance.set_has_identifier(str(uri))
        elif isinstance(uri, BNode):
            instance.has_identifier = str(uri)
        
        # Inizializza set di triple
        if instance not in self._triples_map:
            self._triples_map[instance] = set()
        
        # Step 2: Itera su proprietà
        for predicate, obj in self.graph.predicate_objects(uri):
            
            # FILTRO NAMESPACE: Solo predicati dei namespace ammessi popolano il modello
            predicate_str = str(predicate)
            predicate_namespace = predicate_str.rsplit('#', 1)[0] + '#' if '#' in predicate_str else predicate_str.rsplit('/', 1)[0] + '/'
            
            if predicate_namespace not in self._allowed_namespaces:
                # Non popolare - diventerà Statement in phase6
                continue
            
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
                        try:
                            handler(instance, uri, predicate, obj, None)
                            # Traccia SOLO se applicata con successo
                            self._triples_map[instance].add((uri, predicate, obj))
                        except Exception as e:
                            print(f"  Errore handler {handler_name}: {e}")
                            # NON tracciare - diventerà Statement
                        continue
                
                # Setters
                if 'setters' in config:
                    try:
                        self._apply_setters(instance, config['setters'], obj)
                        # Traccia SOLO se applicata
                        self._triples_map[instance].add((uri, predicate, obj))
                    except Exception as e:
                        print(f"  Errore setters: {e}")
                        # NON tracciare - diventerà Statement
                    continue
            
            # FALLBACK: Collection generica (solo se NON mappata)
            if self._is_rdf_collection(obj):
                self._handle_collection_object(instance, predicate, obj)
                # Traccia come applicata
                self._triples_map[instance].add((uri, predicate, obj))

    # ========= HELPERS ======================

    def _is_triple_mapped(self, subj, pred, obj) -> bool:
        """
        Check se tripla già gestita.
        Una tripla è mappata SOLO se esiste nel _triples_map.
        """

        
        # Se soggetto non esiste in cache, non è mappato
        if subj not in self._instance_cache:
            return False
        
        # Verifica se tripla è nel _triples_map
        instances = self._instance_cache[subj]
        instances_list = instances if isinstance(instances, set) else [instances]
        
        for instance in instances_list:
            if instance in self._triples_map:
                if (subj, pred, obj) in self._triples_map[instance]:
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
        
        statement = Statement()
        
        # Crea un BNode come identificatore (approccio RDF standard)
        stmt_bnode = BNode()
        statement.set_has_identifier(str(stmt_bnode))
        
        # TRACCIA e salva LA TRIPLA per lo Statement
        if statement not in self._triples_map:
            self._triples_map[statement] = set()
        self._triples_map[statement].add((subj, pred, obj))
        
        # Subject
        subj_obj = self.get_or_create(subj, Resource)
        if subj_obj:
            statement.set_has_subject(subj_obj)
        
        # Predicate
        pred_inst = self.get_or_create(pred, Property)
        if pred_inst:
            statement.set_has_predicate(pred_inst)
        
        # Object
        if self._is_rdf_collection(obj):
            obj_inst = self._convert_collection_to_container(obj)
        elif isinstance(obj, RDFlibLiteral):
            obj_inst = self._create_literal(obj)
        else:
            obj_inst = self.get_or_create(obj, Resource)
        
        if obj_inst:
            statement.set_has_object(obj_inst)
        
        # Cache statement usando il BNode come chiave
        if stmt_bnode not in self._instance_cache:
            self._instance_cache[stmt_bnode] = set()
        self._instance_cache[stmt_bnode].add(statement)
        
        
    # call by the config file
    # def handle_range(self, instance, uri, predicate, obj, setter=None):
    #     """
    #     Handler intelligente per rdfs:range:
    #     - Relation → crea Concept
    #     - Property/Attribute → crea Resource
    #     """
    #     if isinstance(instance, Relation):
    #         # Relation vuole Concept
    #         range_obj = self.get_or_create(obj, Concept)
    #         if range_obj:
    #             instance.set_has_range(range_obj)
        
    #     elif isinstance(instance, (Property, Attribute)):
    #         # Property/Attribute vuole Resource
    #         range_obj = self.get_or_create(obj, Resource)
    #         if range_obj:
    #             instance.set_has_range(range_obj)