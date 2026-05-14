# OWLAPI vs LODE comparison

Compares LODE's reader output against OWLAPI 5.x (via ROBOT CLI) over the
ontologies listed in `ontologies_spar.json`.

## One-time setup

1. Install JRE 11+ and verify:
   ```
   java -version
   ```
2. Download `robot.jar` v1.9.8:
   https://github.com/ontodev/robot/releases/tag/v1.9.8
3. Place at `<repo>/tools/robot.jar`.

## Run

Full corpus, 8 parallel workers:
```
uv run python -m tests.compare_owlapi.test_compare --batch
```

Via pytest (per-URI test cases, useful for re-running failures):
```
uv run pytest tests/compare_owlapi/test_compare.py -v
```

Single URI (debug):
```
uv run python -c "from tests.compare_owlapi.runner import compare_one; \
  print(compare_one('https://w3id.org/spar/fabio'))"
```

## Output

- `tests/compare_owlapi/reports/<safe_uri>.json` - one per ontology
- `tests/compare_owlapi/reports/_summary.csv` - aggregated deltas

## Report structure (per ontology)

```
{
  "uri": "...",
  "counts": {           # Layer 1: per-type counts and deltas
    "owl:Class": {"lode": N, "owlapi": M, "delta": N-M},
    ...
  },
  "iri_sets": {         # Layer 2: set diff with bounded samples
    "owl:Class": {
      "intersection_size": N,
      "only_in_lode_size": N,
      "only_in_owlapi_size": N,
      "only_in_lode_sample": [...],
      "only_in_owlapi_sample": [...]
    }, ...
  },
  "axiom_coverage": {   # Layer 3: axiom/triple-level
    "owlapi_metrics": {"axiom_count": N, ...},
    "lode_total_triples": N,
    "lode_typed_instances": N,
    "lode_statement_instances": N
  },
  "lode_unmapped_classes": {  # LODE classes with no OWLAPI entity equivalent
    "Restriction": N, "OneOf": N, ...
  }
}
```

## Failure statuses

- `download_error`: ontology unreachable - skipped, error logged
- `robot_error`: ROBOT timeout / parse failure - LODE not run for this URI
- `lode_error`: LODE reader exception - ROBOT result discarded
- `ok`: both pipelines completed, full diff available

## Mapping notes

Only 6 LODE classes have OWLAPI entity counterparts:
`Concept, Relation, Attribute, Annotation, Individual, Datatype`.

LODE-specific classes (Restriction, OneOf, Cardinality, Quantifier,
PropertyConceptRestriction, ...) are reported separately under
`lode_unmapped_classes` since OWLAPI represents them as anonymous class
expressions inside axioms, not as entities.

`type(inst) is cls` is used everywhere (not `isinstance`) to respect LODE's
granular hierarchy.
