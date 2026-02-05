"""
Reader package - Main entry point for loading, reading and processing Semantic Artefacts
"""

from lode.reader.reader import Reader
from lode.reader.loader import Loader
from lode.reader.config_manager import get_configuration

__all__ = ['Loader',
           'get_configuration',
           'Reader', 
           ]