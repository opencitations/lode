"""Viewer for OWL artefacts."""
from typing import Optional

from lode.viewer.base_viewer import BaseViewer
from lode.viewer.view_data import Value, new_value
from typing import List, Optional


class OwlViewer(BaseViewer):
    """OWL viewer: display names, table of contents and card come from the viewer.yaml of this profile.

    It adds the rendering of class expressions (restrictions, cardinalities,
    boolean combinations), which only OWL has.
    """

    # Model classes that are anonymous class expressions, shown inline as clickable parts.
    _RESTRICTION_TYPES = ["Restriction", "PropertyConceptRestriction", "Quantifier", "Cardinality", "TruthFunction",
                          "OneOf", "Value", "DatatypeRestriction"]

    def _resolve_special(self, obj, value: Value, language=None) -> Optional[Value]:
        """Render a class expression as a Value made of clickable parts; None for any other value.

        The blank node of the expression is never linked: its parts carry the links.
        """
        obj_type = type(obj).__name__
        if obj_type not in self._RESTRICTION_TYPES:
            return None

        is_dep = getattr(obj, 'get_is_deprecated')() if hasattr(obj, 'get_is_deprecated') else getattr(
            obj, 'is_deprecated', False)
        parts = self._parse_restriction(obj, language)   # recursively, into clickable parts

        value['deprecated'] = bool(is_dep)
        value['parts'] = parts
        value['text'] = "".join(p['text'] for p in parts if p['text'])
        value['type'] = obj_type
        return value

    def _parse_restriction(self, obj, language=None, _seen=None) -> List[Value]:
        """
        Recursively unpacks nested restrictions into a list of display parts
        Guards against cyclic class expressions (possible once owl:imports
        completes cross-ontology definitions) via a visited set.
        """
        if not obj: return []

        if _seen is None:
            _seen = set()

        # 1. Handle lists of restrictions/concepts (e.g., in TruthFunctions or OneOf)
        if isinstance(obj, list) or isinstance(obj, set):
            parts = []
            for i, item in enumerate(obj):
                if i > 0:
                    parts.append(new_value(text=', '))
                parts.extend(self._parse_restriction(item, language, _seen))
            return parts

        obj_type = type(obj).__name__

        # 2. If it is a Restriction, recursively unpack its specific components
        if obj_type in self._RESTRICTION_TYPES:
            # cycle guard: a class expression already being expanded upstream
            if id(obj) in _seen:
                return [new_value(text='…')]
            _seen.add(id(obj))

            parts = []

            # Helper to safely call getter methods (e.g., get_applies_on_property)
            def _get(entity, prop_name, default=None):
                """Read a property through its getter, or directly as an attribute, with a default for None."""
                getter = f"get_{prop_name}"
                if hasattr(entity, getter):
                    res = getattr(entity, getter)()
                    return res if res is not None else default
                return getattr(entity, prop_name, default)

            if obj_type == "Quantifier":
                prop = _get(obj, 'applies_on_property')
                quant = _get(obj, 'has_quantifier_type', "some")
                concept = _get(obj, 'applies_on_concept')

                # Safely check if the is_inverse flag is True
                is_inv = obj.get_is_inverse() if hasattr(obj, 'get_is_inverse') else getattr(obj, 'is_inverse', False)
                if is_inv:
                    parts.append(new_value(text='inverse of ', type='Text'))

                parts.extend(self._parse_restriction(prop, language, _seen))
                parts.append(new_value(text=f' {quant} '))
                parts.extend(self._parse_restriction(concept, language, _seen))

            elif obj_type == "Cardinality":
                prop = _get(obj, 'applies_on_property')
                card = _get(obj, 'has_cardinality_type', "exactly")
                card_num = _get(obj, 'has_cardinality')
                concept = _get(obj, 'applies_on_concept')

                # Safely check if the is_inverse flag is True
                is_inv = obj.get_is_inverse() if hasattr(obj, 'get_is_inverse') else getattr(obj, 'is_inverse', False)
                if is_inv:
                    parts.append(new_value(text='inverse of ', type='Text'))

                parts.extend(self._parse_restriction(prop, language, _seen))
                parts.append(new_value(text=f' {card} {card_num}'))
                parts.extend(self._parse_restriction(concept, language, _seen))

            elif obj_type == "TruthFunction":
                operator = _get(obj, 'has_logical_operator', "and")
                concepts = _get(obj, 'applies_on_concept', [])
                if not isinstance(concepts, list): concepts = [concepts]

                # Safely check if the is_inverse flag is True
                is_inv = obj.get_is_inverse() if hasattr(obj, 'get_is_inverse') else getattr(obj, 'is_inverse', False)
                if is_inv:
                    parts.append(new_value(text='inverse of ', type='Text'))

                parts.append(new_value(text='('))
                for i, c in enumerate(concepts):
                    if i > 0:
                        parts.append(new_value(text=f' {operator} '))
                    parts.extend(self._parse_restriction(c, language, _seen))
                parts.append(new_value(text=')'))

            elif obj_type == "OneOf":
                resources = _get(obj, 'applies_on_resource', [])
                if not isinstance(resources, list): resources = [resources]

                # Safely check if the is_inverse flag is True
                is_inv = obj.get_is_inverse() if hasattr(obj, 'get_is_inverse') else getattr(obj, 'is_inverse', False)
                if is_inv:
                    parts.append(new_value(text='inverse of ', type='Text'))

                parts.append(new_value(text='one of { '))
                for i, r in enumerate(resources):
                    if i > 0:
                        parts.append(new_value(text=', '))
                    parts.extend(self._parse_restriction(r, language, _seen))
                parts.append(new_value(text=' }'))

            elif obj_type == "Value":
                prop = _get(obj, 'applies_on_property')
                resource = _get(obj, 'applies_on_resource')

                # Safely check if the is_inverse flag is True
                is_inv = obj.get_is_inverse() if hasattr(obj, 'get_is_inverse') else getattr(obj, 'is_inverse', False)
                if is_inv:
                    parts.append(new_value(text='inverse of ', type='Text'))

                parts.extend(self._parse_restriction(prop, language, _seen))
                parts.append(new_value(text=' value '))
                parts.extend(self._parse_restriction(resource, language, _seen))

            elif obj_type == "DatatypeRestriction":
                concept = _get(obj, 'applies_on_concept')
                facets = _get(obj, 'has_facets', [])

                # Safely check if the is_inverse flag is True
                is_inv = obj.get_is_inverse() if hasattr(obj, 'get_is_inverse') else getattr(obj, 'is_inverse', False)
                if is_inv:
                    parts.append(new_value(text='inverse of ', type='Text'))

                parts.extend(self._parse_restriction(concept, language, _seen))
                if facets:
                    parts.append(new_value(text='[', type='Text'))
                    for i, (constraint, value) in enumerate(facets):
                        if i > 0:
                            parts.append(new_value(text=', ', type='Text'))
                        parts.append(new_value(text=f'{constraint} ', type='Text'))
                        parts.extend(self._parse_restriction(value, language, _seen))
                    parts.append(new_value(text=']', type='Text'))

            return parts

        # 3. Base Case: We hit a non-blank node (Concept, Relation, String)
        # Send it to the main resolver to extract its URI link and clean text.
        resolved = self._resolve_resource_value(obj, language)
        return [resolved] if resolved['text'] else []
