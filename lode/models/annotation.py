"""Annotation: an owl:AnnotationProperty."""
from .property import Property

class Annotation(Property):
    """An annotation property: it carries documentation, not logical meaning."""

    def __init__(self, **kwargs):
        """Create an annotation property; all state comes from Property."""
        super().__init__(**kwargs)