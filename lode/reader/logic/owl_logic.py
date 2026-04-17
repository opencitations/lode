# owl_logic.py
from rdflib import Graph, URIRef, Node, Literal as RDFlibLiteral, BNode
from rdflib.namespace import RDF, RDFS, OWL, SKOS, XSD
from rdflib.collection import Collection as RDFLibCollection

from lode.models import *
from lode.reader.logic.base_logic import BaseLogic


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
        - BNodes with inferred_class predicates -> classified and registered
        - URIRefs with any mapped predicate but no rdf:type -> registered with
        the inferred type from classify_by_predicate (only if unambiguous)
        """

        classified = {}

        # Iterate ALL mapped predicates
        for pred in self._property_mapping:
            for uri in self.graph.subjects(pred, None):
                if uri in self._instance_cache:
                    continue
                python_class = self._strategy.classify_by_predicate(uri, self.graph)
                if not python_class:
                    continue
                # Goes for restrictions
                if isinstance(uri, BNode):
                    if uri not in classified:
                        classified[uri] = python_class
                # Goes for any other URI
                elif isinstance(uri, URIRef):
                    # URIRefs canno be Restrictions, just Bnodes can
                    if not issubclass(python_class, Restriction):
                        self.get_or_create(uri, python_class, populate=False)

        # classify recursively restrictions
        self._classify_nested(classified, self._strategy.get_classifier_predicates())

        # creates classified restrictions after recursion
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
                        # No concrete type found — infer and reclassify
                        inferred = self._infer_property_type(instance)
                        new = inferred()
                        new.__dict__.update(instance.__dict__)
                        self._instance_cache[uri].discard(instance)
                        self._instance_cache[uri].add(new)
                        if instance in self._triples_map:
                            self._triples_map[new] = self._triples_map.pop(instance)
                        self.populate_instance(new, uri)
                        # new, reclassified instance after reclassification
                        instance = new

                self._enrich_or_apply_owl_defaults(instance, uri)        

    def _infer_property_type(self, instance) -> type:
        """
        Infers the concrete subtype (Relation, Attribute, Annotation) for a
        generic Property instance (not better classified)

        Strategy (in order):
        1. Traverse UP the subPropertyOf chain: if any ancestor has a concrete
           type, inherit it (if A subPropertyOf B and B is Relation, A is Relation).
        2. Traverse DOWN by scanning the cache for properties that declare this
           instance as their superproperty: if any subproperty has a concrete
           type, inherit it (if B is Relation and B subPropertyOf A, A is Relation).
        3. Fall back to Annotation if no type can be inferred from the hierarchy.
           Annotation makes no domain/range assumptions and is valid for any
           subject/object combination.
        """
        
        visited = set()
        queue = [instance]

        # (1) Goes up and down subproperty hierarchy
        # (1.1) Traverse UP superproperties
        while queue:
            current = queue.pop(0)
            if id(current) in visited:
                continue
            visited.add(id(current))

            if type(current) in (Relation, Attribute, Annotation):
                return type(current)

            for sup in (current.get_is_sub_property_of() or []):
                queue.append(sup)

        # (1.2) Traverse DOWN subproperties
        for instances_set in self._instance_cache.values():
            for inst in instances_set:
                if isinstance(inst, Property):
                    for sup in (inst.get_is_sub_property_of() or []):
                        if sup is instance:
                            t = self._infer_property_type(inst)
                            if t in (Relation, Attribute, Annotation):
                                return t

        # (2) fallback                 
        return Annotation

    def handle_domain(self, instance, uri, predicate, obj, setter=None):
        concept = self.get_or_create(obj, Concept)
        if concept is None:
            concept = self._force_as_concept(obj)
        instance.set_has_domain(concept)

    def handle_range(self, instance, uri, predicate, obj, setter=None):
        resource = self.get_or_create(obj, Concept)
        if resource is None:
            resource = self._force_as_concept(obj)
        instance.set_has_range(resource)

    def handle_equivalent_class(self, instance, uri, predicate, obj, setter=None):
        """§9.1.2 EquivalentClasses — simmetria garantita."""
        other = self.get_or_create(obj, Concept)
        if other:
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

    def handle_same_as(self, instance, uri, predicate, obj, setter=None):
        """§9.6.1 SameIndividual — simmetria garantita."""
        other = self.get_or_create(obj, Individual)
        if other:
            if other not in instance.get_is_same_as():
                instance.set_is_same_as(other)
            if instance not in other.get_is_same_as():
                other.set_is_same_as(instance)

    def handle_different_from(self, instance, uri, predicate, obj, setter=None):
        """§9.6.2 DifferentIndividuals — simmetria garantita."""
        other = self.get_or_create(obj, Individual)
        if other:
            if other not in instance.get_is_different_from():
                instance.set_is_different_from(other)
            if instance not in other.get_is_different_from():
                other.set_is_different_from(instance)

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
        """If obj is a BNode with owl:inverseOf, resolve the real property and mark as inverse."""
        if isinstance(obj, BNode) and (obj, OWL.inverseOf, None) in self.graph:
            inverse_of = self.graph.value(obj, OWL.inverseOf)
            if inverse_of:
                prop = self.get_or_create(inverse_of, Property)
                if prop and isinstance(instance, PropertyConceptRestriction):
                    instance.set_applies_on_property(prop)
                    instance.set_is_inverse(True)
                return
        prop = self.get_or_create(obj, Property)
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

        OWL open-world assumption requires every property to have a domain and
        range. These are resolved first by traversing the rdfs:subPropertyOf
        chain upward — if an ancestor declares domain/range, those are inherited.
        Only if no value is found anywhere in the chain does the default apply.

        Relation (owl:ObjectProperty):
            domain -> owl:Thing  (applies to any individual)
            range  -> owl:Thing  (returns any individual)

        Attribute (owl:DatatypeProperty):
            domain -> owl:Thing  (applies to any individual)
            range  -> rdfs:Literal (returns any literal value)

        Individual:
            If no rdf:type is declared, defaults to owl:Thing — the individual
            exists but its class is unknown.
        """

        owl_thing = self.get_or_create(OWL.Thing, Concept)
        rdfs_string = self.get_or_create(RDFS.Literal, Datatype)

        if isinstance(instance, Relation):
            if not instance.get_has_domain(): # it handles the
                inherited_domain = self._get_inherited_property_values(instance, "get_has_domain")
                if len(inherited_domain) == 0:
                    instance.set_has_domain(owl_thing)
                else:
                    for domain in inherited_domain:
                        instance.set_has_domain(domain)
            if not instance.get_has_range():
                inherited_range = self._get_inherited_property_values(instance, "get_has_range")
                if len(inherited_range) == 0:
                    instance.set_has_range(owl_thing)
                else:
                    for range in inherited_range:
                        instance.set_has_range(range)
        
        if isinstance(instance, Attribute):
            if not instance.get_has_domain():

                inherited_domain = self._get_inherited_property_values(instance, "get_has_domain")
                if len(inherited_domain) == 0:
                    instance.set_has_domain(owl_thing)
                else:
                    for domain in inherited_domain:
                        instance.set_has_domain(domain)

            if not instance.get_has_range():
                inherited_range = self._get_inherited_property_values(instance, "get_has_range")
                if len(inherited_range) == 0:
                    instance.set_has_range(rdfs_string)
                else:
                    for range in inherited_range:
                        instance.set_has_range(range)

        # Default type per Individual
        if isinstance(instance, Individual):
            if not instance.get_has_type():
                owl_thing = self.get_or_create(OWL.Thing, Concept)
                instance.set_has_type(owl_thing)

         
        if isinstance(instance, Resource):
            # adds to Resources involved in punning the also defined as
            if len(self._instance_cache[uri]) > 1:
                for other in self._instance_cache[uri]:
                    if other is not instance:
                        instance.set_also_defined_as(other)


    def _get_inherited_property_values(self, property_instance, getter_name: str) -> list:
        """
        Traversal upward along rdfs:subPropertyOf looking for values
        exposed by getter_name (e.g. get_has_domain, get_has_range).
        At each node, also checks the inverse property's swapped domain/range
        directly from the graph to avoid ordering issues.
        Returns list of values, or [] if none found in the chain.
        """

        def collect(node):
            # Check direct value
            getter = getattr(node, getter_name, None)
            if getter:
                values = getter()
                if values:
                    return values if isinstance(values, list) else [values]
            
            # Check inverse from graph directly
            if isinstance(node, Relation):
                inverse = node.get_is_inverse_of()
                if inverse:
                    swapped_getter = {
                        "get_has_domain": "get_has_range",
                        "get_has_range": "get_has_domain",
                    }.get(getter_name)
                    if swapped_getter:
                        swapped = getattr(inverse, swapped_getter, lambda: None)()
                        if swapped:
                            return swapped if isinstance(swapped, list) else [swapped]
                        # Fallback: read directly from graph
                        inverse_uri = URIRef(inverse.has_identifier)
                        graph_pred = RDFS.range if swapped_getter == "get_has_range" else RDFS.domain
                        for obj in self.graph.objects(inverse_uri, graph_pred):
                            # skips bnodes as they are restrictions
                            if isinstance(obj, BNode):
                                continue
                            inst = self.get_or_create(obj, Concept)
                            if inst:
                                return [inst]
            return None

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
        1. owl:inverseOf — if inverse is a Relation, this is a Relation.
        2. Traverse UP subPropertyOf — inherit type from ancestor.
        3. Traverse DOWN subPropertyOf — inherit type from descendant.
        4. Fallback to Annotation.
        """
        # (1) inverseOf
        inverse = getattr(instance, 'get_is_inverse_of', lambda: None)()
        if inverse and type(inverse) is Relation:
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

        # (4) fallback
        return Annotation

    # ========== HELPERS & RELATED FUNCTIONS PHASE 1 ==========

    def _classify_nested(self, classified, predicates):
        """
        Recursively classifies BNodes found inside OWL list collections
        (owl:intersectionOf, owl:unionOf, owl:oneOf) hanging off already-classified
        BNodes. Extends the classified dict in place with any newly discovered
        BNode-to-class mappings.
        """

        list_preds = [OWL.intersectionOf, OWL.unionOf, OWL.oneOf, OWL.withRestrictions, OWL.onDataRange]

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
        # Ensure the base datatype (owl:onDatatype object) is in cache
        on_datatype = self.graph.value(uri, OWL.onDatatype)
        if on_datatype:
            self.get_or_create(on_datatype, Datatype)

    def handle_facet(self, instance, uri, predicate, obj, setter=None):
        annotation = Annotation()
        annotation.set_has_identifier(str(predicate))
        instance.set_has_constraint(annotation)
        if isinstance(obj, RDFlibLiteral):
            instance.set_has_restriction_value(str(obj))

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
        Se instance e' TruthFunction: popola in-place, ritorna None.
        Se instance e' Concept: crea TruthFunction separata keyed su obj, ritorna tf.
        """
        if type(instance) is TruthFunction:
            instance.set_has_logical_operator(operator)
            try:
                for item in RDFLibCollection(self.graph, obj):
                    concept = self.get_or_create(item, Concept)
                    if concept:
                        instance.set_applies_on_concept(concept)
            except Exception as e:
                print(f"Errore build_truth_function: {e}")
            return None
        else:
            tf = self.get_or_create(obj, TruthFunction)
            if tf:
                tf.set_has_logical_operator(operator)
                try:
                    for item in RDFLibCollection(self.graph, obj):
                        concept = self.get_or_create(item, Concept)
                        if concept:
                            tf.set_applies_on_concept(concept)
                except Exception as e:
                    print(f"Errore build_truth_function: {e}")
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

        subj_inst = self.get_or_create(subj, Individual)
        if subj_inst is None:
            return

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
        else:
            obj_inst = self.get_or_create(obj, Individual)

        if obj_inst:
            statement.set_has_object(obj_inst)

        if stmt_bnode not in self._instance_cache:
            self._instance_cache[stmt_bnode] = set()
        self._instance_cache[stmt_bnode].add(statement)

        self._enrich_or_apply_owl_defaults(subj_inst, subj)
        if obj_inst and isinstance(obj_inst, Individual):
            self._enrich_or_apply_owl_defaults(obj_inst, obj)