# rdf_logic.py

from rdflib import URIRef, Node, Literal as RDFlibLiteral, BNode
from rdflib.namespace import RDF, RDFS, OWL, SKOS, XSD
from rdflib.collection import Collection as RDFLibCollection

from lode.models import *
from lode.reader.logic.base_logic import BaseLogic


class RdfLogic(BaseLogic):
    """
    RDF/RDFS parsing logic.

    Behavior:
    - Phase1: classify URIRef subjects of mapped predicates whose config
      declares inferred_class or a single target_classes (mirrors OwlLogic).
      BNodes with inferred_class are classified too (e.g. reified Statements
      via rdf:subject/predicate/object).
    - Phase2: create instances from rdf:type using type_mapping; static
      setters declared in 'is: class' entries are applied immediately.
    - Phase3: populate via setters/handlers from the property mapping.
    - Phase4: no group axioms in pure RDF/RDFS.
    - Phase5: fallback - all unmapped predicates -> Property, all unmapped
      URI subjects/objects -> Resource, then RDFS defaults applied to every
      Property (rdfs:Resource for domain, rdfs:Class for range) climbing the
      rdfs:subPropertyOf hierarchy first.
    - Phase6: inherited from BaseLogic, reifies unmapped triples as Statements.
    """

    # ========== READER PHASES ==========

    def phase1_classify_from_predicates(self):
        """Classifies subjects of mapped predicates.
        - BNodes with inferred_class predicates -> classified
        - URIRefs with inferred_class or unambiguous target_classes -> classified
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
                    if uri not in classified:
                        classified[uri] = python_class
                elif isinstance(uri, URIRef):
                    self.get_or_create(uri, python_class, populate=False)

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
                for instance in self._instance_cache.get(uri, set()):
                    if 'setters' in config:
                        self._apply_setters_immediate(instance, config['setters'])
                    if 'handler' in config:
                        getattr(self, config['handler'])(instance, uri)

    def phase3_populate_properties(self):
        """Populates each cached instance via configured setters and handlers."""
        for uri in list(self._instance_cache.keys()):
            for instance in list(self._instance_cache[uri]):
                self.populate_instance(instance, uri)

    def phase4_process_group_axioms(self):
        """No group axioms in pure RDF/RDFS."""
        pass

    def phase5_fallback(self):
        """
        Generic fallback for RDF/RDFS:
        1. Every predicate not yet cached and outside structural namespaces
           is created as Property.
        2. Every URI subject/object not yet cached is created as Resource.
        3. RDFS defaults (rdfs:Resource for domain, rdfs:Class for range)
           are applied to every Property after climbing the rdfs:subPropertyOf
           chain to inherit declared values when present.
        """
        exclude_predicates = {RDF.first, RDF.rest, RDF.nil}

        # 1. predicati -> Property
        for pred in set(self.graph.predicates()):
            if pred in self._instance_cache or pred in exclude_predicates:
                continue
            if self._is_structural(pred):
                continue
            self.get_or_create(pred, Property, populate=False)

        # 2. soggetti/oggetti URI -> Resource
        for subj in set(self.graph.subjects()):
            if isinstance(subj, URIRef) and subj not in self._instance_cache:
                if self._is_structural(subj) or self._is_rdf_collection(subj):
                    continue
                self.get_or_create(subj, Resource, populate=False)

        for obj in set(self.graph.objects()):
            if isinstance(obj, URIRef) and obj not in self._instance_cache:
                if self._is_structural(obj) or self._is_rdf_collection(obj):
                    continue
                self.get_or_create(obj, Resource, populate=False)

        # 3. defaults RDFS su Property
        for uri, instances in list(self._instance_cache.items()):
            for instance in list(instances):
                if isinstance(instance, Property):
                    self._apply_rdfs_defaults(instance)

    # ========== HELPERS ==========

    def _is_structural(self, uri: Node) -> bool:
        """True if URI belongs to RDF/RDFS/OWL/SKOS/XSD vocabulary namespaces."""
        if not isinstance(uri, URIRef):
            return False
        s = str(uri)
        return any(s.startswith(ns) for ns in (str(RDF), str(RDFS), str(OWL), str(SKOS), str(XSD)))

    def _apply_setters_immediate(self, instance, setters_config):
        """Applies static setter values from config directly (mirror of
        OwlLogic._apply_setters_immediate). Used in phase2 for 'is: class'
        entries that declare setters with constant values.
        """
        for setter_item in setters_config:
            if isinstance(setter_item, dict):
                for setter_name, value in setter_item.items():
                    if hasattr(instance, setter_name):
                        getattr(instance, setter_name)(value)
            else:
                if hasattr(instance, setter_item):
                    getattr(instance, setter_item)()

    def _apply_rdfs_defaults(self, instance):
        """Applies rdfs:Resource (domain) and rdfs:Class (range) defaults
        when the property does not declare them, after walking up
        rdfs:subPropertyOf to inherit values from ancestors.
        """
        if not instance.get_has_domain():
            inherited = self._get_inherited_property_values(instance, "get_has_domain")
            if inherited:
                for d in inherited:
                    instance.set_has_domain(d)
            else:
                instance.set_has_domain(self.get_or_create(RDFS.Resource, Concept))

        if not instance.get_has_range():
            inherited = self._get_inherited_property_values(instance, "get_has_range")
            if inherited:
                for r in inherited:
                    instance.set_has_range(r)
            else:
                instance.set_has_range(self.get_or_create(RDFS.Class, Concept))

    def _get_inherited_property_values(self, property_instance, getter_name: str) -> list:
        """Walks up rdfs:subPropertyOf collecting the first non-empty value
        of getter_name found on an ancestor.
        """
        def collect(node):
            if node is property_instance:
                return None
            getter = getattr(node, getter_name, None)
            if getter:
                values = getter()
                if values:
                    return values if isinstance(values, list) else [values]
            return None

        result = self._traverse_hierarchy(
            property_instance,
            next_getter="get_is_sub_property_of",
            direction="up",
            collect=collect,
        )
        return result if result is not None else []
    

    def create_python_container(self, instance, uri):
        """Populates a Container instance from RDF container/list syntax.

        Handles all four RDF container types:
        - rdf:Bag, rdf:Alt, rdf:Seq -> rdf:_N indexed members
        - rdf:List -> rdf:first/rdf:rest linked list

        URI members are resolved as Resource, RDFlibLiterals as Literal.
        All consumed triples are registered in _triples_map so phase6 does not
        reify them as Statements.
        """
        if instance not in self._triples_map:
            self._triples_map[instance] = set()

        # rdf:List: rdf:first/rdf:rest chain
        if (uri, RDF.first, None) in self.graph:
            try:
                for item in RDFLibCollection(self.graph, uri):
                    member = self._resolve_container_member(item)
                    if member:
                        instance.set_has_member(member)
                # mark structural triples as consumed
                node = uri
                while node and node != RDF.nil:
                    first = self.graph.value(node, RDF.first)
                    rest = self.graph.value(node, RDF.rest)
                    if first is not None:
                        self._triples_map[instance].add((node, RDF.first, first))
                    if rest is not None:
                        self._triples_map[instance].add((node, RDF.rest, rest))
                    node = rest
            except Exception as e:
                print(f"Errore create_python_container (List): {e}")
            return

        # rdf:Bag/Alt/Seq: rdf:_N indexed members
        indexed = []
        for pred, obj in self.graph.predicate_objects(uri):
            pred_str = str(pred)
            prefix = str(RDF) + "_"
            if pred_str.startswith(prefix):
                try:
                    idx = int(pred_str[len(prefix):])
                    indexed.append((idx, pred, obj))
                except ValueError:
                    continue

        indexed.sort(key=lambda t: t[0])
        for _, pred, obj in indexed:
            member = self._resolve_container_member(obj)
            if member:
                instance.set_has_member(member)
            self._triples_map[instance].add((uri, pred, obj))

    def _resolve_container_member(self, node):
        if isinstance(node, RDFlibLiteral):
            return self._create_literal(node)
        return self.get_or_create(node, Resource)