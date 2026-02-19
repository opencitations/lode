# viewer/owl_viewer.py
from typing import Dict, Optional
from lode.viewer.base_viewer import BaseViewer

class OwlViewer(BaseViewer):
    """Viewer OWL"""

    def get_view_data(self, resource_uri: Optional[str] = None,  language: Optional[str] = None) -> Dict:
        all_instances = self.get_all_instances()
        metadata_dict = self._find_and_format_metadata(all_instances)

        # 1. Handle single resource (Standard Base logic)
        if resource_uri:
            data = super().get_view_data(resource_uri, language)
            data['metadata'] = metadata_dict
            return data

        # 2. Define the Table of Contents structure
        # Tuple Format: (Reader_Key, HTML_ID, Display_Title)
        toc_config = [
            ('Annotation', 'annotations', 'Annotations'),
            ('Concept', 'concepts', 'Concepts'),
            ('Relation', 'relations', 'Relations'), 
            ('Attribute', 'attributes', 'Attributes'),
            ('Individual', 'individual', 'Individuals')
        ]

        # 3. Build the grouped view
        data = self._build_grouped_view(toc_config)
        data['metadata'] = metadata_dict
        return data
