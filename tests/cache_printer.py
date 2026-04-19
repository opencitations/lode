"""
inspect_viewer.py
Ispezione qualitativa del viewer per una ontologia.
Usa esattamente gli stessi metodi del viewer, così l'output rispecchia
quello che arriva al template HTML.
Uso: python inspect_viewer.py <uri> [--out output.json]
"""
import sys
import json
import argparse
from pathlib import Path

from lode.reader.reader import Reader
from lode.models import *


def inspect(uri):
    reader = Reader()
    reader.load_instances(uri, "owl")

    viewer    = reader.get_viewer()
    view_data = viewer.get_view_data()

    # ── 1. Conteggi nel cache ─────────────────────────────────────────────────
    cache_counts = {}
    for instance_set in reader._instance_cache.values():
        instances = instance_set if isinstance(instance_set, set) else [instance_set]
        for inst in instances:
            t = type(inst).__name__
            cache_counts[t] = cache_counts.get(t, 0) + 1

    # ── 2. Output del viewer (identico a quello che va al template) ───────────
    # view_data contiene già metadata, sections/entities prodotti dal viewer

    # ── 3. Restrictions dettagliate via viewer._format_entities ──────────────
    # Raggruppa per tipo esatto, usa il viewer per formattare ogni entry
    restriction_classes = [Rule, Atom, Variable, DatatypeRestriction, Datatype, Container, Model, Statement, Resource, OneOf, Value, Cardinality, Quantifier, TruthFunction, PropertyConceptRestriction, Restriction]
    seen = set()
    restrictions_by_type = {}

    for cls in restriction_classes:
        instances = []
        for instance_set in reader._instance_cache.values():
            for inst in (instance_set if isinstance(instance_set, set) else [instance_set]):
                if type(inst) is cls and id(inst) not in seen:
                    seen.add(id(inst))
                    instances.append(inst)

        if instances:
            restrictions_by_type[cls.__name__] = viewer._format_entities(instances)

    return {
        "uri":          uri,
        "cache_counts": cache_counts,
        "viewer_data":  view_data,
        "restrictions": restrictions_by_type,
    }


def main():
    p = argparse.ArgumentParser(description="Ispezione qualitativa viewer OWL.")
    p.add_argument("uri", help="URI dell'ontologia")
    p.add_argument("--out",    default=None)
    p.add_argument("--indent", type=int, default=2)
    a = p.parse_args()

    result = inspect(a.uri)
    output = json.dumps(result, indent=a.indent, default=str, ensure_ascii=False)

    if a.out:
        Path(a.out).write_text(output, encoding="utf-8")
        print(f"Salvato in {a.out}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()