"""
Logic package - For parsing specific Semantic Artefacts logics
"""

from lode.reader.logic.base_logic import BaseLogic
from lode.reader.logic.owl_logic import OwlLogic
from lode.reader.logic.rdf_logic import RdfLogic
from lode.reader.logic.skos_logic import SkosLogic

__all__ = [
    'BaseLogic',
    'OwlLogic',
    'RdfLogic',
    'SkosLogic'
]