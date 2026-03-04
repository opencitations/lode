# viewer/rdf_viewer.py
from typing import Dict, Optional
from lode.viewer.base_viewer import BaseViewer

class RdfViewer(BaseViewer):
    """Viewer SKOS"""

    def get_view_data(self, resource_uri: Optional[str] = None,  language: Optional[str] = None) -> Dict:
        # 1. Handle single resource (Standard Base logic)
        if resource_uri:
            return super().get_view_data(resource_uri, language)

        # 2. Define the Table of Contents structure
        # Tuple Format: (Reader_Key, HTML_ID, Display_Title)
        toc_config = [
            ('Concept', 'classes', 'Classes'),
            ('Property', 'properties', 'Properties'),
            ('Container', 'containers', 'Containers'),
            ('Datatype', 'datatypes', 'Datatypes'),
            # Statement, Property, Container, Datatype, Literal, Resource, Concept
        ]

        # 3. Delegate to BaseViewer to build the dictionary
        return self._build_grouped_view(toc_config, language)