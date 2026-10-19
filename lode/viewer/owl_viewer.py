"""Viewer for OWL artefacts."""
from typing import Optional

from lode.viewer.base_viewer import BaseViewer


class OwlViewer(BaseViewer):
    """OWL viewer: display names, table of contents and card come from config/owl_viewer.yaml.

    It adds the rendering of class expressions (restrictions, cardinalities,
    boolean combinations), which only OWL has.
    """

    CONFIG_NAME = "owl"

    # Model classes that are anonymous class expressions, shown inline as clickable parts.
    _RESTRICTION_TYPES = ["Restriction", "PropertyConceptRestriction", "Quantifier", "Cardinality", "TruthFunction",
                          "OneOf", "Value", "DatatypeRestriction"]

    def _resolve_special(self, obj, handler_dic: dict, language=None) -> Optional[dict]:
        """Render a class expression as clickable parts; None for any other value.

        The blank node of the expression is never linked: its parts carry the links.
        """
        obj_type = type(obj).__name__
        if obj_type not in self._RESTRICTION_TYPES:
            return None

        is_dep = getattr(obj, 'get_is_deprecated')() if hasattr(obj, 'get_is_deprecated') else getattr(
            obj, 'is_deprecated', False)
        handler_dic['is_deprecated'] = bool(is_dep)

        # Recursively parse the restriction into clickable parts
        parts = self._parse_restriction(obj, language)

        handler_dic['parts'] = parts
        handler_dic['text'] = "".join([p['text'] for p in parts if p.get('text')])
        handler_dic['link'] = None  # Forces Jinja to ignore the blank node URI
        handler_dic['is_external'] = False
        handler_dic['is_imported'] = False
        handler_dic['type'] = obj_type
        return handler_dic

    def _parse_restriction(self, obj, language=None, _seen=None) -> list:
        """
        Recursively unpacks nested restrictions into a list of display parts
        (each part being a dict with 'text' and 'link').
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
                    parts.append({'text': ', ', 'link': None})
                parts.extend(self._parse_restriction(item, language, _seen))
            return parts

        obj_type = type(obj).__name__

        # 2. If it is a Restriction, recursively unpack its specific components
        if obj_type in self._RESTRICTION_TYPES:
            # cycle guard: a class expression already being expanded upstream
            if id(obj) in _seen:
                return [{'text': '…', 'link': None}]
            _seen.add(id(obj))

            parts = []

            # Helper to safely call getter methods (e.g., get_applies_on_property)
            def _get(instance, prop_name, default=None):
                """Read a property through its getter, or directly as an attribute, with a default for None."""
                getter = f"get_{prop_name}"
                if hasattr(instance, getter):
                    res = getattr(instance, getter)()
                    return res if res is not None else default
                return getattr(instance, prop_name, default)

            if obj_type == "Quantifier":
                prop = _get(obj, 'applies_on_property')
                quant = _get(obj, 'has_quantifier_type', "some")
                concept = _get(obj, 'applies_on_concept')

                # Safely check if the is_inverse flag is True
                is_inv = obj.get_is_inverse() if hasattr(obj, 'get_is_inverse') else getattr(obj, 'is_inverse', False)
                if is_inv:
                    parts.append({'text': 'inverse of ', 'link': None, 'type': 'Text'})

                parts.extend(self._parse_restriction(prop, language, _seen))
                parts.append({'text': f' {quant} ', 'link': None})
                parts.extend(self._parse_restriction(concept, language, _seen))

            elif obj_type == "Cardinality":
                prop = _get(obj, 'applies_on_property')
                card = _get(obj, 'has_cardinality_type', "exactly")
                card_num = _get(obj, 'has_cardinality')
                concept = _get(obj, 'applies_on_concept')

                # Safely check if the is_inverse flag is True
                is_inv = obj.get_is_inverse() if hasattr(obj, 'get_is_inverse') else getattr(obj, 'is_inverse', False)
                if is_inv:
                    parts.append({'text': 'inverse of ', 'link': None, 'type': 'Text'})

                parts.extend(self._parse_restriction(prop, language, _seen))
                parts.append({'text': f' {card} {card_num}',  'link': None})
                parts.extend(self._parse_restriction(concept, language, _seen))

            elif obj_type == "TruthFunction":
                operator = _get(obj, 'has_logical_operator', "and")
                concepts = _get(obj, 'applies_on_concept', [])
                if not isinstance(concepts, list): concepts = [concepts]

                # Safely check if the is_inverse flag is True
                is_inv = obj.get_is_inverse() if hasattr(obj, 'get_is_inverse') else getattr(obj, 'is_inverse', False)
                if is_inv:
                    parts.append({'text': 'inverse of ', 'link': None, 'type': 'Text'})

                parts.append({'text': '(', 'link': None})
                for i, c in enumerate(concepts):
                    if i > 0:
                        parts.append({'text': f' {operator} ', 'link': None})
                    parts.extend(self._parse_restriction(c, language, _seen))
                parts.append({'text': ')', 'link': None})

            elif obj_type == "OneOf":
                resources = _get(obj, 'applies_on_resource', [])
                if not isinstance(resources, list): resources = [resources]

                # Safely check if the is_inverse flag is True
                is_inv = obj.get_is_inverse() if hasattr(obj, 'get_is_inverse') else getattr(obj, 'is_inverse', False)
                if is_inv:
                    parts.append({'text': 'inverse of ', 'link': None, 'type': 'Text'})

                parts.append({'text': 'one of { ', 'link': None})
                for i, r in enumerate(resources):
                    if i > 0:
                        parts.append({'text': ', ', 'link': None})
                    parts.extend(self._parse_restriction(r, language, _seen))
                parts.append({'text': ' }', 'link': None})

            elif obj_type == "Value":
                prop = _get(obj, 'applies_on_property')
                resource = _get(obj, 'applies_on_resource')

                # Safely check if the is_inverse flag is True
                is_inv = obj.get_is_inverse() if hasattr(obj, 'get_is_inverse') else getattr(obj, 'is_inverse', False)
                if is_inv:
                    parts.append({'text': 'inverse of ', 'link': None, 'type': 'Text'})

                parts.extend(self._parse_restriction(prop, language, _seen))
                parts.append({'text': ' value ', 'link': None})
                parts.extend(self._parse_restriction(resource, language, _seen))

            elif obj_type == "DatatypeRestriction":
                concept = _get(obj, 'applies_on_concept')  # Datatype(xsd:string)
                constraint = _get(obj, 'has_constraint')  # "pattern"
                value = _get(obj, 'has_restriction_value')  #  Literal("[0-9]+")

                # Safely check if the is_inverse flag is True
                is_inv = obj.get_is_inverse() if hasattr(obj, 'get_is_inverse') else getattr(obj, 'is_inverse', False)
                if is_inv:
                    parts.append({'text': 'inverse of ', 'link': None, 'type': 'Text'})

                parts.extend(self._parse_restriction(concept, language, _seen))
                if constraint:
                    parts.append({'text': f' with {constraint} ', 'link': None, 'type': 'Text'})
                else:
                    parts.append({'text': ' restricted by ', 'link': None, 'type': 'Text'})

                parts.extend(self._parse_restriction(value, language, _seen))

            return parts

        # 3. Base Case: We hit a non-blank node (Concept, Relation, String)
        # Send it to the main resolver to extract its URI link and clean text.
        resolved = self._resolve_resource_value(obj, language)

        if resolved.get('text'):
            return [{'text': resolved['text'], 'link': resolved.get('link'), 'type': resolved.get('type'), 'is_external': resolved.get('is_external', False)}]

        return []
