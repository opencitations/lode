"""Extraction logic for RDF/RDFS artefacts."""

from rdflib import URIRef, Node, Literal as RDFlibLiteral, BNode
from rdflib.namespace import RDF, RDFS, OWL, SKOS, XSD
from rdflib.collection import Collection as RDFLibCollection

from lode.models import *
from lode.reader.logic.base_logic import BaseLogic

import logging
logger = logging.getLogger(__name__)


class RdfLogic(BaseLogic):
    """
    RDF/RDFS parsing logic.

    Behavior:
    - Phase1: classify URIRef subjects of mapped predicates whose config
      declares inferred_class or a single target_classes (mirrors OwlLogic).
      BNodes with inferred_class are classified too (e.g. reified Statements
      via rdf:subject/predicate/object).
    - Phase2: create instances from rdf:type using type_mapping; static
      setters declared in 'is: class' entries are applied immediately.
    - Phase3: populate via setters/handlers from the property mapping.
    - Phase4: no group axioms in pure RDF/RDFS.
    - Phase5: fallback - all unmapped predicates -> Property, all unmapped
      URI subjects/objects -> Resource, then RDFS defaults applied to every
      Property (rdfs:Resource for domain, rdfs:Class for range) climbing the
      rdfs:subPropertyOf hierarchy first.
    - Phase6: inherited from BaseLogic, reifies unmapped triples as Statements.
    """

    # ========== READER PHASES ==========

    # ========== HELPERS ==========