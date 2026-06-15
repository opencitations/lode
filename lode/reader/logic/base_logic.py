# base_logic.py
from abc import ABC, abstractmethod
from rdflib import Graph, URIRef, Node, Literal as RDFlibLiteral, BNode
from rdflib.namespace import RDF, RDFS, OWL, SKOS, XSD, Namespace
from rdflib.collection import Collection as RDFLibCollection
from rdflib import Namespace
SWRL_NS = Namespace("http://www.w3.org/2003/11/swrl#")

from lode.models import *

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
        self._warnings = []

    def add_warning(self, code, subject, message):
        self._warnings.append({'code': code, 'subject': str(subject), 'message': message})

    def get_warnings(self):
        if not getattr(self, '_warnings_enabled', False):  # self qui è la LOGIC
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
        for subj, pred, obj in self.graph:
            if pred in self._property_mapping:
                continue
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
    
    # ========== Namespaces resolution ==========
    
    def populate_namespaces(self):
        """Attacca i prefissi del grafo a ogni Model in cache."""
        ns = {prefix: str(uri) for prefix, uri in self.graph.namespaces()}
        for instances in self._instance_cache.values():
            for inst in instances:
                if isinstance(inst, Model):
                    inst.set_has_namespaces(ns)

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
                        # Don't add structural OWL/RDFS/RDF URIs to has_type
                        if setter_name == 'set_has_type' and isinstance(obj, URIRef):
                            obj_str = str(obj)
                            if any(obj_str.startswith(ns) for ns in self._allowed_namespaces) and obj not in (OWL.Thing, OWL.Nothing, RDFS.Literal):
                                continue
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
                        if old in self._triples_map:
                            self._triples_map[new] = self._triples_map.pop(old)
                        return new

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
        
            # handles punning priorities wrt config
            is_subordinate = self._is_punning_subordinate(instance, uri)
            instance_cls_name = type(instance).__name__

            if predicate in self._property_mapping:
                config = self._property_mapping[predicate]
                target_classes = config.get('target_classes', [])

                # Punning subordinate: apply only if config explicitly targets this class
                if is_subordinate and type(instance) not in target_classes:
                    continue

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

    def _is_unmapped_structured_bnode(self, node) -> bool:
        """A BNode is a structured Statement value if:
        - it's a BNode (not URIRef, not Literal)
        - it's not already in the instance cache (not classified by any phase)
        - it has at least one outgoing triple
        - none of its outgoing predicates carry a useful rdf:type for our model
        (i.e. it's not declaring itself as a typed entity)
        """
        if not isinstance(node, BNode):
            return False
        if node in self._instance_cache:
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

        if node not in self._instance_cache:
            self._instance_cache[node] = set()
        self._instance_cache[node].add(statement)
        if statement not in self._triples_map:
            self._triples_map[statement] = set()

        for p, o in self.graph.predicate_objects(node):
            self._triples_map[statement].add((node, p, o))

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
                o_inst = self.get_or_create(o, Individual)

            # The first (predicate, object) pair fills the Statement slots;
            # additional pairs are stored as side annotations on the Statement
            # itself via setattr (a Statement keeps its own __dict__).
            if statement.get_has_predicate() is None:
                statement.set_has_predicate(pred_inst)
                if o_inst:
                    statement.set_has_object(o_inst)
            else:
                # extra triples live as ad-hoc attributes keyed by the predicate label
                attr_name = str(p).rsplit('#', 1)[-1].rsplit('/', 1)[-1]
                existing = getattr(statement, attr_name, None)
                if existing is None:
                    setattr(statement, attr_name, o_inst)
                elif isinstance(existing, list):
                    existing.append(o_inst)
                else:
                    setattr(statement, attr_name, [existing, o_inst])

        return statement

    def _get_punning_dominant(self, uri):
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
        dom = self._get_punning_dominant(uri)
        return dom is not None and dom is not instance

    # ========== SWRL ==========

    def handle_swrl_imp(self, uri):
        # Force promotion to Rule if cached as something else
        if uri in self._instance_cache:
            existing = next(iter(self._instance_cache[uri]))
            if not isinstance(existing, Rule):
                rule = Rule()
                rule.__dict__.update(existing.__dict__)
                self._instance_cache[uri].discard(existing)
                self._instance_cache[uri].add(rule)
                if existing in self._triples_map:
                    self._triples_map[rule] = self._triples_map.pop(existing)
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
            except Exception as e:
                print(f"Errore body AtomList: {e}")

        head_node = self.graph.value(uri, SWRL_NS.head)
        if head_node:
            try:
                for atom_node in RDFLibCollection(self.graph, head_node):
                    atom = self._parse_swrl_atom(atom_node)
                    if atom:
                        rule.set_has_consequent(atom)
            except Exception as e:
                print(f"Errore head AtomList: {e}")

    def _parse_swrl_atom(self, atom_node):
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
            local = str(atom_type_uri).split('#')[-1] if atom_type_uri else ''
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
            local = str(atom_type_uri).split('#')[-1]
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

        # arguments (BuiltinAtom — lista RDF)
        args_node = self.graph.value(atom_node, SWRL_NS.arguments)
        if args_node:
            try:
                for arg in RDFLibCollection(self.graph, args_node):
                    atom.set_has_arguments(self._resolve_swrl_arg(arg))
            except Exception as e:
                print(f"Errore builtin arguments: {e}")

        return atom

    def _resolve_swrl_arg(self, node):
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
    