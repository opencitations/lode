# viewer/owl_viewer.py
from typing import Dict, Optional
from lode.viewer.base_viewer import BaseViewer

class OwlViewer(BaseViewer):
    """Viewer OWL"""

    TYPE_MAP = {
        'concept':    {'singular': 'Class',                'plural': 'Classes',               'abb': 'c'},
        'relation':   {'singular': 'Object Property',      'plural': 'Object Properties',     'abb': 'op'},
        'attribute':  {'singular': 'Data Property',        'plural': 'Data Properties',       'abb': 'dp'},
        'annotation': {'singular': 'Annotation Property',  'plural': 'Annotation Properties', 'abb': 'ap'},
        'individual': {'singular': 'Named Individual',     'plural': 'Named Individuals',     'abb': 'ni'},
        'model':      {'singular': 'Ontology',             'plural': 'Ontologies',            'abb': 'o'},
    }

    def get_view_data(self, resource_uri: Optional[str] = None, language: Optional[str] = None) -> Dict:
        all_instances = self.get_all_instances()
        metadata_dict = self._find_and_format_metadata(all_instances)

        if resource_uri:
            data = super().get_view_data(resource_uri, language)
            data['metadata'] = metadata_dict
            data['type_map'] = self.TYPE_MAP
            return data

        toc_config = [
            ('Annotation', 'annotations', 'Annotation'),
            ('Concept',    'concepts',    'Concept'),
            ('Relation',   'relations',   'Relation'),
            ('Attribute',  'attributes',  'Attribute'),
            ('Individual', 'individuals', 'Individual'),
        ]

        data = self._build_grouped_view(toc_config, language)
        data['metadata'] = metadata_dict
        data['type_map'] = self.TYPE_MAP
        return data