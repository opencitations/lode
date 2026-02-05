# viewer/__init__.py

from lode.viewer.base_viewer import BaseViewer
from lode.viewer.owl_viewer import OwlViewer

__all__ = [
    'BaseViewer',
    'OwlViewer'
]

def get_viewer(read_as: str, reader):
    """
    Factory function per creare il viewer appropriato.
    
    Args:
        read_as: Formato ('owl', 'rdf', 'skos')
        reader: Istanza di Reader già popolata
        
    Returns:
        Istanza del viewer appropriato
    """
    if read_as.lower() == 'owl':
        return OwlViewer(reader)
    # To do : add RDFViewer, SKOSViewer
    return BaseViewer(reader)