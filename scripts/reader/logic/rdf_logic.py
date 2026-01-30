# logic/rdf_logic.py
from rdflib import Graph, URIRef, Node, Literal as RDFlibLiteral, BNode
from rdflib.namespace import RDF, RDFS, OWL, SKOS, XSD
from rdflib.collection import Collection as RDFLibCollection

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from models import *
from reader.logic.base_logic import BaseLogic, ALLOWED_CLASSES


class RdfLogic(BaseLogic):
    """
    Logica RDF pura.
    
    Comportamento:
    - TUTTE le triple non mappate → Statement (phase6)
    - Predicati → Property
    - Soggetti/Oggetti non classificati → Resource
    - Type mapping per rdf:Property, rdf:Statement, etc.
    """
    
    def __init__(self, graph, instance_cache, strategy):
        super().__init__(graph, instance_cache, strategy)
        self._statements_created = set()
        self._statement_counter = 0
    
    def _get_allowed_classes(self) -> set:
        """RDF puro ammette solo classi essenziali"""
        return ALLOWED_CLASSES['RDF']
    
    def _get_allowed_namespaces(self) -> set:
        return {str(RDF), str(RDFS)}
    
    def phase1_classify_from_predicates(self):
        print("\n--- FASE 1: Classificazione RDF ---")
        print("  Skip (RDF puro non classifica da predicati)")
    
    def phase2_create_from_types(self):
        """Crea istanze da rdf:type usando type_mapping"""
        print("\n--- FASE 2: Types RDF ---")
        
        type_mapping = self._strategy.get_type_mapping()
        created = 0
        
        for subj, pred, obj in self.graph.triples((None, RDF.type, None)):
            if subj in self._instance_cache:
                continue
            
            # Check se c'è mapping specifico per questo type
            if obj in type_mapping:
                config = type_mapping[obj]
                py_class = config.get('target_class')
                
                if py_class:
                    self.create_empty_instance(subj, py_class)
                    created += 1
        
        print(f"  Creati {created} da rdf:type")
    
    def phase3_populate_properties(self):
        """Popola proprietà delle istanze create"""
        print("\n--- FASE 3: Popolamento RDF ---")
        
        populated = 0
        
        for uri in list(self._instance_cache.keys()):
            if isinstance(uri, str) and uri.startswith("LITERAL::"):
                continue
            
            instances = self._instance_cache[uri]
            instances_list = instances if isinstance(instances, set) else [instances]
            
            for instance in instances_list:
                # Popola solo se NON è uno Statement
                if not isinstance(instance, Statement):
                    self.populate_instance(instance, uri)
                    populated += 1
        
        print(f"  Popolate {populated} istanze")
    
    def phase4_process_group_axioms(self):
        print("\n--- FASE 4: Axioms RDF ---")
        print("  Nessun axiom in RDF puro")
    
    def phase5_fallback(self):
        """
        Fallback RDF:
        - Tutti i predicati → Property
        - Tutti i soggetti/oggetti non classificati → Resource
        """
        print("\n--- FASE 5: Fallback RDF ---")
        
        # 1. Tutti i predicati → Property
        all_predicates = set(self.graph.predicates())
        property_count = 0
        
        # Predicati strutturali RDF da escludere
        exclude_predicates = {RDF.first, RDF.rest, RDF.nil}
        exclude_namespaces = [RDF, RDFS, OWL, SKOS, XSD]
        
        for pred in all_predicates:
            if pred not in self._instance_cache and pred not in exclude_predicates:
                if not any(str(pred).startswith(str(ns)) for ns in exclude_namespaces):
                    self.create_empty_instance(pred, Property)
                    property_count += 1
        
        print(f"  Property: {property_count} predicati")
        
        # 2. Tutti i soggetti non Collection → Resource
        all_subjects = set(self.graph.subjects())
        subject_count = 0
        
        for subj in all_subjects:
            if isinstance(subj, URIRef) and subj not in self._instance_cache:
                # Escludi Collection nodes
                if not self._is_rdf_collection(subj):
                    exclude_namespaces = [RDF, RDFS, OWL, SKOS, XSD]
                    if not any(str(subj).startswith(str(ns)) for ns in exclude_namespaces):
                        self.create_empty_instance(subj, Resource)
                        subject_count += 1
        
        print(f"  Resource (soggetti): {subject_count}")
        
        # 3. Tutti gli oggetti URI non Collection → Resource
        object_count = 0
        
        for s, p, o in self.graph:
            if isinstance(o, URIRef) and o not in self._instance_cache:
                # Escludi Collection nodes
                if not self._is_rdf_collection(o):
                    exclude_namespaces = [RDF, RDFS, OWL, SKOS, XSD]
                    if not any(str(o).startswith(str(ns)) for ns in exclude_namespaces):
                        self.create_empty_instance(o, Resource)
                        object_count += 1
        
        print(f"  Resource (oggetti): {object_count}")
    
    def phase6_create_statements(self):
        """
        Crea Statement per TUTTE le triple non mappate.
        Esclude predicati strutturali Collection.
        """
        print("\n--- FASE 6: Statements RDF ---")
        
        statements_count = 0
        
        # Predicati da escludere completamente
        exclude_predicates = {RDF.first, RDF.rest, RDF.nil, OWL.members, OWL.distinctMembers}
        
        for subj, pred, obj in self.graph:
            # Skip predicati strutturali
            if pred in exclude_predicates:
                continue
            
            # Skip se già mappata
            if self._is_triple_mapped(subj, pred, obj):
                continue
            
            # Crea Statement
            stmt = self._create_statement_for_triple(subj, pred, obj)
            if stmt:
                statements_count += 1
        
        print(f"  Creati {statements_count} Statement")
    
    # ========== HELPER METHODS ==========
    
    def _create_statement_for_triple(self, subj, pred, obj):
        """
        Crea Statement per una tripla.
        
        Subject → Resource (già creato in phase5)
        Predicate → Property (già creato in phase5)
        Object → Resource o Literal
        
        Returns: Statement creato o None se già esistente
        """
        stmt_key = (str(subj), str(pred), str(obj))
        
        if stmt_key in self._statements_created:
            return None
        
        # Crea Statement
        statement = Statement()
        
        # Genera URI univoco come BNode
        self._statement_counter += 1
        stmt_uri = BNode(f"statement_{self._statement_counter}")
        
        # Subject → Resource
        subj_instance = self.get_or_create(subj, Resource)
        if subj_instance:
            statement.set_has_subject(subj_instance)
        
        # Predicate → Property
        pred_instance = self.get_or_create(pred, Property)
        if pred_instance:
            statement.set_has_predicate(pred_instance)
        
        # Object → Literal o Resource
        if isinstance(obj, RDFlibLiteral):
            obj_instance = self._create_literal(obj)
        elif self._is_rdf_collection(obj):
            # Gestione Collection RDF (rdf:List)
            obj_instance = self._handle_collection_as_container(obj)
        else:
            obj_instance = self.get_or_create(obj, Resource)
        
        if obj_instance:
            statement.set_has_object(obj_instance)
        
        # CRITICO: Salva Statement nella cache
        self._instance_cache[stmt_uri] = {statement}
        
        # Marca come creato
        self._statements_created.add(stmt_key)
        
        # CRITICO: Registra SOLO la tripla originale per provenance
        if statement not in self._triples_map:
            self._triples_map[statement] = set()
        
        # Aggiungi SOLO la tripla originale
        self._triples_map[statement].add((subj, pred, obj))
        
        return statement
    
    def _handle_collection_as_container(self, collection_node):
        """
        Gestisce RDF Collection (rdf:List) convertendola in Container.
        NON traccia le triple rdf:first/rest nei triples_map.
        """
        try:
            collection = RDFLibCollection(self.graph, collection_node)
            
            # Crea un Container per rappresentare la lista
            container = Container()
            container.set_has_identifier(str(collection_node))
            
            items = []
            for item in collection:
                if isinstance(item, RDFlibLiteral):
                    items.append(self._create_literal(item))
                else:
                    item_instance = self.get_or_create(item, Resource)
                    if item_instance:
                        items.append(item_instance)
            
            # Aggiungi items al container
            for item in items:
                container.set_has_member(item)
            
            # CRITICO: Salva Container nella cache
            if collection_node not in self._instance_cache:
                self._instance_cache[collection_node] = {container}
            
            # NON tracciare rdf:first/rest - traccia solo triple significative
            if container not in self._triples_map:
                self._triples_map[container] = set()
            
            # Traccia solo triple NON strutturali della Collection
            for s, p, o in self.graph.triples((collection_node, None, None)):
                if p not in {RDF.first, RDF.rest, RDF.nil}:
                    self._triples_map[container].add((s, p, o))
            
            return container
        
        except Exception as e:
            print(f"  Errore gestione Collection: {e}")
            # Fallback: crea Resource
            return self.get_or_create(collection_node, Resource)
    
    # def _is_triple_mapped(self, subj, pred, obj) -> bool:
    #     """
    #     Check se tripla già gestita.
    #     Una tripla è mappata se:
    #     - Il predicato è in property_mapping
    #     - Il soggetto esiste in cache E non è uno Statement fallback
    #     """
    #     # Se predicato è nel property_mapping, è mappato
    #     if pred in self._property_mapping:
    #         return True
        
    #     # Se soggetto non esiste in cache, non è mappato
    #     if subj not in self._instance_cache:
    #         return False
        
    #     # Se soggetto esiste ma è uno Statement, NON è mappato
    #     # (evita loop infinito)
    #     instances = self._instance_cache[subj]
    #     for inst in instances:
    #         if isinstance(inst, Statement):
    #             return False
        
    #     return False