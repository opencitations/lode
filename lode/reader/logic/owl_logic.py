# owl_logic.py

from rdflib import Graph, URIRef, Node, Literal as RDFlibLiteral, BNode
from rdflib.namespace import RDF, RDFS, OWL, SKOS, XSD
from rdflib.collection import Collection as RDFLibCollection

from lode.models import *
from lode.reader.logic.base_logic import BaseLogic
from lode.reader.warnings import owl_warnings


class OwlLogic(BaseLogic):
    """
    OWL-specific parsing logic.

    Extends BaseLogic with:
    - Phase 1 BNode classification for OWL restrictions and truth functions
    - OWL defaults for domain, range (owl:Thing) and Individual type
    - Handlers for property characteristics, cardinality, truth functions,
      quantifiers, and group axioms (AllDisjointClasses, AllDifferent, etc.)
    - Property type inference for properties not explicitly typed in the artefact
    """

    # _get_allowed_namespaces: ereditato da BaseLogic, legge config YAML

    # ========== HOOK per resolve custom OWL ==========

    def _pre_resolve_hook(self, python_class: type, id: Node) -> type | None:
        """
        OWL override: if the URI is already cached with a non-Individual type,
        return that type to prevent silent downcasting during MRO resolution.
        Returns None to fall through to the default MRO walk.
        """
        if id and id in self._instance_cache:
            for existing in self._instance_cache[id]:
                if type(existing) is not Individual:
                    return type(existing)
        return None

    # ========== READER PHASES ==========

    def phase1_classify_from_predicates(self):
        """Scans the RDF graph for subjects of mapped predicates.
        - BNodes with inferred_class predicates -> classified and registered (mainly Restrictions)
        - URIRefs with any mapped predicate but no rdf:type -> registered with
        the inferred type from classify_by_predicate (only if unambiguous)
        """

        classified = {}

        for pred in self._property_mapping:
            for uri in self.graph.subjects(pred, None):
                if uri in self._instance_cache:
                    continue
                python_class = self._strategy.classify_by_predicate(uri, self.graph)
                if not python_class:
                    continue
                if isinstance(uri, BNode):
                    # [ owl:inverseOf <prop> ] used as object of owl:onProperty is an
                    # anonymous inline property expression inside a Restriction, not a
                    # standalone entity — skipped it to avoid spurious cache entries
                    if (None, OWL.onProperty, uri) in self.graph:
                        continue
                    if uri not in classified:
                        classified[uri] = python_class
                elif isinstance(uri, URIRef):
                    if not issubclass(python_class, Restriction):
                        self.get_or_create(uri, python_class, populate=False)

        owl_warnings.flag_malformed_restrictions(self, classified)
        
        self._classify_nested(classified, self._strategy.get_classifier_predicates())

        for uri, py_class in classified.items():
            self.get_or_create(uri, py_class, populate=False)

    def phase2_create_from_types(self):
        type_mapping = self._strategy.get_type_mapping()

        for rdf_type, config in type_mapping.items():
            py_class = config.get('target_class')
            if not py_class:
                continue
            for uri in self.graph.subjects(RDF.type, rdf_type):
                self.get_or_create(uri, py_class, populate=False)
                # Apply static setters (e.g. set_is_transitive: True) always,
                # even if instance already existed in cache from phase1.
                if 'setters' in config:
                    for instance in self._instance_cache.get(uri, set()):
                        self._apply_setters_immediate(instance, config['setters'])

        # Subjects with rdf:type not covered by config -> Individual
        for s, o in self.graph.subject_objects(RDF.type):
            if isinstance(s, BNode) or s in self._instance_cache:
                continue
            if o not in type_mapping:
                if isinstance(o, URIRef):
                    o_str = str(o)
                    if any(o_str.startswith(ns) for ns in self._allowed_namespaces) and o not in (OWL.Thing, OWL.Nothing, RDFS.Literal):
                        continue
                self.get_or_create(s, Individual, populate=True)

        # Subjects with an rdf:type not mapped in config -> Individual
        for s, o in self.graph.subject_objects(RDF.type):
            if o not in type_mapping and not isinstance(s, BNode) and s not in self._instance_cache:
                self.get_or_create(s, Individual, populate=True)

    def phase3_populate_properties(self):
        """Iterates over all cached instances and populates their properties
        by dispatching each predicate-object pair through the configured
        setters and handlers defined in the property mapping.
        """
        
        for uri in list(self._instance_cache.keys()):
            for instance in list(self._instance_cache[uri]):
                self.populate_instance(instance, uri)             

    def phase4_process_group_axioms(self):
        """Processes group axioms defined in the enricher section of the config.
        For each axiom type, retrieves all matching subjects from the graph
        and dispatches them to the handler specified in the config entry.
        """
                
        axioms = self._strategy.get_group_axioms()
        for axiom_type, handler_name in axioms.items():
            for uri in self.graph.subjects(RDF.type, axiom_type):
                # handler existence guaranteed by _validate_handlers (defined in base_logic)
                getattr(self, handler_name)(uri)

    def phase5_fallback(self):
        """
        Classifies or reclassifies any entity whose concrete type could not be
        determined in earlier phases, in particular generic Property instances
        whose subtype (Relation, Attribute, Annotation) is not explicitly
        asserted in the semantic artefact via rdf:type (handled by phase 2). It uses _infer_property_type to resolve the concrete subtype.

        After reclassification, applies OWL defaults (e.g., domain, range, thing) to all instances via _enrich_or_apply_owl_defaults.
        """
        
        for uri, instances in list(self._instance_cache.items()):
            for instance in list(instances):

                if type(instance) is Property:
                    # Check if a more specific Property subclass already exists for this URI

                    has_concrete = any(
                        type(i) in (Relation, Attribute, Annotation) 
                        for i in instances if i is not instance
                    )
                    
                    if has_concrete:
                        # Remove generic Property, keep the concrete one
                        self._instance_cache[uri].discard(instance)
                    else:
                        # # No concrete type found — infer and reclassify
                        # inferred = self._infer_property_type(instance)
                        # new = inferred()
                        # new.__dict__.update(instance.__dict__)
                        # self._instance_cache[uri].discard(instance)
                        # self._instance_cache[uri].add(new)
                        # if instance in self._triples_map:
                        #     self._triples_map[new] = self._triples_map.pop(instance)
                        # self.populate_instance(new, uri)
                        # # new, reclassified instance after reclassification
                        # instance = new

                        inferred = self._infer_property_type(instance)
                        old_dict = instance.__dict__.copy()
                        instance.__class__ = inferred
                        inferred.__init__(instance)
                        instance.__dict__.update(old_dict)
                        self.populate_instance(instance, uri)

                self._enrich_or_apply_owl_defaults(instance, uri)        

    # def _infer_property_type(self, instance) -> type:
    #     """
    #     Infers the concrete subtype (Relation, Attribute, Annotation) for a
    #     generic Property instance (not better classified)

    #     Strategy (in order):
    #     1. Traverse UP the subPropertyOf chain: if any ancestor has a concrete
    #        type, inherit it (if A subPropertyOf B and B is Relation, A is Relation).
    #     2. Traverse DOWN by scanning the cache for properties that declare this
    #        instance as their superproperty: if any subproperty has a concrete
    #        type, inherit it (if B is Relation and B subPropertyOf A, A is Relation).
    #     3. Fall back to Annotation if no type can be inferred from the hierarchy.
    #        Annotation makes no domain/range assumptions and is valid for any
    #        subject/object combination.
    #     """
        
    #     visited = set()
    #     queue = [instance]

    #     # (1) Goes up and down subproperty hierarchy
    #     # (1.1) Traverse UP superproperties
    #     while queue:
    #         current = queue.pop(0)
    #         if id(current) in visited:
    #             continue
    #         visited.add(id(current))

    #         if type(current) in (Relation, Attribute, Annotation):
    #             return type(current)

    #         for sup in (current.get_is_sub_property_of() or []):
    #             queue.append(sup)

    #     # (1.2) Traverse DOWN subproperties
    #     for instances_set in self._instance_cache.values():
    #         for inst in instances_set:
    #             if isinstance(inst, Property):
    #                 for sup in (inst.get_is_sub_property_of() or []):
    #                     if sup is instance:
    #                         t = self._infer_property_type(inst)
    #                         if t in (Relation, Attribute, Annotation):
    #                             return t

    #     # (2) fallback                 
    #     return Annotation

    def handle_domain(self, instance, uri, predicate, obj, setter=None):
        concept = self.get_or_create(obj, Concept)
        if concept is None:
            concept = self._force_as_concept(obj)
        instance.set_has_domain(concept)

    def handle_range(self, instance, uri, predicate, obj, setter=None):
        if isinstance(instance, Attribute):
            resource = self.get_or_create(obj, Datatype)
        else:
            resource = self.get_or_create(obj, Concept)
        if resource is None:
            resource = self._force_as_concept(obj)
        instance.set_has_range(resource)
        
    def handle_equivalent_class(self, instance, uri, predicate, obj, setter=None):
        """§9.1.2 EquivalentClasses — simmetria garantita."""

        # add WARNING
        if not isinstance(instance, Concept):
            return

        other = self.get_or_create(obj, Concept)
        # add WARNING 
        if not other or not isinstance(other, Concept):
            return
        
        if other not in instance.get_is_equivalent_to():
            instance.set_is_equivalent_to(other)
        if instance not in other.get_is_equivalent_to():
            other.set_is_equivalent_to(instance)

    def handle_disjoint_with(self, instance, uri, predicate, obj, setter=None):
        """§9.1.3 DisjointClasses — simmetria garantita."""
        other = self.get_or_create(obj, Concept)
        if other:
            if other not in instance.get_is_disjoint_with():
                instance.set_is_disjoint_with(other)
            if instance not in other.get_is_disjoint_with():
                other.set_is_disjoint_with(instance)

    def handle_equivalent_property(self, instance, uri, predicate, obj, setter=None):        
        if obj in self._instance_cache:
            other = self.get_or_create(obj, Property)
        else:
            other = self.get_or_create(obj, type(instance))
        if other:
            if other not in instance.get_is_equivalent_to():
                instance.set_is_equivalent_to(other)
            if instance not in other.get_is_equivalent_to():
                other.set_is_equivalent_to(instance)

    def handle_property_disjoint_with(self, instance, uri, predicate, obj, setter=None):
        """§9.2.3 DisjointObjectProperties — simmetria garantita."""
        other = self.get_or_create(obj, Property)
        if other:
            if other not in instance.get_is_disjoint_with():
                instance.set_is_disjoint_with(other)
            if instance not in other.get_is_disjoint_with():
                other.set_is_disjoint_with(instance)

    def _ensure_individual(self, node):
        """Get or create an Individual for node, preserving existing types (punning)."""
        if isinstance(node, RDFlibLiteral):
            return None
        cached = self._instance_cache.get(node, set())
        ind = next((i for i in cached if isinstance(i, Individual)), None)
        if ind:
            return ind
        ind = Individual()
        ind.set_has_identifier(str(node))
        self._instance_cache.setdefault(node, set()).add(ind)
        return ind

    def handle_same_as(self, instance, uri, predicate, obj, setter=None):
        """§9.6.1 SameIndividual — simmetria garantita."""
        subj_ind = self._ensure_individual(uri)
        other = self._ensure_individual(obj)
        if subj_ind and other:
            if other not in subj_ind.get_is_same_as():
                subj_ind.set_is_same_as(other)
            if subj_ind not in other.get_is_same_as():
                other.set_is_same_as(subj_ind)

    def handle_different_from(self, instance, uri, predicate, obj, setter=None):
        """§9.6.2 DifferentIndividuals — simmetria garantita."""
        subj_ind = self._ensure_individual(uri)
        other = self._ensure_individual(obj)
        if subj_ind and other:
            if other not in subj_ind.get_is_different_from():
                subj_ind.set_is_different_from(other)
            if subj_ind not in other.get_is_different_from():
                other.set_is_different_from(subj_ind)

    def handle_inverse_of(self, instance, uri, predicate, obj, setter=None):
        if isinstance(instance, Restriction) and not isinstance(instance, Relation):
            prop = self.get_or_create(obj, Property)
            if prop:
                instance.set_applies_on_property(prop)
            return
        other = self.get_or_create(obj, Relation)
        if other:
            if instance.get_is_inverse_of() is not other:
                instance.set_is_inverse_of(other)
            if other.get_is_inverse_of() is not instance:
                other.set_is_inverse_of(instance)

    def handle_on_property(self, instance, uri, predicate, obj, setter=None):
        """If obj is a BNode with owl:inverseOf, resolve the real property and mark as inverse.
        Undeclared properties default to Relation (ObjectProperty) per OWL DL.
        """
        if isinstance(obj, BNode) and (obj, OWL.inverseOf, None) in self.graph:
            inverse_of = self.graph.value(obj, OWL.inverseOf)
            if inverse_of:
                prop = self.get_or_create(inverse_of, Property)
                if prop and type(prop) is Property:
                    prop = self.get_or_create(inverse_of, Relation)
                if prop and isinstance(instance, PropertyConceptRestriction):
                    instance.set_applies_on_property(prop)
                    instance.set_is_inverse(True)
                return
        prop = self.get_or_create(obj, Property)
        if prop and type(prop) is Property:
            prop = self.get_or_create(obj, Relation)
        if prop:
            instance.set_applies_on_property(prop)
            
    def _force_as_concept(self, uri):
        """Aggiunge Concept in cache per URI già classificato come Individual/Resource (punning OWL)."""
        cached = list(self._instance_cache.get(uri, set()))
        concept = Concept()
        if cached:
            concept.__dict__.update(cached[0].__dict__)
        else:
            concept.set_has_identifier(str(uri))
        self._instance_cache.setdefault(uri, set()).add(concept)
        return concept

    def _enrich_or_apply_owl_defaults(self, instance, uri):
        """
        Applies OWL-mandated defaults to instances lacking explicit declarations.
        [...docstring invariata...]
        """
        
        if uri not in self._instance_cache:
            return

        owl_thing = self.get_or_create(OWL.Thing, Concept)
        rdfs_string = self.get_or_create(RDFS.Literal, Datatype)

        def _safe_inherited(instance, getter_name):
            values = self._get_inherited_property_values(instance, getter_name)
            if isinstance(instance, Attribute):
                if getter_name == "get_has_range":
                    return [v for v in values if isinstance(v, (Datatype, DatatypeRestriction))]
            if isinstance(instance, Relation):
                if getter_name == "get_has_range":
                    return [v for v in values if isinstance(v, Concept)]
            return values

        def _is_only_default(values, default_id):
            return values and all(d.get_has_identifier() == default_id for d in values)

        # Type-specific defaults: always apply, even for punning subordinates
        # (these are constitutive of the class, not generic Resource enrichments)

        if isinstance(instance, Relation):
            current_domains = instance.get_has_domain()
            if not current_domains or _is_only_default(current_domains, owl_thing):
                inherited_domain = _safe_inherited(instance, "get_has_domain")
                if inherited_domain:
                    instance.has_domain.clear()
                    for domain in inherited_domain:
                        instance.set_has_domain(domain)
                elif not current_domains:
                    instance.set_has_domain(owl_thing)

            current_ranges = instance.get_has_range()
            if not current_ranges or _is_only_default(current_ranges, owl_thing):
                inherited_range = _safe_inherited(instance, "get_has_range")
                if inherited_range:
                    instance.has_range.clear()
                    for r in inherited_range:
                        instance.set_has_range(r)
                elif not current_ranges:
                    instance.set_has_range(owl_thing)

        if isinstance(instance, Attribute):
            current_domains = instance.get_has_domain()
            if not current_domains or _is_only_default(current_domains, owl_thing):
                inherited_domain = _safe_inherited(instance, "get_has_domain")
                if inherited_domain:
                    instance.has_domain.clear()
                    for domain in inherited_domain:
                        instance.set_has_domain(domain)
                elif not current_domains:
                    instance.set_has_domain(owl_thing)

            current_ranges = instance.get_has_range()
            if not current_ranges or _is_only_default(current_ranges, rdfs_string):
                inherited_range = _safe_inherited(instance, "get_has_range")
                if inherited_range:
                    instance.has_range.clear()
                    for r in inherited_range:
                        instance.set_has_range(r)
                elif not current_ranges:
                    instance.set_has_range(rdfs_string)

        if isinstance(instance, Individual):
            if not instance.get_has_type():
                instance.set_has_type(owl_thing)

        # Generic Resource-level enrichments: skip for punning subordinates
        if self._is_punning_subordinate(instance, uri):
            return

        if isinstance(instance, Resource):
            if len(self._instance_cache[uri]) > 1:
                existing = instance.get_also_defined_as() or []
                for other in self._instance_cache[uri]:
                    if other is not instance and other not in existing:
                        instance.set_also_defined_as(other)


    def _get_inherited_property_values(self, property_instance, getter_name: str) -> list:
        def collect(node):
            if node is property_instance:
                return None
            getter = getattr(node, getter_name, None)
            if getter:
                values = getter()
                if values:
                    return values if isinstance(values, list) else [values]
            if isinstance(node, Relation):
                swapped_getter = {"get_has_domain": "get_has_range", "get_has_range": "get_has_domain"}.get(getter_name)
                if swapped_getter:
                    for inverse in (node.get_is_inverse_of() or []):
                        swapped = getattr(inverse, swapped_getter, lambda: None)()
                        if swapped:
                            return swapped if isinstance(swapped, list) else [swapped]
                        inverse_uri = URIRef(inverse.get_has_identifier())
                        graph_pred = RDFS.range if swapped_getter == "get_has_range" else RDFS.domain
                        for obj in self.graph.objects(inverse_uri, graph_pred):
                            if isinstance(obj, BNode):
                                continue
                            inst = self.get_or_create(obj, Concept)
                            if inst:
                                return [inst]
            return None

        if isinstance(property_instance, Relation):
            swapped_getter = {"get_has_domain": "get_has_range", "get_has_range": "get_has_domain"}.get(getter_name)
            if swapped_getter:
                owl_thing_id = str(OWL.Thing)
                for inverse in (property_instance.get_is_inverse_of() or []):
                    swapped = getattr(inverse, swapped_getter, lambda: None)()
                    if swapped:
                        filtered = [v for v in (swapped if isinstance(swapped, list) else [swapped])
                                    if v.get_has_identifier() != owl_thing_id]
                        if filtered:
                            return filtered
                    inverse_uri = URIRef(inverse.get_has_identifier())
                    graph_pred = RDFS.range if swapped_getter == "get_has_range" else RDFS.domain
                    for obj in self.graph.objects(inverse_uri, graph_pred):
                        if isinstance(obj, BNode):
                            continue
                        inst = self.get_or_create(obj, Concept)
                        if inst:
                            return [inst]

        result = self._traverse_hierarchy(
            property_instance,
            next_getter="get_is_sub_property_of",
            direction="up",
            collect=collect,
        )
        return result if result is not None else []


    def _infer_property_type(self, instance) -> type:
        """
        Infers the concrete subtype (Relation, Attribute, Annotation) for a
        generic Property instance.

        Strategy:
        1. owl:inverseOf in graph — if present, this is a Relation.
        2. Traverse UP subPropertyOf — inherit type from ancestor.
        3. Traverse DOWN subPropertyOf — inherit type from descendant.
        4. Declared rdfs:range — XSD/Literal range -> Attribute, URIRef range -> Relation.
        5. Graph usage — all literal objects -> Attribute, any URIRef object -> Relation.
        6. Fallback to Annotation.
        """
        uri_ref = URIRef(instance.get_has_identifier()) if instance.get_has_identifier() else None

        # (1) inverseOf in graph (instance not yet populated as Property)
        if uri_ref:
            if any(self.graph.objects(uri_ref, OWL.inverseOf)) or \
               any(self.graph.subjects(OWL.inverseOf, uri_ref)):
                return Relation

        CONCRETE = (Relation, Attribute, Annotation)

        # (2) UP THE HIERARCHY
        def collect_type(node):
            if type(node) in CONCRETE:
                return type(node)
            return None

        result = self._traverse_hierarchy(
            instance,
            next_getter="get_is_sub_property_of",
            direction="up",
            collect=collect_type,
        )
        if result:
            return result

        # (3) DOWN THE HIERARCHY
        result = self._traverse_hierarchy(
            instance,
            next_getter="get_is_sub_property_of",
            direction="down",
            collect=collect_type,
        )
        if result:
            return result

        # (4) Declared rdfs:range
        if uri_ref:
            for range_obj in self.graph.objects(uri_ref, RDFS.range):
                range_str = str(range_obj)
                if range_str.startswith(str(XSD)) or range_obj in (RDFS.Literal,):
                    return Attribute
                if isinstance(range_obj, URIRef):
                    return Relation

        # (5) Graph usage: how the property is used as predicate
        if uri_ref:
            has_literal = False
            has_uriref = False
            for s, p, o in self.graph.triples((None, uri_ref, None)):
                if isinstance(o, RDFlibLiteral):
                    has_literal = True
                elif isinstance(o, URIRef):
                    has_uriref = True
            if has_uriref:
                return Relation
            if has_literal:
                return Attribute

        # (6) fallback
        return Annotation

    # ========== HELPERS & RELATED FUNCTIONS PHASE 1 ==========

    def _classify_nested(self, classified, predicates):
        """
        Recursively classifies BNodes found inside OWL list collections
        (owl:intersectionOf, owl:unionOf, owl:oneOf) hanging off already-classified
        BNodes. Extends the classified dict in place with any newly discovered
        BNode-to-class mappings.
        """

        list_preds = [OWL.intersectionOf, OWL.unionOf, OWL.oneOf, OWL.onDataRange]

        for bnode in list(classified.keys()):
            for pred, obj in self.graph.predicate_objects(bnode):
                if pred in list_preds:
                    try:
                        collection = RDFLibCollection(self.graph, obj)
                        for item in collection:
                            if isinstance(item, BNode) and item not in classified:
                                py_class = self._strategy.classify_by_predicate(item, self.graph)
                                if py_class:
                                    classified[item] = py_class
                    except:
                        pass

    # ========== HELPERS & RELATED FUNCTIONS PHASE 2 ==========

    def _apply_setters_immediate(self, instance, setters_config):
        """Applies static setter values from the config directly to an instance,
        without resolving any RDF object. Used in phase2 to apply constant values
        (e.g. set_is_symmetric: True) defined alongside is: class entries.
        """
        for setter_item in setters_config:
            if isinstance(setter_item, dict):
                for setter_name, value in setter_item.items():
                    if hasattr(instance, setter_name):
                        getattr(instance, setter_name)(value)
            else:
                if hasattr(instance, setter_item):
                    getattr(instance, setter_item)()

    # ========== HANDLERS PHASE 4 (GROUP AXIOMS) ==========

    def process_all_disjoint_classes(self, uri: Node):
        """
        Handles owl:AllDisjointClasses axioms by resolving the owl:members
        collection and marking every pair of member Concepts as mutually
        disjoint via set_is_disjoint_with.
        """
        members_list = self.graph.value(uri, OWL.members)
        if not members_list:
            return
        try:
            members = list(RDFLibCollection(self.graph, members_list))
            for i, class_a_uri in enumerate(members):
                class_a = self.get_or_create(class_a_uri, Concept)
                for class_b_uri in members[i + 1:]:
                    class_b = self.get_or_create(class_b_uri, Concept)
                    class_a.set_is_disjoint_with(class_b)
                    class_b.set_is_disjoint_with(class_a)
        except Exception as e:
            print(f"Errore AllDisjointClasses: {e}")

    def process_all_different(self, uri: Node):
        """
        Handles owl:AllDifferent axioms by resolving the owl:distinctMembers
        collection and marking every pair of member Individuals as mutually
        different via set_is_different_from.
        """
        members_list = self.graph.value(uri, OWL.distinctMembers)
        if not members_list:
            return
        try:
            members = list(RDFLibCollection(self.graph, members_list))
            for i, ind_a_uri in enumerate(members):
                ind_a = self.get_or_create(ind_a_uri, Individual)
                for ind_b_uri in members[i + 1:]:
                    ind_b = self.get_or_create(ind_b_uri, Individual)
                    ind_a.set_is_different_from(ind_b)
                    ind_b.set_is_different_from(ind_a)
        except Exception as e:
            print(f"Errore AllDifferent: {e}")

    def process_all_disjoint_properties(self, uri: Node):
        """
        Handles owl:AllDisjointProperties axioms by resolving the owl:members
        collection and marking every pair of member Properties as mutually
        disjoint via set_is_disjoint_with.
        """
        members_list = self.graph.value(uri, OWL.members)
        if not members_list:
            return
        try:
            members = list(RDFLibCollection(self.graph, members_list))
            for i, prop_a_uri in enumerate(members):
                prop_a = self.get_or_create(prop_a_uri, Property)
                for prop_b_uri in members[i + 1:]:
                    prop_b = self.get_or_create(prop_b_uri, Property)
                    prop_a.set_is_disjoint_with(prop_b)
                    prop_b.set_is_disjoint_with(prop_a)
        except Exception as e:
            print(f"Errore AllDisjointProperties: {e}")

    # ========== HANDLER CALLED BY PHASE 3 FOR POPULATING INSTANCES ==========

    def handle_property_chain(self, instance, uri, predicate, obj, setter=None):
        """Handler per owl:propertyChainAxiom"""
        print(f"DEBUG: uri={uri}, instance={type(instance).__name__}, obj={obj}, is_collection={self._is_rdf_collection(obj)}")

        if not self._is_rdf_collection(obj):
            raise ValueError(f"owl:propertyChainAxiom object is not an RDF list: {obj}")
        collection = RDFLibCollection(self.graph, obj)
        chain_instances = []
        for chain_uri in collection:
            chain_instance = self.get_or_create(chain_uri, Relation)
            chain_instances.append(chain_instance)
        instance.set_has_property_chain(chain_instances)

    def handle_has_key(self, instance, uri, predicate, obj, setter=None):
        try:
            for prop_uri in RDFLibCollection(self.graph, obj):
                prop = self.get_or_create(prop_uri, Property)
                if prop:
                    instance.set_has_key(prop)
        except Exception as e:
            print(f"Errore handle_has_key: {e}")

    # ========== RESTRICTIONS ================================================

    def handle_disjoint_union(self, instance, uri, predicate, obj, setter=None):
        """§9.1.4 DisjointUnion(C CE1...CEn) — equivalent to:
        EquivalentClasses(C ObjectUnionOf(CE1...CEn)) + DisjointClasses(CE1...CEn).
        """
        if not isinstance(instance, Concept):
            return
        try:
            collection = RDFLibCollection(self.graph, obj)
            members = list(collection)

            # 1. C equivalentClass ObjectUnionOf(CE1...CEn)
            tf = self.get_or_create(obj, TruthFunction)
            if tf:
                tf.set_has_logical_operator("or")
                for member_uri in members:
                    concept = self.get_or_create(member_uri, Concept)
                    if concept:
                        tf.set_applies_on_concept(concept)
                instance.set_is_equivalent_to(tf)

            # 2. DisjointClasses(CE1...CEn) — pairwise
            for i, uri_a in enumerate(members):
                concept_a = self.get_or_create(uri_a, Concept)
                for uri_b in members[i+1:]:
                    concept_b = self.get_or_create(uri_b, Concept)
                    if concept_a and concept_b:
                        concept_a.set_is_disjoint_with(concept_b)
                        concept_b.set_is_disjoint_with(concept_a)

        except Exception as e:
            print(f"Errore disjointUnion: {e}")

    def handle_datatype_restriction(self, instance, uri, predicate, obj, setter=None):
        on_datatype = self.graph.value(uri, OWL.onDatatype)
        if on_datatype:
            dt = self.get_or_create(on_datatype, Datatype)
            if dt:
                instance.set_applies_on_concept(dt)
        try:
            collection = RDFLibCollection(self.graph, obj)
            for facet_node in collection:
                for facet_pred, facet_val in self.graph.predicate_objects(facet_node):
                    if facet_pred == RDF.type:
                        continue
                    if isinstance(facet_val, RDFlibLiteral):
                        FACET_MAP = {
                            str(XSD.minInclusive): ">=",
                            str(XSD.maxInclusive): "<=",
                            str(XSD.minExclusive): ">",
                            str(XSD.maxExclusive): "<",
                            str(XSD.pattern): "pattern",
                            str(XSD.length): "length",
                            str(XSD.minLength): "minLength",
                            str(XSD.maxLength): "maxLength",
                        }
                        manchester_facet = FACET_MAP.get(str(facet_pred), str(facet_pred))
                        instance.set_applies_on_concept(manchester_facet)
                        literal = self._create_literal(facet_val)
                        instance.set_has_restriction_value(literal)

                # Register facet node in cache keyed to the parent DatatypeRestriction
                # and mark all its triples as mapped, so phase6 does not create
                # spurious Statements or Individuals for the facet BNode.
                if facet_node not in self._instance_cache:
                    self._instance_cache[facet_node] = set()
                self._instance_cache[facet_node].add(instance)
                if instance not in self._triples_map:
                    self._triples_map[instance] = set()
                for fp, fv in self.graph.predicate_objects(facet_node):
                    self._triples_map[instance].add((facet_node, fp, fv))

        except Exception as e:
            print(f"Errore handle_datatype_restriction: {e}")

    def handle_cardinality_exactly(self, instance, uri, predicate, obj, setter=None):
        instance.set_has_cardinality_type("exactly")
        instance.set_has_cardinality(obj)
        instance.set_applies_on_concept(self.get_or_create(OWL.Thing, Concept))

    def handle_cardinality_min(self, instance, uri, predicate, obj, setter=None):
        instance.set_has_cardinality_type("min")
        instance.set_has_cardinality(obj)
        instance.set_applies_on_concept(self.get_or_create(OWL.Thing, Concept))

    def handle_cardinality_max(self, instance, uri, predicate, obj, setter=None):
        instance.set_has_cardinality_type("max")
        instance.set_has_cardinality(obj)
        instance.set_applies_on_concept(self.get_or_create(OWL.Thing, Concept))

    # ========== HANDLER TRUTH FUNCTIONS ==========

    def _build_truth_function(self, instance, obj, operator):
        """
        If instance is TruthFunction: populate in-place, return None.
        If instance is Concept: create a separate TruthFunction keyed on obj, return tf.

        If the list has a single element, log a warning and:
        - if instance is TruthFunction: populate applies_on_concept anyway, return None
        - if instance is Concept: return the Concept directly (no TruthFunction created)

        If the list is empty, log a warning and return None.
        """
        try:
            items = list(RDFLibCollection(self.graph, obj))
        except Exception as e:
            print(f"Errore build_truth_function: {e}")
            return None

        if len(items) == 0:
            owl_warnings.empty_truth_function(self, instance, obj, operator)
            return None

        if len(items) == 1:
            owl_warnings.singleton_truth_function(self, instance, obj, operator)
            single_concept = self.get_or_create(items[0], Concept)
            if type(instance) is TruthFunction:
                instance.set_has_logical_operator(operator)
                if single_concept:
                    instance.set_applies_on_concept(single_concept)
                return None
            else:
                return single_concept

        if type(instance) is TruthFunction:
            instance.set_has_logical_operator(operator)
            for item in items:
                concept = self.get_or_create(item, Concept)
                if concept:
                    instance.set_applies_on_concept(concept)
            return None
        else:
            tf = self.get_or_create(obj, TruthFunction)
            if tf:
                tf.set_has_logical_operator(operator)
                for item in items:
                    concept = self.get_or_create(item, Concept)
                    if concept:
                        tf.set_applies_on_concept(concept)
            return tf

    def handle_intersection(self, instance, uri, predicate, obj, setter=None):
        if type(instance) not in (TruthFunction, Concept):
            return
        tf = self._build_truth_function(instance, obj, "and")
        if tf and isinstance(instance, Concept):
            instance.set_is_equivalent_to(tf)

    def handle_union(self, instance, uri, predicate, obj, setter=None):
        if type(instance) not in (TruthFunction, Concept):
            return
        tf = self._build_truth_function(instance, obj, "or")
        if tf and isinstance(instance, Concept):
            instance.set_is_equivalent_to(tf)

    def handle_complement(self, instance, uri, predicate, obj, setter=None):
        if type(instance) not in (TruthFunction, Concept):
            return
        if type(instance) is TruthFunction:
            instance.set_has_logical_operator("not")
            concept = self.get_or_create(obj, Concept)
            if concept:
                instance.set_applies_on_concept(concept)
        else:
            tf = self.get_or_create(obj, TruthFunction)
            if tf:
                tf.set_has_logical_operator("not")
                concept = self.get_or_create(obj, Concept)
                if concept:
                    tf.set_applies_on_concept(concept)
            instance.set_is_equivalent_to(tf)

    def handle_one_of(self, instance, uri, predicate, obj, setter=None):
        if type(instance) not in (OneOf, Concept):
            return
        if type(instance) is Concept:
            one_of = self.get_or_create(uri, OneOf)
            if one_of:
                try:
                    collection = RDFLibCollection(self.graph, obj)
                    for item in collection:
                        resource = self.get_or_create(item, Individual)
                        if resource:
                            one_of.set_applies_on_resource(resource)
                except Exception as e:
                    print(f"Errore oneOf su Concept: {e}")
                instance.set_is_equivalent_to(one_of)
        else:  # type(instance) is OneOf
            try:
                collection = RDFLibCollection(self.graph, obj)
                for item in collection:
                    resource = self.get_or_create(item, Individual)
                    if resource:
                        instance.set_applies_on_resource(resource)
            except Exception as e:
                print(f"Errore oneOf: {e}")

    def handle_has_value(self, instance, uri, predicate, obj, setter=None):
        resource = self.get_or_create(obj, Resource)
        if resource:
            instance.set_applies_on_resource(resource)
        on_prop = self.graph.value(uri, OWL.onProperty)
        if on_prop:
            prop = self.get_or_create(on_prop, Property)
            if prop:
                instance.set_applies_on_property(prop)


    def handle_rdf_type(self, instance, uri, predicate, obj, setter=None):
        """
        Handler bidirezionale per rdf:type.

        - subject.has_type += object  (lato Individual/Resource)
        - object.has_member += subject (lato Concept, solo se l'oggetto e'
        effettivamente classificato come Concept e non e' un URI strutturale
        del vocabolario)

        Replica la filter logic di _apply_setters per set_has_type: scarta
        oggetti nei namespace OWL/RDF/RDFS, eccetto owl:Thing, owl:Nothing,
        rdfs:Literal.
        """
        if not isinstance(obj, URIRef) and not isinstance(obj, BNode):
            return

        # Filtro URI strutturali (stessa logica di _apply_setters)
        if isinstance(obj, URIRef):
            obj_str = str(obj)
            if any(obj_str.startswith(ns) for ns in self._allowed_namespaces) \
                    and obj not in (OWL.Thing, OWL.Nothing, RDFS.Literal):
                return

        concept = self.get_or_create(obj, Concept)
        if concept is None:
            return

        # Lato diretto
        if hasattr(instance, 'set_has_type'):
            instance.set_has_type(concept)

        # Lato inverso: solo se l'oggetto e' realmente un Concept
        # (get_or_create puo' promuovere; type() esatto evita di sporcare
        #  TruthFunction/Restriction/OneOf/etc.)
        if type(concept) is Concept and isinstance(instance, Individual):
            concept.set_has_member(instance)


    # ========== OVERRIDE Statement per OWL (typed subject/object) ==========

    def _create_statement_for_triple(self, subj, pred, obj):
        """
        Creates a Statement instance for a triple that was not mapped during
        population phases.

        Skips rdf:type triples — those are handled by phase2 and must not be
        reified as Statements.

        Subject is resolved as Individual; if the namespace filter blocks it
        (e.g. OWL/RDF/RDFS URIs), the triple is silently dropped.

        Predicate is looked up in the instance cache first. If not found, a bare
        Annotation is created directly, bypassing the namespace filter — predicates
        must always be reifiable regardless of their namespace.

        Object is resolved based on its RDF type: RDF collections become
        Containers, RDFLib Literals become Literal instances, everything else
        is resolved as Individual.

        OWL defaults (owl:Thing type for untyped Individuals) are applied to
        subject and object after the Statement is built, since these instances
        may have been created here for the first time, after phase3 defaults
        have already run.
        """
        if pred == RDF.type:
            return
        
        # Subject: an unmapped structured BNode is a Statement, not an Individual.
        # This handles the case where phase6 visits the BNode's outgoing triples
        # before visiting the triple that points to it.
        if self._is_unmapped_structured_bnode(subj):
            # Just materialise it; its outgoing triples will be absorbed inside.
            # Skip emitting a wrapper Statement for this triple — _create_nested_statement
            # already records (subj, pred, obj) in the BNode-Statement's triples_map.
            self._create_nested_statement(subj)
            return

        subj_inst = self._resolve_statement_endpoint(subj, Individual)
        if subj_inst is None:
            # Fallback for structural-namespace subjects: create a bare Resource
            # so the predicate is still reifiable.
            subj_inst = Resource()
            subj_inst.set_has_identifier(str(subj))
            if subj not in self._instance_cache:
                self._instance_cache[subj] = set()
            self._instance_cache[subj].add(subj_inst)

        if pred in self._instance_cache:
            pred_inst = next(
                (i for i in self._instance_cache[pred] if isinstance(i, Property)),
                None
            )
        else:
            pred_inst = None

        if pred_inst is None:
            pred_inst = Annotation()
            pred_inst.set_has_identifier(str(pred))
            if pred not in self._instance_cache:
                self._instance_cache[pred] = set()
            self._instance_cache[pred].add(pred_inst)

        statement = Statement()
        stmt_bnode = BNode()
        statement.set_has_identifier(str(stmt_bnode))

        if statement not in self._triples_map:
            self._triples_map[statement] = set()
        self._triples_map[statement].add((subj, pred, obj))

        statement.set_has_subject(subj_inst)
        statement.set_has_predicate(pred_inst)

        if self._is_rdf_collection(obj):
            obj_inst = self._convert_collection_to_container(obj)
        elif isinstance(obj, RDFlibLiteral):
            obj_inst = self._create_literal(obj)
        elif self._is_unmapped_structured_bnode(obj):
            obj_inst = self._create_nested_statement(obj)
        else:
            # oggetto mai visto: Individual (fallback class — _resolve_statement_endpoint
            # ritorna il dominante in cache se presente, altrimenti crea Individual)
            obj_inst = self._resolve_statement_endpoint(obj, Resource)

        if obj_inst:
            statement.set_has_object(obj_inst)

        if stmt_bnode not in self._instance_cache:
            self._instance_cache[stmt_bnode] = set()
        self._instance_cache[stmt_bnode].add(statement)

        self._enrich_or_apply_owl_defaults(subj_inst, subj)
        if obj_inst and not isinstance(obj, RDFlibLiteral):
            self._enrich_or_apply_owl_defaults(obj_inst, obj)

    def _resolve_statement_endpoint(self, node, fallback_class):
        dom = self._get_punning_dominant(node)
        if dom is not None:
            return dom
        return self.get_or_create(node, fallback_class)
    
    # ========== PROVENANCE OWL-SPECIFIC ==========

    _PROVENANCE_AXIOM_TYPES = (
        OWL.AllDisjointClasses,
        OWL.AllDifferent,
        OWL.AllDisjointProperties,
    )

    def _add_axiom_provenance(self, instance, sub):
        """Include general axioms that mention `instance` URI in members/distinctMembers."""
        uri_str = getattr(instance, 'has_identifier', None)
        if not uri_str:
            return
        uri_ref = URIRef(uri_str)
        for axiom_type in self._PROVENANCE_AXIOM_TYPES:
            for axiom in self.graph.subjects(RDF.type, axiom_type):
                if self._uri_in_axiom_members(axiom, uri_ref):
                    self._expand_bnode_into(axiom, sub, set())

    def _uri_in_axiom_members(self, axiom_node, uri_ref):
        """True if uri_ref appears in owl:members or owl:distinctMembers list of axiom_node."""
        for list_pred in (OWL.members, OWL.distinctMembers):
            head = self.graph.value(axiom_node, list_pred)
            if head is None:
                continue
            node = head
            while node and node != RDF.nil:
                first = self.graph.value(node, RDF.first)
                if first == uri_ref:
                    return True
                node = self.graph.value(node, RDF.rest)
        return False