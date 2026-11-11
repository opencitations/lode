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
                if 'setters' in config:
                    for instance in self._instance_cache.get(uri, set()):
                        # constant values only: no RDF object is resolved here
                        self._apply_setters(instance, config['setters'], None)
        
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

    
    # HANDLERS FROM DECLARATIVE MAPPING
    
    def handle_member_list(self, instance, uri, predicate, obj, value):
        """Handle skos:memberList: add every item of the RDF list as a member, in order.

        The list is expanded here because a plain setter would receive the list head, not
        its items. A memberList is ordered by definition, so the collection is flagged as
        ordered. Items get the same class resolution as skos:member (Resource when no phase
        classified them); duplicates are ignored by the Collection setter.
        """
        if not self._is_rdf_collection(obj):
            return False
        for item in RDFLibCollection(self.graph, obj):
            if isinstance(item, RDFlibLiteral):
                continue
            member = self.get_or_create(item, self._resolve_target_class(item, [Concept, Collection]))
            if member:
                instance.set_has_member(member)
        instance.set_is_ordered(True)
