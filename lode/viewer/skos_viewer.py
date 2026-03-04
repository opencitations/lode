# viewer/skos.py
import hashlib
from typing import Dict, Optional, List
from lode.viewer.base_viewer import BaseViewer

class SkosViewer(BaseViewer):
    """Viewer SKOS con visualizzazione LODE-style."""

    def get_view_data(self, resource_uri: Optional[str] = None, language: Optional[str] = None) -> Dict:
        # 1. Single resource detail view
        if resource_uri:
            return super().get_view_data(resource_uri, language)

        # 2. Define the Table of Contents structure for SKOS
        toc_config = [
            ('Collection', 'collections', 'Collections'),
            ('Concept', 'concepts', 'Concepts'),
        ]

        # 3. Build grouped view with SKOS-specific formatting
        return self._build_skos_grouped_view(toc_config, language)

    def _build_skos_grouped_view(self, group_definitions: List, language: Optional[str] = None) -> Dict:
        """Costruisce la vista raggruppata con formattazione SKOS-style."""
        all_instances = self.get_all_instances()
        sections = []

        for class_key, section_id, section_title in group_definitions:
            instances = [
                inst for inst in all_instances 
                if type(inst).__name__ == class_key
            ]

            if instances:
                sections.append({
                    'id': section_id,
                    'title': section_title,
                    'entities': self._format_skos_entities(instances, language)
                })

        return {
            'grouped_view': True,
            'sections': sections
        }

    def _format_skos_entities(self, instances: List, language: Optional[str] = None) -> List[Dict]:
        """Formatta le entità SKOS in stile LODE."""
        entities = []
        
        for instance in instances:
            uri = instance.has_identifier
            safe_id = hashlib.md5(str(uri).encode('utf-8')).hexdigest()
            
            # Get definition
            definition = self._get_definition(instance, language)
            
            # Build SKOS-specific semantic sections
            semantic_sections = []
            
            # === COLLECTION-specific relations ===
            if hasattr(instance, 'has_member') and instance.has_member:
                semantic_sections.append({
                    'title': 'has members',
                    'concepts': self._format_concept_list(instance.has_member, language)
                })
            
            # === CONCEPT-specific relations ===
            # is equivalent to
            if hasattr(instance, 'is_equivalent_to') and instance.is_equivalent_to:
                semantic_sections.append({
                    'title': 'is equivalent to',
                    'concepts': self._format_concept_list(instance.is_equivalent_to, language)
                })
            
            # has super-concepts (broader)
            if hasattr(instance, 'is_sub_concept_of') and instance.is_sub_concept_of:
                semantic_sections.append({
                    'title': 'has super-concepts',
                    'concepts': self._format_concept_list(instance.is_sub_concept_of, language)
                })
            
            # is disjoint with
            if hasattr(instance, 'is_disjoint_with') and instance.is_disjoint_with:
                semantic_sections.append({
                    'title': 'is disjoint with',
                    'concepts': self._format_concept_list(instance.is_disjoint_with, language)
                })
            
            # is related to
            if hasattr(instance, 'is_related_to') and instance.is_related_to:
                semantic_sections.append({
                    'title': 'is related to',
                    'concepts': self._format_concept_list(instance.is_related_to, language)
                })
            
            # Mapping relations
            # has broad match
            if hasattr(instance, 'has_broad_match') and instance.has_broad_match:
                semantic_sections.append({
                    'title': 'has broad match',
                    'concepts': self._format_concept_list(instance.has_broad_match, language)
                })
            
            # has narrow match
            if hasattr(instance, 'has_narrow_match') and instance.has_narrow_match:
                semantic_sections.append({
                    'title': 'has narrow match',
                    'concepts': self._format_concept_list(instance.has_narrow_match, language)
                })
            
            # has exact match
            if hasattr(instance, 'has_exact_match') and instance.has_exact_match:
                semantic_sections.append({
                    'title': 'has exact match',
                    'concepts': self._format_concept_list(instance.has_exact_match, language)
                })
            
            # has close match
            if hasattr(instance, 'has_close_match') and instance.has_close_match:
                semantic_sections.append({
                    'title': 'has close match',
                    'concepts': self._format_concept_list(instance.has_close_match, language)
                })
            
            # has related match
            if hasattr(instance, 'has_related_match') and instance.has_related_match:
                semantic_sections.append({
                    'title': 'has related match',
                    'concepts': self._format_concept_list(instance.has_related_match, language)
                })

            # Extract ALL relations from model (like BaseViewer does)
            relations = {}
            # Attributes to skip (already handled above or not useful to display)
            skip_attrs = {
                'has_identifier', 'has_label', 'has_preferred_label', 'has_definition',
                'has_member',  # Handled in semantic_sections for Collections
                'is_equivalent_to', 'is_sub_concept_of', 'is_disjoint_with', 'is_related_to',
                'has_broad_match', 'has_narrow_match', 'has_exact_match', 'has_close_match', 'has_related_match',
                'is_ordered',  # Boolean, not a relation
            }
            for attr, value in instance.__dict__.items():
                if not attr.startswith('_') and value and attr not in skip_attrs:
                    clean_name = attr.replace('has_', '').replace('is_', '').replace('_', ' ').title()
                    relations[clean_name] = value

            entities.append({
                'type': type(instance).__name__,
                'uri': uri,
                'label': self._get_best_label(instance, language),
                'anchor_id': f"id_{safe_id}",
                'definition': definition,
                'semantic_sections': semantic_sections,
                'relations': relations,
            })

        entities.sort(key=lambda x: (x['label'] or x['uri']).lower())
        return entities

    def _format_concept_list(self, concepts, language: Optional[str]) -> List[Dict]:
        """Formatta una lista di concetti con label e URI."""
        items = []
        concept_list = concepts if isinstance(concepts, (list, set)) else [concepts]
        
        for concept in concept_list:
            if hasattr(concept, 'has_identifier'):
                items.append({
                    'label': self._get_best_label(concept, language),
                    'uri': concept.has_identifier,
                    'anchor_id': f"id_{hashlib.md5(concept.has_identifier.encode()).hexdigest()}"
                })
            elif isinstance(concept, str):
                # External URI
                items.append({
                    'label': concept.split('/')[-1].split('#')[-1],
                    'uri': concept,
                    'anchor_id': None,
                    'external': True
                })
        
        return items

    def _get_definition(self, instance, language: Optional[str]) -> Optional[str]:
        """Estrae la definizione."""
        if hasattr(instance, 'has_definition') and instance.has_definition:
            return self._get_literal_value(instance.has_definition, language)
        return None

    def _get_literal_value(self, value, language: Optional[str]) -> Optional[str]:
        """Estrae il valore stringa da un Literal o lista di Literal."""
        if isinstance(value, (set, list)):
            if language:
                for v in value:
                    if hasattr(v, 'get_has_language') and v.get_has_language() == language:
                        return v.get_has_value() if hasattr(v, 'get_has_value') else str(v)
            for v in value:
                if hasattr(v, 'get_has_value'):
                    return v.get_has_value()
                return str(v)
        elif hasattr(value, 'get_has_value'):
            return value.get_has_value()
        elif value:
            return str(value)
        return None