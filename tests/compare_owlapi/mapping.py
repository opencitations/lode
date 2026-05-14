"""LODE model class <-> OWLAPI EntityType mapping.

The 'Type' column of `robot export` emits the OWLAPI EntityType label:
'Class', 'ObjectProperty', 'DataProperty', 'AnnotationProperty', 'Datatype'.
For named individuals, the 'Type' column emits the rdf:type class IRI(s),
not the entity-type tag - so individuals are extracted via
`--include "individuals"` (presence in the export = is a NamedIndividual).
"""
from lode.models import (
    Concept, Relation, Attribute, Annotation, Individual, Datatype,
)


# LODE class -> ROBOT 'Type' column value (OWLAPI EntityType.getPrintName())
# These are the human-readable strings ROBOT actually writes (with space, lowercase
# second word). Confirmed via TSV inspection.
LODE_TO_ROBOT_TYPE = {
    Concept:    "Class",
    Relation:   "Object property",
    Attribute:  "Data property",
    Annotation: "Annotation property",
    Individual: "Named individual",  # synthesized: see robot_runner._parse_entities
    Datatype:   "Datatype",
}

ROBOT_TYPE_TO_LODE = {v: k for k, v in LODE_TO_ROBOT_TYPE.items()}

# LODE classes that have no OWLAPI entity counterpart (skipped in entity-level diff)
LODE_NON_ENTITY_CLASSES = {
    "Statement", "Literal", "Model", "Property", "Resource",
    "Container", "Collection",
    "Restriction", "OneOf", "Cardinality", "Quantifier",
    "PropertyConceptRestriction", "TruthFunction", "Value",
    "DatatypeRestriction",
    # SWRL
    "Variable", "Atom", "Rule",
}