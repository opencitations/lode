# base_logic.py
from abc import ABC, abstractmethod
from rdflib import Graph, URIRef, Node, Literal as RDFlibLiteral, BNode
from rdflib.namespace import RDF, RDFS, OWL, SKOS, XSD
from rdflib.collection import Collection as RDFLibCollection

from lode.models import *

# ========== ALLOWED CLASSES PER FORMATO ==========

# ALLOWED_CLASSES = {
#     'RDF': {
#         Statement, Property, Container, Datatype, Literal, Resource, Concept
#     },
#     'OWL': {
#         Statement, Literal, Relation, Container,
#         Concept, Attribute, Datatype,
#         Individual, Model, Annotation,
#         TruthFunction, Value, OneOf, Quantifier, Cardinality, PropertyConceptRestriction,
#         Collection, Restriction, Resource
#     },
#     'SKOS': {
#         Collection, Literal, Resource,
#         Concept, Model, Datatype
#     }
# }


class BaseLogic(ABC):
    """
    Logica base comune per parsing RDF.
    """

    def __init__(self, graph: Graph, instance_cache: dict, strategy):
        self.graph = graph
        self._instance_cache = instance_cache
        self._strategy = strategy
        self._property_mapping = strategy.get_property_mapping()
        self._allowed_classes = self._get_allowed_classes()
        self._triples_map = {}
        # Namespaces now driven by config YAML (key: 'namespaces')
        self._allowed_namespaces = self._get_allowed_namespaces()
        # Validate all handlers declared in config exist on this instance
        self._validate_handlers()

    # ========== METODI ASTRATTI ==========

    def _get_allowed_classes(self) -> set:
        class_names = self._strategy.config.get('allowed_classes', [])
        return {self._strategy.CLASSES[name] for name in class_names if name in self._strategy.CLASSES}

    def _get_allowed_namespaces(self) -> set:
        """
        Reads namespaces from config YAML key 'namespaces'.
        Subclasses do NOT need to override this anymore.
        """
        return set(self._strategy.config.get('namespaces', []))

    @abstractmethod
    def phase1_classify_from_predicates(self):
        pass

    @abstractmethod
    def phase2_create_from_types(self):
        pass

    @abstractmethod
    def phase3_populate_properties(self):
        pass

    @abstractmethod
    def phase4_process_group_axioms(self):
        pass

    @abstractmethod
    def phase5_fallback(self):
        pass

    def phase6_create_statements(self):
        """Crea Statement per triple non mappate"""
        for subj, pred, obj in self.graph:
            if pred not in [RDF.first, RDF.rest, RDF.nil, OWL.distinctMembers, OWL.members]:
                if self._is_triple_mapped(subj, pred, obj):
                    continue
                self._create_statement_for_triple(subj, pred, obj)

    # ========== VALIDAZIONE CONFIG -> LOGIC ==========

    def _validate_handlers(self):
        """
        Fail-fast: verifica che tutti gli handler dichiarati nel config
        esistano come metodi su questa istanza Logic.
        Solleva AttributeError subito, prima di qualsiasi parsing.
        """
        errors = []

        for uri_str, cfg in self._strategy.config.get('mapper', {}).items():
            handler_name = cfg.get('handler')
            if handler_name and not hasattr(self, handler_name):
                errors.append(
                    f"mapper['{uri_str}'].handler='{handler_name}' "
                    f"not found on {type(self).__name__}"
                )

        for uri_str, handler_name in self._strategy.config.get('enricher', {}).items():
            if isinstance(handler_name, str) and not hasattr(self, handler_name):
                errors.append(
                    f"enricher['{uri_str}']='{handler_name}' "
                    f"not found on {type(self).__name__}"
                )

        if errors:
            raise AttributeError(
                f"Config/Logic contract violations in {type(self).__name__}:\n"
                + "\n".join(f"  - {e}" for e in errors)
            )

    # ========== RISOLUZIONE CLASSI AMMESSE ==========

    def _resolve_allowed_class(self, python_class: type, id: Node = None) -> type:
        """
        Resolves a Python class to one allowed by the current format, by walking
        the MRO until a class present in _allowed_classes is found.
        Before the MRO walk, calls _pre_resolve_hook to allow subclasses to
        short-circuit resolution with custom logic (e.g. reusing an existing
        cached type instead of silently downcasting).
        Falls back to Resource if nothing is found.
        """
        if python_class in self._allowed_classes:
            return python_class

        # Hook per logica custom pre-MRO (es. OWL: controlla cache)
        resolved = self._pre_resolve_hook(python_class, id)
        if resolved:
            return resolved

        for parent_class in python_class.__mro__[1:]:
            if parent_class in self._allowed_classes:
                return parent_class

        print(f"  [WARN] {python_class.__name__} -> Resource (fallback finale)")
        return Resource

    def _pre_resolve_hook(self, python_class: type, id: Node) -> type | None:
        """
        Hook opzionale per logica custom pre-MRO.
        Le subclass possono override senza toccare _resolve_allowed_class.
        Ritorna None per delegare al comportamento base.
        """
        return None

    # ========== UTILITIES ==========

    def _traverse_hierarchy(
        self,
        start: object,
        next_getter: str,
        direction: str = "up",          # "up" | "down" | "both"
        collect: callable = None,       # (node) -> value | None  — ferma e ritorna quando non None
        visit_all: callable = None,     # (node) -> None          — visita ogni nodo senza fermarsi
    ) -> object | None:
        """
        Generic BFS traversal along a property hierarchy.

        Parameters
        ----------
        start        : starting node (Python model instance)
        next_getter  : name of the getter that returns the next nodes in the
                    'up' direction (e.g. 'get_is_sub_property_of').
                    For 'down' the cache is scanned for instances that list
                    `start` as one of their `next_getter` targets.
        direction    : 'up'   - follow next_getter only
                    'down' - scan cache for reverse links only
                    'both' - up first, then down
        collect      : callable(node) -> value | None
                    Called on every visited node (including start).
                    When it returns a non-None value the traversal stops
                    immediately and that value is returned.
        visit_all    : callable(node) -> None
                    Called on every visited node; traversal never stops early.
                    Mutually exclusive with collect (collect takes priority).

        Returns the first non-None value from collect, or None if visit_all is used.
        """
        visited = set()
        queue = [start]
        result = None

        while queue:
            current = queue.pop(0)
            if id(current) in visited:
                continue
            visited.add(id(current))

            # --- collect / visit ---
            if collect:
                value = collect(current)
                if value is not None:
                    return value
            elif visit_all:
                visit_all(current)

            # --- enqueue next nodes ---
            if direction in ("up", "both"):
                getter = getattr(current, next_getter, None)
                if getter:
                    nexts = getter()
                    if nexts:
                        if not isinstance(nexts, list):
                            nexts = [nexts]
                        queue.extend(nexts)

            if direction in ("down", "both"):
                for instances_set in self._instance_cache.values():
                    for inst in instances_set:
                        if inst is current or id(inst) in visited:
                            continue
                        getter = getattr(inst, next_getter, None)
                        if getter:
                            parents = getter() or []
                            if not isinstance(parents, list):
                                parents = [parents]
                            if any(p is current for p in parents):
                                queue.append(inst)

        return None

    # def is_in_range_or_domain_of_property(self, property_getter, property_getter_inverse, property_instance):

    #     if isinstance(object, (Concept, Individual, Datatype)):
    #         obj_inst = property_instance.property_getter()
    #         obj_inst.property_getter_inverse()


    def _create_literal(self, rdflib_literal):
        literal_key = f"LITERAL::{rdflib_literal}"
        if literal_key in self._instance_cache:
            return next(iter(self._instance_cache[literal_key]))

        literal = Literal()
        literal.set_has_value(str(rdflib_literal))

        if rdflib_literal.language:
            literal.set_has_language(rdflib_literal.language)

        if rdflib_literal.datatype:
            dt = self.get_or_create(rdflib_literal.datatype, Datatype)
            if dt:
                literal.set_has_type(dt)

        self._instance_cache[literal_key] = {literal}
        return literal

    def _is_rdf_collection(self, node: Node) -> bool:
        return (node, RDF.first, None) in self.graph

    def _instance_matches_target(self, instance, target_classes: list) -> bool:
        instance_class = instance.__class__
        if instance_class in target_classes:
            return True
        for parent_class in instance_class.__mro__[1:]:
            if parent_class in target_classes:
                return True
        return False

    def _apply_setters(self, instance, setters_config, obj):
        for setter_item in setters_config:
            if isinstance(setter_item, dict):
                for setter_name, value_type in setter_item.items():
                    if not hasattr(instance, setter_name):
                        continue
                    setter = getattr(instance, setter_name)
                    if value_type == 'Literal':
                        try:
                            setter(self._create_literal(obj))
                        except:
                            continue
                    elif isinstance(value_type, bool):
                        setter(value_type)
                    elif isinstance(value_type, str):
                        setter(value_type)
                    elif isinstance(value_type, type):
                        obj_instance = self.get_or_create(obj, value_type)
                        if obj_instance:
                            setter(obj_instance)
                    else:
                        setter(obj)
            else:
                if hasattr(instance, setter_item):
                    getattr(instance, setter_item)()

    def _handle_collection_object(self, instance, predicate, collection_uri):
        try:
            collection = RDFLibCollection(self.graph, collection_uri)
            items = []
            for item in collection:
                if isinstance(item, RDFlibLiteral):
                    items.append(self._create_literal(item))
                else:
                    item_instance = self.get_or_create(item, Resource)
                    if item_instance:
                        items.append(item_instance)

            config = self._property_mapping.get(predicate, {})
            for setter_item in config.get('setters', []):
                if isinstance(setter_item, dict):
                    for setter_name in setter_item:
                        if hasattr(instance, setter_name):
                            getattr(instance, setter_name)(items)
                            break
        except Exception as e:
            print(f"Errore Collection: {e}")

    def clear_cache(self):
        self._instance_cache.clear()

    # ========== LOGIC CORE ==========

    def get_or_create(self, id: Node, python_class: type = None, populate: bool = True):
        try:
            
            if isinstance(id, RDFlibLiteral):
                return self._create_literal(id)

            if isinstance(id, URIRef) and str(id).startswith(str(XSD)):
                python_class = Datatype

            if python_class:
                python_class = self._resolve_allowed_class(python_class, id)

            if isinstance(id, URIRef):
                uri_str = str(id)
                for ns in self._allowed_namespaces:
                    if uri_str.startswith(ns) and id not in (OWL.Thing, OWL.Nothing, RDFS.Literal):
                        return None

            # Individual punning: non sovrascrivere tipi esistenti non-Individual
            if python_class == Individual and id in self._instance_cache:
                is_named_individual = (id, RDF.type, OWL.NamedIndividual) in self.graph
                if not is_named_individual:
                    for existing in self._instance_cache[id]:
                        if not isinstance(existing, Individual):
                            return existing

            if id in self._instance_cache:
                if isinstance(id, BNode):
                    return next(iter(self._instance_cache[id]))
                if isinstance(id, URIRef):
                    for obj in self._instance_cache[id]:
                        if isinstance(obj, python_class):
                            return obj

            instance = python_class()
            if id not in self._instance_cache:
                self._instance_cache[id] = set()
            self._instance_cache[id].add(instance)
            instance.set_has_identifier(str(id))

            if populate:
                self.populate_instance(instance, id)

            return instance

        except Exception as e:
            print(f"Cannot create {python_class.__name__ if python_class else 'Unknown'} for {id}: {e}")
            return None

    def populate_instance(self, instance, uri: Node):
        if isinstance(uri, URIRef):
            instance.set_has_identifier(str(uri))
        elif isinstance(uri, BNode):
            instance.has_identifier = str(uri)

        if instance not in self._triples_map:
            self._triples_map[instance] = set()

        for predicate, obj in self.graph.predicate_objects(uri):
            predicate_str = str(predicate)
            predicate_namespace = (
                predicate_str.rsplit('#', 1)[0] + '#'
                if '#' in predicate_str
                else predicate_str.rsplit('/', 1)[0] + '/'
            )

            if predicate_namespace not in self._allowed_namespaces:
                continue

            if predicate in self._property_mapping:
                config = self._property_mapping[predicate]

                target_classes = config.get('target_classes', [])
                if target_classes and not self._instance_matches_target(instance, target_classes):
                    continue

                if 'handler' in config:
                    handler_name = config['handler']
                    # handler existence already guaranteed by _validate_handlers
                    handler = getattr(self, handler_name)
                    try:
                        handler(instance, uri, predicate, obj, None)
                        self._triples_map[instance].add((uri, predicate, obj))
                    except Exception as e:
                        print(f"  Errore handler {handler_name}: {e}")
                    continue

                if 'setters' in config:
                    try:
                        self._apply_setters(instance, config['setters'], obj)
                        self._triples_map[instance].add((uri, predicate, obj))
                    except Exception as e:
                        print(f"  Errore setters: {e}")
                    continue

            if self._is_rdf_collection(obj):
                self._handle_collection_object(instance, predicate, obj)
                self._triples_map[instance].add((uri, predicate, obj))

    # ========== HELPERS ==========

    def _is_triple_mapped(self, subj, pred, obj) -> bool:
        if subj not in self._instance_cache:
            return False
        instances = self._instance_cache[subj]
        instances_list = instances if isinstance(instances, set) else [instances]
        for instance in instances_list:
            if instance in self._triples_map:
                if (subj, pred, obj) in self._triples_map[instance]:
                    return True
        return False

    def _convert_collection_to_container(self, collection_uri):
        if collection_uri in self._instance_cache:
            for cached in self._instance_cache[collection_uri]:
                if isinstance(cached, Container):
                    return cached

        container = Container()
        container.set_has_identifier(str(collection_uri))

        if collection_uri not in self._instance_cache:
            self._instance_cache[collection_uri] = set()
        self._instance_cache[collection_uri].add(container)

        try:
            collection = RDFLibCollection(self.graph, collection_uri)
            members = []
            for item in collection:
                if isinstance(item, RDFlibLiteral):
                    members.append(self._create_literal(item))
                else:
                    member_instance = self.get_or_create(item, Resource)
                    if member_instance:
                        members.append(member_instance)
            container.set_has_members(members)
        except Exception as e:
            print(f"Errore Collection: {e}")

        return container

    def _create_statement_for_triple(self, subj, pred, obj):
        statement = Statement()
        stmt_bnode = BNode()
        statement.set_has_identifier(str(stmt_bnode))

        if statement not in self._triples_map:
            self._triples_map[statement] = set()
        self._triples_map[statement].add((subj, pred, obj))

        subj_obj = self.get_or_create(subj, Resource)
        if subj_obj:
            statement.set_has_subject(subj_obj)

        pred_inst = self.get_or_create(pred, Property)
        if pred_inst:
            statement.set_has_predicate(pred_inst)

        if self._is_rdf_collection(obj):
            obj_inst = self._convert_collection_to_container(obj)
        elif isinstance(obj, RDFlibLiteral):
            obj_inst = self._create_literal(obj)
        else:
            obj_inst = self.get_or_create(obj, Resource)

        if obj_inst:
            statement.set_has_object(obj_inst)

        if stmt_bnode not in self._instance_cache:
            self._instance_cache[stmt_bnode] = set()
        self._instance_cache[stmt_bnode].add(statement)