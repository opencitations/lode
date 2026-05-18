# viewer/__init__.py

from .base_viewer import BaseViewer
from .owl_viewer import OwlViewer
from .rdf_viewer import RdfViewer
from .skos_viewer import SkosViewer

__all__ = [
    'BaseViewer',
    'OwlViewer',
    'RdfViewer',
    'SkosViewer',
]


def get_viewer(read_as: str, reader):
    """Factory per il viewer corretto in base al formato."""
    key = read_as.lower()
    if key == 'owl':
        return OwlViewer(reader)
    if key in ('rdf', 'rdfs'):
        return RdfViewer(reader)
    if key == 'skos':
        return SkosViewer(reader)
    return BaseViewer(reader)