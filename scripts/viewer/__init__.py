# viewer/__init__.py

from viewer.base_viewer import BaseViewer
from viewer.owl_viewer import OWLViewer

__all__ = [
    'BaseViewer',
    'OWLViewer'
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
        return OWLViewer(reader)
    # To do : add RDFViewer, SKOSViewer
    return BaseViewer(reader)