"""Extraction logic for SKOS artefacts."""
from rdflib import Graph, URIRef, Node, Literal as RDFlibLiteral, BNode
from rdflib.namespace import RDF, RDFS, OWL, SKOS, XSD
from rdflib.collection import Collection as RDFLibCollection

from lode.models import *
from lode.reader.logic.base_logic import BaseLogic

import logging
logger = logging.getLogger(__name__)

class SkosLogic(BaseLogic):
    """
    SKOS logic.

    Differences:
    - Focus on Concept/ConceptScheme
    - skos:broader/narrower relations
    - NO default domain/range
    - NO Restriction, Individual, CompositeClass, Datatype, Attribute
    """
    
    def _get_allowed_namespaces(self) -> set:
        """Return the RDF, RDFS and SKOS namespaces, ignoring the config 'namespaces' key."""
        return {str(RDF), str(RDFS), str(SKOS)}
    
    def phase1_classify_from_predicates(self):
        """Do nothing: in SKOS the class always comes from rdf:type."""
        logger.debug("Phase 1 (SKOS classification): skipped, SKOS uses only rdf:type")
    
    def phase2_create_from_types(self):
        """Create an unpopulated instance for every subject typed with a mapped SKOS type."""
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
        
        logger.debug("Phase 2 (SKOS types): created %d instances", created)
    
    def phase3_populate_properties(self):
        """Fill every cached instance from its triples."""
        for uri in list(self._instance_cache.keys()):
            for instance in list(self._instance_cache[uri]):
                self.populate_instance(instance, uri)
        
        logger.debug("Phase 3 (SKOS population): populated %d cache entries", len(self._instance_cache))
    
    def phase4_process_group_axioms(self):
        """Do nothing: SKOS has no group axioms."""
        logger.debug("Phase 4 (SKOS axioms): no group axioms in SKOS")

    def phase5_fallback(self):
        """Do nothing yet: the SKOS fallback is not implemented."""
        logger.debug("Phase 5 (SKOS fallback): not implemented yet")
    
    # SKOS-specific handlers
    def handle_membership(self, instance, uri, predicate, obj, value):
        """Handle skos:member: add the cached members of a Collection."""
        if not isinstance(instance, Collection):
            return
        
        for obj_uri in self.graph.objects(uri, predicate):
            member_obj = self._instance_cache.get(obj_uri)
            
            if isinstance(member_obj, set):
                member_obj = next(iter(member_obj), None)
            
            if member_obj and isinstance(member_obj, (Model, Concept)):
                instance.set_has_member(member_obj)
    
    def handle_narrower(self, instance, uri, predicate, obj, value):
        """Handle skos:narrower (the inverse of broader): link the concept to its broader concepts."""
        if not isinstance(instance, Concept):
            return
        
        for subj_uri in self.graph.subjects(predicate, uri):
            broader_obj = self._instance_cache.get(subj_uri)
            
            if isinstance(broader_obj, set):
                broader_obj = next(iter(broader_obj), None)
            
            if broader_obj and isinstance(broader_obj, Concept):
                instance.set_is_sub_concept_of(broader_obj)