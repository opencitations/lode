"""Viewer for RDF/RDFS artefacts."""
from typing import Dict, Optional
from lode.viewer.base_viewer import BaseViewer


class RdfViewer(BaseViewer):
    """Viewer RDF / RDFS"""

    TYPE_MAP = {
        'concept':   {'singular': 'Class',     'plural': 'Classes',     'abb': 'c'},
        'property':  {'singular': 'Property',  'plural': 'Properties',  'abb': 'p'},
        'container': {'singular': 'Container', 'plural': 'Containers',  'abb': 'cont'},
        'resource':  {'singular': 'Resource',  'plural': 'Resources',   'abb': 'r'},
        'model':     {'singular': 'Vocabulary','plural': 'Vocabularies','abb': 'v'},
    }

    def get_view_data(self, resource_uri: Optional[str] = None, language: Optional[str] = None) -> Dict:
        """Build the template data for one resource, or for the vocabulary grouped by concepts, properties and containers.

        Both views also carry the vocabulary metadata and the TYPE_MAP of display names.
        """

        language = language.strip() if language else "en"
        
        all_instances = self.get_all_instances()
        metadata_dict = self._find_and_format_metadata(all_instances, language)

        if resource_uri:
            data = super().get_view_data(resource_uri, language)
            data['metadata'] = metadata_dict
            data['type_map'] = self.TYPE_MAP
            return data

        # title in SINGULAR to match the TYPE_MAP keys
        toc_config = [
            ('Concept',   'concepts',   'Concept'),
            ('Property',  'properties', 'Property'),
            ('Container', 'containers', 'Container'),
        ]

        data = self._build_grouped_view(toc_config, language)
        data['metadata'] = metadata_dict
        data['type_map'] = self.TYPE_MAP

        return data