# logic.py - LOGICHE SPECIFICHE PER FORMATO
from rdflib import Graph, URIRef, Node, Literal as RDFlibLiteral, BNode
from rdflib.namespace import RDF, RDFS, OWL, SKOS, XSD
from rdflib.collection import Collection as RDFLibCollection

from lode.models import *
from lode.reader.logic.base_logic import BaseLogic, ALLOWED_CLASSES

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
    
    def _get_allowed_namespaces(self) -> set:
        return {str(RDF), str(RDFS), str(SKOS)}
    
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
                    self.get_or_create(uri, py_class, populate=False)
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