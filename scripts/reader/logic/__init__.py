"""
Logic package - Logiche specifiche per formato RDF
"""

from reader.logic.base_logic import BaseLogic
from reader.logic.owl_logic import OwlLogic
from reader.logic.rdf_logic import RdfLogic
from reader.logic.skos_logic import SkosLogic

__all__ = [
    'BaseLogic',
    'OwlLogic',
    'RdfLogic',
    'SkosLogic'
]