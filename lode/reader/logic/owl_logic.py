# owl_logic.py
from rdflib import Graph, URIRef, Node, Literal as RDFlibLiteral, BNode
from rdflib.namespace import RDF, RDFS, OWL, SKOS, XSD
from rdflib.collection import Collection as RDFLibCollection

from lode.models import *
from lode.reader.logic.base_logic import BaseLogic


class OwlLogic(BaseLogic):
    """
    Logica specifica OWL.

    Differenze rispetto a BaseLogic:
    - Domain/Range default a owl:Thing
    - Gestione restrictions (onProperty, someValuesFrom, etc.)
    - Equivalenze e disgiunzioni
    - Classi ammesse: tutte le OWL classes

    NON override _get_allowed_namespaces: lette da config YAML (key 'namespaces').
    NON override _resolve_allowed_class: usa _pre_resolve_hook.
    """

    # _get_allowed_namespaces: ereditato da BaseLogic, legge config YAML

    # ========== HOOK per resolve custom OWL ==========

    def _pre_resolve_hook(self, python_class: type, id: Node) -> type | None:
        """
        OWL: se l'URI è già in cache con un tipo non-Individual,
        usa quello invece di salire l'MRO (evita downcasting silenzioso).
        """
        if id and id in self._instance_cache:
            for existing in self._instance_cache[id]:
                if type(existing) is not Individual:
                    return type(existing)
        return None

    # ========== READER PHASES ==========
    def phase1_classify_from_predicates(self):
        """Classifies entities from the predicates mapping"""
        # print("\n--- FASE 1: Classificazione OWL ---")
        
        classifier_preds = self._strategy.get_classifier_predicates()
        if not classifier_preds:
            print("Nessun classificatore")
            return
        
        classified = {}
        
        for pred in classifier_preds:
            for uri in self.graph.subjects(pred, None):
                # handle OWL restrictions 
                if isinstance(uri, BNode) and uri not in classified:
                    python_class = self._strategy.classify_by_predicate(uri, self.graph)
                    if python_class:
                        classified[uri] = python_class

        # Ricorsione per liste
        self._classify_nested(classified, classifier_preds)
        
        # Crea istanze
        for uri, py_class in classified.items():
            self.get_or_create(uri, py_class, populate=False)


        #print(f"  Classificate: {len(classified)}")

    def phase2_create_from_types(self):
        """Crea istanze da rdf:type e li mappa al config + applica setters immediati"""
        type_mapping = self._strategy.get_type_mapping()

        for rdf_type, config in type_mapping.items():
            py_class = config.get('target_class')
            if not py_class:
                continue

            for uri in self.graph.subjects(RDF.type, rdf_type):
                self.get_or_create(uri, py_class, populate=False)

                if 'setters' in config:
                    for instance in self._instance_cache.get(uri, set()):
                        self._apply_setters_immediate(instance, config['setters'])

        # Soggetti con rdf:type non mappato -> Individual
        for s, o in self.graph.subject_objects(RDF.type):
            if o not in type_mapping and not isinstance(s, BNode) and s not in self._instance_cache:
                self.get_or_create(s, Individual, populate=True)

    def phase3_populate_properties(self):
        # Pass 1: reclassify
        reclassifying = {
            pred: cfg for pred, cfg in self._property_mapping.items()
            if cfg.get('reclassifies')
        }
        for pred, cfg in reclassifying.items():
            for uri in list(self._instance_cache.keys()):
                obj = self.graph.value(uri, pred)
                if obj:
                    for instance in list(self._instance_cache[uri]):
                        handler = getattr(self, cfg['handler'])
                        handler(instance, uri, pred, obj)

        # Pass 2: populate
        for uri in list(self._instance_cache.keys()):
            for instance in list(self._instance_cache[uri]):
                self.populate_instance(instance, uri)             

    def phase4_process_group_axioms(self):
        """Processa assiomi di gruppo dall'enricher config"""
        axioms = self._strategy.get_group_axioms()
        for axiom_type, handler_name in axioms.items():
            for uri in self.graph.subjects(RDF.type, axiom_type):
                # handler existence guaranteed by _validate_handlers
                getattr(self, handler_name)(uri)

    def phase5_fallback(self):
        """
        ADD OTHER FALLBACKS IF NEEDED 

        ## PROPERTIES FALLBACK
        Infers the concrete property type (Relation, Attribute, Annotation)
        for a generic Property by traversing the subPropertyOf hierarchy.

        Strategy (in order):
        1. Traverse UP the superproperties chain via get_is_sub_property_of.
        If any ancestor has a concrete type, inherit it.
        Rationale: if A subPropertyOf B and B is a Relation, then A is also
        a Relation by rdfs:subPropertyOf semantics.

        2. Traverse DOWN by scanning the full cache for any Property that
        declares this instance as its superproperty.
        If any subproperty has a concrete type, inherit it.
        Rationale: if B is a Relation and B subPropertyOf A, then A must
        also be a Relation.

        3. Fallback to Annotation if no type can be inferred from the hierarchy.
        Annotation is the safest default: it makes no domain/range assumptions
        and is valid for any subject/object combination.
        """
        for uri, instances in list(self._instance_cache.items()):
            for instance in list(instances):
                if type(instance) is Property:
                    inferred = self._infer_property_type(instance)
                    if inferred is not type(instance):
                        new = inferred()
                        new.set_has_identifier(instance.has_identifier)
                        self._instance_cache[uri] = {new}
                        self.populate_instance(new, uri)
                        self._apply_owl_defaults(new)

                if type(instance) is Resource:
                    print(instance.get_has_identifier())

        

    def _infer_property_type(self, instance) -> type:
        """
        Infers the concrete property type (Relation, Attribute, Annotation)
        for a generic Property by traversing the subPropertyOf hierarchy.

        Strategy (in order):
        1. Traverse UP the superproperties chain via get_is_sub_property_of.
        If any ancestor has a concrete type, inherit it.
        Rationale: if A subPropertyOf B and B is a Relation, then A is also
        a Relation by rdfs:subPropertyOf semantics.

        2. Traverse DOWN by scanning the full cache for any Property that
        declares this instance as its superproperty.
        If any subproperty has a concrete type, inherit it.
        Rationale: if B is a Relation and B subPropertyOf A, then A must
        also be a Relation.

        3. Fallback to Annotation if no type can be inferred from the hierarchy.
        Annotation is the safest default: it makes no domain/range assumptions
        and is valid for any subject/object combination.
        """
        visited = set()
        queue = [instance]

        # Risali superproprietà
        while queue:
            current = queue.pop(0)
            if id(current) in visited:
                continue
            visited.add(id(current))

            if type(current) in (Relation, Attribute, Annotation):
                return type(current)

            for sup in (current.get_is_sub_property_of() or []):
                queue.append(sup)

        # Scendi sottoproprietà
        for instances_set in self._instance_cache.values():
            for inst in instances_set:
                if isinstance(inst, Property):
                    for sup in (inst.get_is_sub_property_of() or []):
                        if sup is instance:
                            t = self._infer_property_type(inst)
                            if t in (Relation, Attribute, Annotation):
                                return t
                            
        return Annotation

    # ========== OWL DEFAULTS ==========

    def _apply_owl_defaults(self, instance):
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
        xsd_anytype = self.get_or_create(RDFS.Literal, Datatype)

        if isinstance(instance, Relation):

            inherited_domain = self._get_inherited_property_values(instance, "get_has_domain")
            if len(inherited_domain) == 0:
                instance.set_has_domain(owl_thing)
            else:
                for domain in inherited_domain:
                    instance.set_has_domain(domain)

            inherited_range = self._get_inherited_property_values(instance, "get_has_range")
            if len(inherited_range) == 0:
                instance.set_has_range(owl_thing)
            else:
                for range in inherited_range:
                    instance.set_has_range(range)
        
        if isinstance(instance, Attribute):

            inherited_domain = self._get_inherited_property_values(instance, "get_has_domain")
            if len(inherited_domain) == 0:
                instance.set_has_domain(owl_thing)
            else:
                for domain in inherited_domain:
                    instance.set_has_domain(domain)

            inherited_range = self._get_inherited_property_values(instance, "get_has_range")
            if len(inherited_range) == 0:
                instance.set_has_range(xsd_anytype)
            else:
                for range in inherited_range:
                    instance.set_has_range(range)

        # Default type per Individual
        if isinstance(instance, Individual):
            if not instance.get_has_type():
                owl_thing = self.get_or_create(OWL.Thing, Concept)
                instance.set_has_type(owl_thing)

    def _get_inherited_property_values(self, property_instance, getter_name):
        """Traversal upward along rdfs:subPropertyOf chain looking for values
            exposed by getter_name (e.g. get_has_domain, get_has_range).

            If a super-property was misclassified as generic Resource (because it
            belongs to an external namespace and was only seen as an object of
            rdfs:subPropertyOf, never as a subject of rdf:type), it is upgraded
            in-place to the same type as the child that references it.
            This is valid by rdfs:subPropertyOf semantics: if A is a Relation and
            A rdfs:subPropertyOf B, then B must also be a Relation (same for
            Attribute and Annotation).

            Returns a list of values, or empty list if none found in the chain."""
        
        visited = set()
        queue = [property_instance]

        while queue:
            current = queue.pop(0)
            if id(current) in visited:
                continue
            visited.add(id(current))

            getter = getattr(current, getter_name, None)
            if getter:
                values = getter()
                if values:
                    return values if isinstance(values, list) else [values]

            get_supers = getattr(current, 'get_is_sub_property_of', None)
            if not get_supers:
                continue
                
            supers = get_supers()
            if supers:
                if not isinstance(supers, list):
                    supers = [supers]
                for s in supers:
                    # Se il super è Resource generico, upgradalo al tipo del figlio
                    if type(s) is Resource:
                        target_class = type(current)  # eredita il tipo dal figlio
                        uri = s.has_identifier
                        # trova la chiave in cache
                        for k, v in self._instance_cache.items():
                            if s in v and str(k) == uri:
                                new_instance = self.get_or_create(k, target_class, populate=True)
                                print(f"[INFER] {uri} Resource -> {target_class.__name__} (da subPropertyOf)")
                                queue.append(new_instance)
                                break
                    else:
                        queue.append(s)

        return []

    # ========== HELPERS FASE 1 ==========

    def _classify_nested(self, classified, predicates):
        """Classifica ricorsivamente elementi dentro liste OWL"""
        list_preds = [OWL.intersectionOf, OWL.unionOf, OWL.oneOf]

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

    def _apply_setters_immediate(self, instance, setters_config):
        """Applica setters configurati senza oggetto RDF (valori statici da config)"""
        for setter_item in setters_config:
            if isinstance(setter_item, dict):
                for setter_name, value in setter_item.items():
                    if hasattr(instance, setter_name):
                        getattr(instance, setter_name)(value)
            else:
                if hasattr(instance, setter_item):
                    getattr(instance, setter_item)()

    # ========== HANDLER GROUP AXIOMS ==========

    def process_all_disjoint_classes(self, uri: Node):
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

    # ========== HANDLER RESTRICTIONS ==========

    def handle_range(self, instance, uri, predicate, obj, setter=None):
        
        if type(instance) is not (Property, Attribute, Relation, Annotation):
            return
        if str(obj).startswith(str(XSD)) or obj == RDFS.Literal:
            inferred = Attribute
        else:
            inferred = Relation
        new = inferred()
        new.set_has_identifier(instance.has_identifier)
        self._instance_cache[uri].discard(instance)
        self._instance_cache[uri].add(new)

        # applica set_has_range sull'istanza corretta (nuova o esistente)
        range_obj = self.get_or_create(obj, Resource)
        if range_obj:
            instance.set_has_range(range_obj)

    def handle_property_chain(self, instance, uri, predicate, obj, setter=None):
        try:
            collection = RDFLibCollection(self.graph, obj)
            chain = [self.get_or_create(chain_uri, Relation) for chain_uri in collection]
            instance.set_has_property_chain(chain)
        except Exception as e:
            print(f"Errore propertyChain: {e}")

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
    
    
    # ========== CUSTOM OWL CONFIG HANDLERS ==========

    def handle_with_restrictions(self, instance, uri, predicate, obj, setter=None):
        """Handles owl:withRestrictions — a collection of facet BNodes."""
        try:
            collection = RDFLibCollection(self.graph, obj)
            for node in collection:
                if not isinstance(node, BNode):
                    continue
                for pred, obj in self.graph.predicate_objects(node):
                    print(node, pred, obj)
                    print(self._instance_cache[str(node)])
        except Exception as e:
            print(f"handle_with_restrictions error: {e}")

    # def handle_range(self, instance, uri, predicate, obj, setter=None):
        
    #     obj_instance = None
    #     if obj in self._instance_cache:
    #         obj_instance = next(iter(self._instance_cache[obj]))
    #     else: 
    #         if isinstance(obj, URIRef) and str(obj).startswith(str(XSD)):
    #             self.get_or_create(obj, Datatype)
    #         else: 
    #             self.get_or_create(obj, Resource)

    #     if isinstance(obj_instance, Datatype): 
    #         self.get_or_create(uri, Attribute)
    #     elif isinstance(obj_instance, Concept):
    #         self.get_or_create(uri, Relation)
    #     else: 
    #         self.get_or_create(uri, Property)

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
        if isinstance(instance, Concept):
            one_of = self.get_or_create(uri, OneOf)
            if one_of:
                try:
                    for item in RDFLibCollection(self.graph, obj):
                        resource = self.get_or_create(item, Individual)
                        if resource:
                            one_of.set_applies_on_resource(resource)
                except Exception as e:
                    print(f"Errore oneOf su Concept: {e}")
                instance.set_is_equivalent_to(one_of)
        else:
            try:
                for item in RDFLibCollection(self.graph, obj):
                    resource = self.get_or_create(item, Individual)
                    if resource:
                        instance.set_applies_on_resource(resource)
            except Exception as e:
                print(f"Errore oneOf: {e}")

    # ========== OVERRIDE Statement per OWL (typed subject/object) ==========

    def _create_statement_for_triple(self, subj, pred, obj):
        """OWL override: soggetto -> Individual, oggetto tipizzato."""
        statement = Statement()
        stmt_bnode = BNode()
        statement.set_has_identifier(str(stmt_bnode))

        if statement not in self._triples_map:
            self._triples_map[statement] = set()
        self._triples_map[statement].add((subj, pred, obj))

        if pred != RDF.type:
            # if the subject of a Statement is a BNode, then its reification (they can be shacl shapes :))
            if isinstance(subj, BNode):
                subj_inst = self.get_or_create(subj, Statement)
            # otherwise its most likely a Named Individual (get_or_create decides the actual class)
            else:
                subj_inst = self.get_or_create(subj, Individual)
            
            statement.set_has_subject(subj_inst)

            if self._is_rdf_collection(obj):
                obj_inst = self._convert_collection_to_container(obj)
                pred_inst = self.get_or_create(pred, Relation)
            elif isinstance(obj, RDFlibLiteral):
                obj_inst = self._create_literal(obj)
                pred_inst = self.get_or_create(pred, Annotation)
            elif isinstance(obj, BNode):
                # BNode object = reified annotation, use existing instance or create new Statement
                obj_inst = self.get_or_create(obj, Statement)
                pred_inst = self.get_or_create(pred, Annotation)
            else:
                obj_inst = self.get_or_create(obj, Resource)
                pred_inst = self.get_or_create(pred, Annotation)

            # pred or obj may be None if their URI is in a protected namespace (e.g. rdf:, rdfs:)
            if pred_inst is None:
                pred_inst = Annotation()
                pred_inst.set_has_identifier(str(pred))
            
            if obj_inst is None:
                obj_inst = Resource()
                obj_inst.set_has_identifier(str(obj))

            statement.set_has_predicate(pred_inst)
            statement.set_has_object(obj_inst)

        if stmt_bnode not in self._instance_cache:
            self._instance_cache[stmt_bnode] = set()
        self._instance_cache[stmt_bnode].add(statement)