"""Viewer for OWL artefacts."""
from typing import Dict, Optional
from lode.viewer.base_viewer import BaseViewer

class OwlViewer(BaseViewer):
    """OWL viewer"""

    TYPE_MAP = {
        'concept':    {'singular': 'Class',                'plural': 'Classes',               'abb': 'c'},
        'relation':   {'singular': 'Object Property',      'plural': 'Object Properties',     'abb': 'op'},
        'attribute':  {'singular': 'Data Property',        'plural': 'Data Properties',       'abb': 'dp'},
        'annotation': {'singular': 'Annotation Property',  'plural': 'Annotation Properties', 'abb': 'ap'},
        'individual': {'singular': 'Named Individual',     'plural': 'Named Individuals',     'abb': 'ni'},
    }

    def get_toc_config(self):
        """Return the table of contents: (class name, section id, TYPE_MAP key) in display order."""
        return [
            ('Concept',    'concepts',    'Concept'),
            ('Relation',   'relations',   'Relation'),
            ('Attribute',  'attributes',  'Attribute'),
            ('Individual', 'individuals', 'Individual'),
            ('Annotation', 'annotations', 'Annotation'),
        ]
        

    def get_view_data(self, resource_uri: Optional[str] = None, language: Optional[str] = None) -> Dict:
        """Build the template data for one resource, or for the whole ontology grouped by entity type.

        Both views also carry the ontology metadata and the TYPE_MAP of display names.
        """

        anguage = language.strip() if language else "en"
        
        all_instances = self.get_all_instances()
        metadata_dict = self._find_and_format_metadata(all_instances, language)

        if resource_uri:
            data = super().get_view_data(resource_uri, language)
        else:
            data = self._build_grouped_view(self.get_toc_config(), language)

        data['metadata'] = metadata_dict
        data['type_map'] = self.TYPE_MAP
        return data