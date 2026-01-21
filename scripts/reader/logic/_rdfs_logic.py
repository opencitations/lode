# logic.py - LOGICHE SPECIFICHE PER FORMATO
from abc import ABC, abstractmethod
from rdflib import Graph, URIRef, Node, Literal as RDFlibLiteral, BNode
from rdflib.namespace import RDF, RDFS, OWL, SKOS, XSD
from rdflib.collection import Collection as RDFLibCollection

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from models import *
from .base_logic import BaseLogic, ALLOWED_CLASSES

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

