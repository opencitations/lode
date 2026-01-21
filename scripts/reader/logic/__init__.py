"""
Logic package - Logiche specifiche per formato RDF
"""

from .base_logic import BaseLogic
from .owl_logic import OwlLogic
# from .rdfs_logic import RdfsLogic
from .rdf_logic import RdfLogic
from .skos_logic import SkosLogic

__all__ = [
    'BaseLogic',
    'OwlLogic',
    # 'RdfsLogic',
    'RdfLogic',
    'SkosLogic'
]