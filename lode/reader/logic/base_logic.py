"""Format-independent core of the extraction logic.

BaseLogic turns the triples of a graph into model instances in phases. What is
specific to OWL, RDF or SKOS lives in the subclasses and in the YAML mapper.
"""
from abc import ABC, abstractmethod
from rdflib import Graph, URIRef, Node, Literal as RDFlibLiteral, BNode
from rdflib.namespace import RDF, RDFS, OWL, SKOS, XSD, Namespace
from rdflib.collection import Collection as RDFLibCollection
from rdflib import Namespace
SWRL_NS = Namespace("http://www.w3.org/2003/11/swrl#")

from lode.models import *
from lode.helpers.rdf import iri_local_name, iri_namespace

import logging
logger = logging.getLogger(__name__)

class BaseLogic(ABC):
    """
    Common base logic for RDF parsing.

    Owns the instance cache, the triples-to-instance provenance map and the
    generic machinery (get_or_create, populate_instance, SWRL, statements);
    subclasses implement the phases that differ between formats.
    """

    def __init__(self, graph: Graph, instance_cache: dict, strategy):
        """Bind the logic to a graph, a shared instance cache and a config manager.

        Fails fast if the config names a handler this logic does not implement.
        """
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
        self._warnings = []

    def add_warning(self, code, subject, message):
        """Record a reader warning with a machine-readable code, its subject and a message."""
        self._warnings.append({'code': code, 'subject': str(subject), 'message': message})

    def get_warnings(self):
        """Return the collected warnings, or [] when they were not requested."""
        if not getattr(self, '_warnings_enabled', False):  # self is the logic here
            return []

    def save_warnings(self, filepath: str = None):
        """Save warnings to JSON file."""
        import json
        from pathlib import Path
        
        if not self._warnings:
            return
        
        if filepath is None:
            filepath = Path(__file__).parent.parent.parent / 'warnings.json'
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self._warnings, f, indent=2, ensure_ascii=False)

    def _get_allowed_classes(self) -> set:
        """Resolve the 'allowed_classes' names of the config into the model classes."""
        class_names = self._strategy.config.get('allowed_classes', [])
        import lode.models as _models
        return {getattr(_models, name) for name in class_names if getattr(_models, name, None) is not None}

    def _get_allowed_namespaces(self) -> set:
        """
        Reads namespaces from config YAML key 'namespaces'.
        Subclasses do NOT need to override this anymore.
        """
        return set(self._strategy.config.get('namespaces', []))
    
    def get_namespaces(self) -> dict:
        """Prefixes declared in the graph (prefix -> URI)."""
        return {prefix: str(ns) for prefix, ns in self.graph.namespaces()}

    @abstractmethod
    def phase1_classify_from_predicates(self):
        """Phase 1: create instances for subjects whose predicates reveal their class."""
        pass

    @abstractmethod
    def phase2_create_from_types(self):
        """Phase 2: create instances from the rdf:type declarations of the graph."""
        pass

    @abstractmethod
    def phase3_populate_properties(self):
        """Phase 3: fill every instance from its triples, through the property mapping."""
        pass

    @abstractmethod
    def phase4_process_group_axioms(self):
        """Phase 4: process axioms that involve several entities at once (e.g. AllDisjointClasses)."""
        pass

    @abstractmethod
    def phase5_fallback(self):
        """Phase 5: give a class (and the format defaults) to whatever is still unclassified."""
        pass

    def phase6_create_statements(self):
        """Phase 6: reify every triple no earlier phase consumed as a Statement.

        Structural list triples and structural vocabulary subjects without a type
        are skipped; triples already tracked by an instance are not duplicated.
        """
        for subj, pred, obj in self.graph:
            # if pred in self._property_mapping:
            #     continue
            if pred in [RDF.first, RDF.rest, RDF.nil, OWL.distinctMembers, OWL.members]:
                continue
            if isinstance(subj, URIRef):
                subj_str = str(subj)
                # structural entities from taken namespaces are not used for statements 
                if any(subj_str.startswith(ns) for ns in self._allowed_namespaces):
                    if not any(True for _ in self.graph.objects(subj, RDF.type)):
                        continue
            if self._is_triple_mapped(subj, pred, obj):
                continue
            self._create_statement_for_triple(subj, pred, obj)

    # ========== CONFIG -> LOGIC VALIDATION ==========

    def _validate_handlers(self):
        """
        Fail-fast: check that every handler declared in the config
        exists as a method on this Logic instance.
        Raises AttributeError immediately, before any parsing.
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

    # ========== ALLOWED CLASS RESOLUTION ==========

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

        # Hook for custom pre-MRO logic (e.g. OWL: check the cache)
        resolved = self._pre_resolve_hook(python_class, id)
        if resolved:
            return resolved

        for parent_class in python_class.__mro__[1:]:
            if parent_class in self._allowed_classes:
                return parent_class

        logger.warning("%s fell back to Resource", python_class.__name__)
        return Resource

    def _pre_resolve_hook(self, python_class: type, id: Node) -> type | None:
        """
        Optional hook for custom pre-MRO logic.
        Subclasses can override it without touching _resolve_allowed_class.
        Returns None to delegate to the base behaviour.
        """
        return None
    
    # ========== Namespaces resolution ==========
    
    def populate_namespaces(self):
        """Attach the graph prefixes to every cached Model."""
        ns = {prefix: str(uri) for prefix, uri in self.graph.namespaces()}
        for instances in self._instance_cache.values():
            for inst in instances:
                if isinstance(inst, Model):
                    inst.set_has_namespaces(ns)

    # ========== PROVENANCE ========== (note: _triples_map is written only by these three methods.)

    def _track(self, instance, *triples):
        """Attribute one or more triples to the provenance of `instance`."""
        self._triples_map.setdefault(instance, set()).update(triples)

    def _untrack(self, instance, *triples):
        """Remove triples from the provenance of `instance`."""
        bucket = self._triples_map.get(instance)
        if bucket:
            bucket.difference_update(triples)

    def _move_tracking(self, old, new):
        """Move the provenance from `old` to `new` when an instance is promoted or replaced."""
        if old in self._triples_map:
            self._triples_map.setdefault(new, set()).update(self._triples_map.pop(old))

    # ========== UTILITIES ==========

    def _traverse_hierarchy(
        self,
        start: object,
        next_getter: str,
        direction: str = "up",          # "up" | "down" | "both"
        collect: callable = None,       # (node) -> value | None  — stops and returns when not None
        visit_all: callable = None,     # (node) -> None          — visits every node without stopping
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
        """Return the model Literal for an rdflib literal, one per distinct lexical form.

        The instance is cached under a LITERAL:: key; language and datatype are
        copied over when present.
        """
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
        """Return True if the node is the head of an RDF list (it has an rdf:first)."""
        return (node, RDF.first, None) in self.graph

    def _instance_matches_target(self, instance, target_classes: list) -> bool:
        """Return True if the instance is of one of the target classes, or a subclass of one."""
        instance_class = instance.__class__
        if instance_class in target_classes:
            return True
        for parent_class in instance_class.__mro__[1:]:
            if parent_class in target_classes:
                return True
        return False

    def _apply_setters(self, instance, setters_config, obj):
        """Call the setters declared in the config on `instance`, using `obj` as the value.

        Per entry: 'Literal' builds a Literal from obj; a bool or a string is passed
        as a constant; a model class resolves obj to an instance of that class (the
        punned instance of the same class if one is cached); anything else passes
        obj as is. An entry with no value calls the setter with no argument.
        Structural vocabulary URIs are never added to has_type.
        """
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
                        # Don't add structural OWL/RDFS/RDF URIs to has_type
                        if setter_name == 'set_has_type' and isinstance(obj, URIRef):
                            obj_str = str(obj)
                            if any(obj_str.startswith(ns) for ns in self._allowed_namespaces) and obj not in (OWL.Thing, OWL.Nothing, RDFS.Literal):
                                continue
                        # punning: prefer the instance of obj with the same class as the subject
                        obj_instance = next(
                            (c for c in self._instance_cache.get(obj, ())
                             if type(c) is type(instance) and isinstance(c, value_type)),
                            None
                        ) or self.get_or_create(obj, value_type)
                        if obj_instance:
                            setter(obj_instance)
                    else:
                        setter(obj)
            else:
                if hasattr(instance, setter_item):
                    getattr(instance, setter_item)()

    def _handle_collection_object(self, instance, predicate, collection_uri):
        """Resolve an RDF list used as an object and pass its members to the first matching setter.

        Failures are logged and swallowed: one malformed list must not stop the read.
        """
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
        except Exception:
            logger.warning("Collection handling failed on %s (predicate %s)",
                           instance, predicate, exc_info=True)

    def clear_cache(self):
        """Empty the shared instance cache."""
        self._instance_cache.clear()

    # ========== LOGIC CORE ==========

    def get_or_create(self, id: Node, python_class: type = None, populate: bool = True):
        """Return the model instance for a node, creating (and populating) it when needed.

        Literals go through _create_literal; built-in datatypes and undeclared XSD
        terms are always Datatype. A cached instance is reused; a single cached
        instance of a broader class is promoted to the requested one, so punning
        keeps working. Returns None, after logging, when creation fails.
        """
        try:
            
            if isinstance(id, RDFlibLiteral):
                return self._create_literal(id)

            DATATYPE_BUILTINS = frozenset({
            RDFS.Literal, RDF.XMLLiteral, RDF.HTML,
            RDF.PlainLiteral, RDF.langString, RDF.JSON,
            OWL.real, OWL.rational
            })

            if isinstance(id, URIRef):
                if id in DATATYPE_BUILTINS:
                    python_class = Datatype  # built-ins: always Datatype, no exceptions
                elif str(id).startswith(str(XSD)) and str(id) != str(XSD):
                    if (id, RDF.type, None) not in self.graph:
                        python_class = Datatype  # XSD: only if explicitly declared as something else

            # if isinstance(id, URIRef):
            #     uri_str = str(id)
            #     for ns in self._allowed_namespaces:
            #         if uri_str.startswith(ns) and id not in (OWL.Thing, OWL.Nothing, RDFS.Literal):
            #             return None

            # Individual punning: do not override existing non-Individual types
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
                    # Promote only if there is exactly one cached instance and
                    # the requested class is strictly more specific than it
                    # so punning is mantained
                    cached = list(self._instance_cache[id])
                    if len(cached) == 1 and issubclass(python_class, type(cached[0])):
                        old = cached[0]
                        new = python_class()
                        new.__dict__.update(old.__dict__)
                        self._instance_cache[id].discard(old)
                        self._instance_cache[id].add(new)
                        self._move_tracking(old, new)
                        return new

            instance = python_class()
            if id not in self._instance_cache:
                self._instance_cache[id] = set()
            self._instance_cache[id].add(instance)
            instance.set_has_identifier(str(id))

            if populate:
                self.populate_instance(instance, id)

            return instance

        except Exception:
            logger.warning("Cannot create %s for %s",
                           python_class.__name__ if python_class else "Unknown", id, exc_info=True)
            return None

    def populate_instance(self, instance, uri: Node):
        """Fill an instance from the triples of `uri`, following the property mapping.

        Only predicates in the allowed namespaces are read. A configured handler or
        setters list runs for each predicate; failures are logged and skipped. Every
        handled triple is recorded in the provenance map, except the rdf:type that
        selected the instance's class.
        """
        if isinstance(uri, URIRef):
            instance.set_has_identifier(str(uri))
        elif isinstance(uri, BNode):
            instance.has_identifier = str(uri)

        # is_subordinate = self._is_punning_subordinate(instance, uri)

        for predicate, obj in self.graph.predicate_objects(uri):
            if iri_namespace(str(predicate)) not in self._allowed_namespaces:
                continue

            handled = False
            config = self._property_mapping.get(predicate)

            if config is not None:
                target_classes = config.get('target_classes', [])
                #if is_subordinate and target_classes and type(instance) not in target_classes:
                #    continue
                if target_classes and not self._instance_matches_target(instance, target_classes):
                    continue

                if 'handler' in config:
                    try:
                        # An explicit False means "not admissible for this instance".
                        result = getattr(self, config['handler'])(instance, uri, predicate, obj, None)
                        handled = result is not False
                    except Exception:
                        logger.warning("Handler %s failed on %s (predicate %s)",
                                       config['handler'], uri, predicate, exc_info=True)
                elif 'setters' in config:
                    try:
                        self._apply_setters(instance, config['setters'], obj)
                        handled = True
                    except Exception:
                        logger.warning("Setters failed on %s (predicate %s)",
                                       uri, predicate, exc_info=True)

            if not handled and config is None and self._is_rdf_collection(obj):
                self._handle_collection_object(instance, predicate, obj)
                handled = True

            if handled and not (predicate == RDF.type and obj in self._strategy.get_type_mapping()):
                self._track(instance, (uri, predicate, obj))

    # ========== HELPERS ==========

    def _is_triple_mapped(self, subj, pred, obj) -> bool:
        """Return True if some instance already tracks this triple in its provenance."""
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
        """Return the Container that represents an RDF list, building and caching it once.

        The container is cached before its members are resolved, so a list that
        contains itself cannot loop forever.
        """
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
        except Exception:
            logger.warning("Collection to container conversion failed for %s",
                           collection_uri, exc_info=True)

        return container

    def _create_statement_for_triple(self, subj, pred, obj):
        """Reify one triple as a Statement, unless its predicate is already mapped.

        Lists in object position become Containers and literals become Literals.
        """

        if pred in self._property_mapping:
            return
        
        statement = Statement()
        stmt_bnode = BNode()
        statement.set_has_identifier(str(stmt_bnode))

        self._track(statement, (subj, pred, obj))

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

    def _is_unmapped_structured_bnode(self, node) -> bool:
        """A BNode is a structured Statement value if:
        - it's a BNode (not URIRef, not Literal)
        - it's not already classified by any phase (a bare Resource in the cache is
        only a placeholder made by a mapped predicate such as rdfs:seeAlso)
        - it has at least one outgoing triple
        - none of its outgoing predicates carry a useful rdf:type for our model
        (i.e. it's not declaring itself as a typed entity)
        """
        if not isinstance(node, BNode):
            return False
        if any(type(i) is not Resource for i in self._instance_cache.get(node, ())):
            return False
        has_out = False
        for _ in self.graph.predicate_objects(node):
            has_out = True
            break
        if not has_out:
            return False
        # if it declares an rdf:type that we know how to map, leave it alone
        for t in self.graph.objects(node, RDF.type):
            if t in self._strategy.get_type_mapping():
                return False
        return True

    def _create_nested_statement(self, node):
        """Materialises an unmapped structured BNode as a Statement whose own
        triples become its annotations. Recurses for nested structured BNodes.
        """
        statement = Statement()
        statement.set_has_identifier(str(node))

        # drop the placeholder Resource: the node is represented by the Statement
        self._instance_cache[node] = {statement}

        for p, o in self.graph.predicate_objects(node):
            self._track(statement, (node, p, o))

            # The predicate becomes an Annotation if not otherwise known
            if p in self._instance_cache:
                pred_inst = next(
                    (i for i in self._instance_cache[p] if isinstance(i, Property)),
                    None
                )
            else:
                pred_inst = None
            if pred_inst is None:
                pred_inst = Annotation()
                pred_inst.set_has_identifier(str(p))
                self._instance_cache.setdefault(p, set()).add(pred_inst)

            # Resolve the object recursively
            if self._is_rdf_collection(o):
                o_inst = self._convert_collection_to_container(o)
            elif isinstance(o, RDFlibLiteral):
                o_inst = self._create_literal(o)
            elif self._is_unmapped_structured_bnode(o):
                o_inst = self._create_nested_statement(o)
            else:
                o_inst = self.get_or_create(o, Resource)

            # The first (predicate, object) pair fills the Statement slots;
            # additional pairs are stored as side annotations on the Statement
            # itself via setattr (a Statement keeps its own __dict__).
            if statement.get_has_predicate() is None:
                statement.set_has_predicate(pred_inst)
                if o_inst:
                    statement.set_has_object(o_inst)
            else:
                # extra triples live as ad-hoc attributes keyed by the predicate label
                attr_name = iri_local_name(p) # rdf helper
                existing = getattr(statement, attr_name, None)
                if existing is None:
                    setattr(statement, attr_name, o_inst)
                elif isinstance(existing, list):
                    existing.append(o_inst)
                else:
                    setattr(statement, attr_name, [existing, o_inst])

        return statement

    def _get_punning_dominant(self, uri):
        """Return the instance that wins when an IRI is used as several things (punning).

        The winner follows the config's punning priority; with no match, any cached one.
        """
        if uri not in self._instance_cache:
            return None
        cached = self._instance_cache[uri]
        if not cached:
            return None
        if len(cached) == 1:
            return next(iter(cached))
        priority = self._strategy.get_punning_priority()
        for cls in priority:
            for inst in cached:
                if type(inst) is cls:
                    return inst
        return next(iter(cached))

    def _is_punning_subordinate(self, instance, uri):
        """Return True if `instance` loses against another instance of the same IRI."""
        dom = self._get_punning_dominant(uri)
        return dom is not None and dom is not instance

    # ========== SWRL ==========

    def handle_swrl_imp(self, uri):
        """Build a Rule from a swrl:Imp, with its body atoms as antecedent and head atoms as consequent."""
        # Force promotion to Rule if cached as something else
        if uri in self._instance_cache:
            existing = next(iter(self._instance_cache[uri]))
            if not isinstance(existing, Rule):
                rule = Rule()
                rule.__dict__.update(existing.__dict__)
                self._instance_cache[uri].discard(existing)
                self._instance_cache[uri].add(rule)
                self._move_tracking(existing, rule)
            else:
                rule = existing
        else:
            rule = self.get_or_create(uri, Rule)
        
        if not rule:
            return
        
        body_node = self.graph.value(uri, SWRL_NS.body)
        if body_node:
            try:
                for atom_node in RDFLibCollection(self.graph, body_node):
                    atom = self._parse_swrl_atom(atom_node)
                    if atom:
                        rule.set_has_antecedent(atom)
            except Exception:
                logger.warning("SWRL body parsing failed for rule %s", uri, exc_info=True)

        head_node = self.graph.value(uri, SWRL_NS.head)
        if head_node:
            try:
                for atom_node in RDFLibCollection(self.graph, head_node):
                    atom = self._parse_swrl_atom(atom_node)
                    if atom:
                        rule.set_has_consequent(atom)
            except Exception:
                logger.warning("SWRL head parsing failed for rule %s", uri, exc_info=True)

    def _parse_swrl_atom(self, atom_node):
        """Build an Atom from a SWRL atom node: its predicate (by atom kind) and its arguments."""
        atom = self.get_or_create(atom_node, Atom)
        if not atom:
            return None

        # classPredicate (ClassAtom)
        class_pred = self.graph.value(atom_node, SWRL_NS.classPredicate)
        if class_pred:
            atom.set_has_predicate(self.get_or_create(class_pred, Concept))

        # propertyPredicate (IndividualPropertyAtom, DatavaluedPropertyAtom)
        prop_pred = self.graph.value(atom_node, SWRL_NS.propertyPredicate)
        if prop_pred:
            atom_type_uri = self.graph.value(atom_node, RDF.type)
            local = iri_local_name(atom_type_uri) if atom_type_uri else ''
            if local == 'DatavaluedPropertyAtom':
                atom.set_has_predicate(self.get_or_create(prop_pred, Attribute))
            else:
                atom.set_has_predicate(self.get_or_create(prop_pred, Relation))

        # builtin (BuiltinAtom)
        builtin = self.graph.value(atom_node, SWRL_NS.builtin)
        if builtin:
            atom.set_has_predicate(self.get_or_create(builtin, Resource))

        # SameIndividualsAtom / DifferentIndividualsAtom — no predicate in RDF
        atom_type_uri = self.graph.value(atom_node, RDF.type)
        if atom_type_uri:
            local = iri_local_name(atom_type_uri)
            if local == 'SameIndividualsAtom':
                atom.set_has_predicate(self.get_or_create(OWL.sameAs, Relation))
            elif local == 'DifferentIndividualsAtom':
                atom.set_has_predicate(self.get_or_create(OWL.differentFrom, Relation))

        # dataRange (DataRangeAtom)
        data_range = self.graph.value(atom_node, SWRL_NS.dataRange)
        if data_range and atom.get_has_predicate() is None:
            atom.set_has_predicate(self.get_or_create(data_range, Datatype))

        # argument1 / argument2 (most atom types)
        arg1 = self.graph.value(atom_node, SWRL_NS.argument1)
        if arg1:
            atom.set_has_arguments(self._resolve_swrl_arg(arg1))

        arg2 = self.graph.value(atom_node, SWRL_NS.argument2)
        if arg2:
            atom.set_has_arguments(self._resolve_swrl_arg(arg2))

        # arguments (BuiltinAtom — RDF list)
        args_node = self.graph.value(atom_node, SWRL_NS.arguments)
        if args_node:
            try:
                for arg in RDFLibCollection(self.graph, args_node):
                    atom.set_has_arguments(self._resolve_swrl_arg(arg))
            except Exception:
                logger.warning("SWRL builtin arguments failed for atom %s",
                               atom_node, exc_info=True)

        return atom

    def _resolve_swrl_arg(self, node):
        """Resolve a SWRL argument: a Literal, a Variable or, by default, an Individual."""
        if isinstance(node, RDFlibLiteral):
            return self._create_literal(node)
        if (node, RDF.type, SWRL_NS.Variable) in self.graph:
            return self.get_or_create(node, Variable)
        return self.get_or_create(node, Individual)
    
    # ========== PROVENANCE SUBGRAPH ==========

    def build_provenance_subgraph(self, instance):
        """
        Build the RDF subgraph that provenanced `instance`:
        - direct triples from _triples_map[instance]
        - BNode-transitive closure on object positions
        - reified Statements with `instance` as has_subject
        - strategy-specific axioms (hook: _add_axiom_provenance)
        """
        from rdflib import Graph, BNode
        from lode.models import Statement

        sub = Graph()
        for prefix, ns in self.graph.namespaces():
            sub.bind(prefix, ns, override=True, replace=True)

        # 1. direct triples
        source_triples = self._triples_map.get(instance, set())
        for t in source_triples:
            sub.add(t)

        # 2. BNode-transitive closure on objects
        seen = set()
        for (_s, _p, o) in source_triples:
            if isinstance(o, BNode):
                self._expand_bnode_into(o, sub, seen)

        # 3. reified Statements pointing at instance
        for other_inst, other_triples in self._triples_map.items():
            if not isinstance(other_inst, Statement):
                continue
            if other_inst.get_has_subject() is instance:
                for t in other_triples:
                    sub.add(t)
                    _, _, o = t
                    if isinstance(o, BNode) and o not in seen:
                        self._expand_bnode_into(o, sub, seen)

        # 4. strategy-specific axioms (hook)
        self._add_axiom_provenance(instance, sub)

        return sub

    def _expand_bnode_into(self, bn, sub, seen):
        """Add `bn` and its BNode-transitive closure to `sub`."""
        from rdflib import BNode
        stack = [bn]
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            for p, o in self.graph.predicate_objects(n):
                sub.add((n, p, o))
                if isinstance(o, BNode) and o not in seen:
                    stack.append(o)

    def _add_axiom_provenance(self, instance, sub):
        """Hook for subclasses. Default: no strategy-specific axioms."""
        pass
    