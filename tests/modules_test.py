"""
modules_test.py
Test batch moduli OWL imported e closure.
Uso: python modules_test.py [--out modules_report.json]
"""
import sys
import json
import argparse
from pathlib import Path
from rdflib import OWL

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from lode.reader.reader import Reader
from lode.reader.loader import Loader

ONTOLOGIES_FILE = PROJECT_ROOT / "ontologies.json"


def _load_uris(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    if "uris" in data:
        entries = data["uris"]
        return [e["uri"] if isinstance(e, dict) else e for e in entries]
    raise ValueError("Formato ontologies.json non riconosciuto")


def _get_declared_imports(uri):
    """Carica il grafo base e restituisce la lista di URI dichiarati in owl:imports."""
    try:
        loader = Loader(uri)
        graph = loader.get_graph()
        return [str(o) for _, _, o in graph.triples((None, OWL.imports, None))]
    except Exception:
        return []


def _try_load(uri):
    """Prova a caricare una singola URI. Restituisce True/False."""
    try:
        Loader(uri)
        return True
    except Exception:
        return False


def _count_entities(reader):
    return {cls: len(instances) for cls, instances in reader.get_instances().items()}


def _run_variant(uri, imported=None, closure=None):
    try:
        reader = Reader()
        reader.load_instances(uri, "owl", imported=imported, closure=closure)
        return {
            "passed": True,
            "triples": len(reader._graph),
            "entities": _count_entities(reader),
            "error": None
        }
    except Exception as e:
        return {"passed": False, "triples": None, "entities": None, "error": str(e)}


def _test_uri(uri):
    # 1. Trova gli imports dichiarati nel grafo base
    declared_imports = _get_declared_imports(uri)

    # 2. Per ogni import dichiarato, verifica se è raggiungibile
    imports_detail = {}
    for imp_uri in declared_imports:
        imports_detail[imp_uri] = _try_load(imp_uri)

    reachable   = [u for u, ok in imports_detail.items() if ok]
    unreachable = [u for u, ok in imports_detail.items() if not ok]

    # 3. Esegui le tre varianti
    base     = _run_variant(uri)
    imported = _run_variant(uri, imported=True)
    closure  = _run_variant(uri, closure=True)

    for v in (imported, closure):
        if v["passed"] and base["passed"]:
            v["added"] = v["triples"] - base["triples"]
        else:
            v["added"] = None

    # 4. Determina il risultato del test
    # passed=True solo se: nessun errore E (nessun import dichiarato OPPURE almeno uno importato)
    # passed=False se: errore oppure imports dichiarati ma nessuno raggiungibile
    def _evaluate(variant):
        if not variant["passed"]:
            return False, "load_error"
        if not declared_imports:
            return True, "no_imports"
        if variant["added"] == 0 and len(unreachable) == len(declared_imports):
            return False, "all_imports_unreachable"
        if variant["added"] == 0 and reachable:
            return False, "imports_reachable_but_not_added"
        return True, "ok"

    imp_passed, imp_reason = _evaluate(imported)
    clo_passed, clo_reason = _evaluate(closure)

    return {
        "declared_imports": {
            "count": len(declared_imports),
            "reachable": reachable,
            "unreachable": unreachable,
        },
        "base":     base,
        "imported": {**imported, "passed": imp_passed, "reason": imp_reason},
        "closure":  {**closure,  "passed": clo_passed, "reason": clo_reason},
    }


def _save(out_path, output, indent):
    if out_path:
        out_path.write_text(
            json.dumps(output, indent=indent, default=str, ensure_ascii=False),
            encoding="utf-8"
        )


def run_batch(ontologies_path, output_file, indent):
    uris  = _load_uris(ontologies_path)
    total = len(uris)
    print(f"[modules_test] {total} URI da {ontologies_path.name}", file=sys.stderr)

    summary = {
        "total": total,
        "with_imports": 0,
        "imported_passed": 0, "imported_failed": 0,
        "closure_passed":  0, "closure_failed":  0,
        "fail_reasons": {}
    }
    output   = {"summary": summary, "results": {}}
    out_path = Path(output_file) if output_file else None

    for i, uri in enumerate(uris, 1):
        print(f"[{i}/{total}] {uri}", file=sys.stderr, end="  ")
        entry = _test_uri(uri)

        n_imports = entry["declared_imports"]["count"]
        if n_imports > 0:
            summary["with_imports"] += 1

        for module in ("imported", "closure"):
            m = entry[module]
            key = f"{module}_passed" if m["passed"] else f"{module}_failed"
            summary[key] += 1
            if not m["passed"]:
                reason = m.get("reason", "unknown")
                summary["fail_reasons"][reason] = summary["fail_reasons"].get(reason, 0) + 1

        imp, clo = entry["imported"], entry["closure"]
        imp_s = f"OK +{imp['added']} ({imp['reason']})" if imp["passed"] else f"FAIL [{imp['reason']}]"
        clo_s = f"OK +{clo['added']} ({clo['reason']})" if clo["passed"] else f"FAIL [{clo['reason']}]"
        imports_s = f"imports={n_imports} reach={len(entry['declared_imports']['reachable'])}"
        print(f"{imports_s}  |  imported: {imp_s}  |  closure: {clo_s}", file=sys.stderr)

        output["results"][uri] = entry
        _save(out_path, output, indent)

    print(f"\n{'='*60}", file=sys.stderr)
    print(f"Ontologie con imports dichiarati: {summary['with_imports']}/{total}", file=sys.stderr)
    print(f"imported: {summary['imported_passed']}/{total} passed", file=sys.stderr)
    print(f"closure:  {summary['closure_passed']}/{total} passed",  file=sys.stderr)
    print(f"Fail reasons: {summary['fail_reasons']}", file=sys.stderr)

    if not out_path:
        print(json.dumps(output, indent=indent, default=str, ensure_ascii=False))


def main():
    p = argparse.ArgumentParser(description="Test batch moduli OWL imported e closure.")
    p.add_argument("--input", default=str(ONTOLOGIES_FILE))
    p.add_argument("--out",        default=None)
    p.add_argument("--indent",     type=int, default=2)
    a = p.parse_args()
    run_batch(Path(a.input), a.out, a.indent)


if __name__ == "__main__":
    main()