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
    
    def phase1_classify_from_predicates(self):
        """Do nothing: in SKOS the class always comes from rdf:type."""
        logger.debug("Phase 1 (SKOS classification): skipped, SKOS uses only rdf:type which is handled in phase 2")

# ==========================================================================
# SKOS-SPECIFIC HANDLERS LOGIC FROM DECLARATIVE MAPPING
# ==========================================================================
    
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
