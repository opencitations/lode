"""Three-layer diff between LODE and OWLAPI/ROBOT outputs."""
from typing import Dict, Set


def diff_counts(lode_iris: Dict[str, Set[str]],
                robot_iris: Dict[str, Set[str]]) -> Dict[str, dict]:
    """Layer 1: per-type counts and absolute deltas."""
    out = {}
    for t in robot_iris:
        l = len(lode_iris.get(t, set()))
        r = len(robot_iris[t])
        out[t] = {"lode": l, "owlapi": r, "delta": l - r}
    return out


def diff_iri_sets(lode_iris: Dict[str, Set[str]],
                  robot_iris: Dict[str, Set[str]],
                  sample_limit: int = 20) -> Dict[str, dict]:
    """Layer 2: set-difference per entity type, with bounded samples.

    Full sets included only if small (<= sample_limit). Otherwise, samples
    are reported alongside cardinalities to keep JSON compact.
    """
    out = {}
    for t in robot_iris:
        l_set = lode_iris.get(t, set())
        r_set = robot_iris[t]
        only_lode = l_set - r_set
        only_owlapi = r_set - l_set
        common = l_set & r_set
        out[t] = {
            "intersection_size": len(common),
            "only_in_lode_size": len(only_lode),
            "only_in_owlapi_size": len(only_owlapi),
            "only_in_lode_sample": sorted(only_lode)[:sample_limit],
            "only_in_owlapi_sample": sorted(only_owlapi)[:sample_limit],
        }
    return out


def diff_axiom_coverage(robot_metrics: Dict[str, int],
                        lode_logic) -> Dict[str, int]:
    """Layer 3: axiom-level coverage proxy.

    OWLAPI side: full ROBOT measure metrics (axiom counts, expressivity, ...).
    LODE side: total triples in graph, mapped via Statement instances vs
    non-Statement instances (proxy for 'consumed by typed model' vs
    'fallback Statement').
    """
    total_triples = len(lode_logic.graph)
    statement_count = 0
    typed_count = 0
    for instances in lode_logic._instance_cache.values():
        for inst in instances:
            if type(inst).__name__ == "Statement":
                statement_count += 1
            else:
                typed_count += 1
    return {
        "owlapi_metrics": dict(robot_metrics),
        "lode_total_triples": total_triples,
        "lode_typed_instances": typed_count,
        "lode_statement_instances": statement_count,
    }


def build_report(uri: str,
                 lode_iris: Dict[str, Set[str]],
                 robot_iris: Dict[str, Set[str]],
                 robot_metrics: Dict[str, int],
                 lode_logic,
                 unmapped_lode: Dict[str, int]) -> dict:
    """Assemble the full per-ontology report."""
    return {
        "uri": uri,
        "counts": diff_counts(lode_iris, robot_iris),
        "iri_sets": diff_iri_sets(lode_iris, robot_iris),
        "axiom_coverage": diff_axiom_coverage(robot_metrics, lode_logic),
        "lode_unmapped_classes": unmapped_lode,
    }
