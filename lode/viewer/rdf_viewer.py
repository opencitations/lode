# viewer/rdf_viewer.py
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
        all_instances = self.get_all_instances()
        metadata_dict = self._find_and_format_metadata(all_instances, language)

        if resource_uri:
            data = super().get_view_data(resource_uri, language)
            data['metadata'] = metadata_dict
            data['type_map'] = self.TYPE_MAP
            return data

        # title in SINGOLARE per matchare le chiavi di TYPE_MAP
        toc_config = [
            ('Concept',   'concepts',   'Concept'),
            ('Property',  'properties', 'Property'),
            ('Container', 'containers', 'Container'),
        ]

        data = self._build_grouped_view(toc_config, language)
        data['metadata'] = metadata_dict
        data['type_map'] = self.TYPE_MAP

        # DEBUG — togliere dopo
        print("=" * 60)
        print(f"DEBUG RDF VIEWER")
        print(f"  grouped_view = {data.get('grouped_view')}")
        print(f"  sections count = {len(data.get('sections') or [])}")
        for s in data.get('sections') or []:
            print(f"    [{s['id']}] title={s['title']!r}  entities={len(s['entities'])}")
        print(f"  type_map keys = {list(data['type_map'].keys())}")
        # Conta i tipi reali nel cache
        from collections import Counter
        types = Counter(type(i).__name__ for i in self.get_all_instances())
        print(f"  instances by type = {dict(types)}")
        print("=" * 60)

        return data