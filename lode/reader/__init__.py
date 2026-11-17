"""
Reader package - Main entry point for loading, reading and processing Semantic Artefacts
"""

from lode.reader.pipeline import read_into
from lode.reader.loader import Loader
from lode.reader import modules

__all__ = ['Loader',
           'read_into',
           'modules',
           ]
