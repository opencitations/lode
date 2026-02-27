"""
inspect_viewer.py
-----------------
Script di ispezione per BaseViewer / OwlViewer.

Uso:
    python inspect_viewer.py [--out report.json] [--read-as owl] [--indent 2]

Legge gli URI da ontologies.json ed esegue test Loader + Punning su ciascuno.
"""

import sys
import json
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from lode.reader.reader import Reader
from lode.viewer.owl_viewer import OwlViewer

ONTOLOGIES_FILE = PROJECT_ROOT / "ontologies.json"


# --------------------------------------------------------------------------
# Punning check
# --------------------------------------------------------------------------

def _is_punning(types: set) -> bool:
    return 'Individual' in types and len(types) > 1


def _check_punning_single(reader, viewer) -> dict:
    from rdflib.namespace import RDF, OWL
    from rdflib import URIRef

    type_mapping = reader._configuration.get_type_mapping()

    named_individuals = {
        str(s) for s, _, _ in reader._graph.triples((None, RDF.type, OWL.NamedIndividual))
    }

    rdf_punning = {}
    for uri_str in named_individuals:
        uri = URIRef(uri_str)
        python_types = {'Individual'}
        for _, _, rdf_type in reader._graph.triples((uri, RDF.type, None)):
            config = type_mapping.get(rdf_type)
            if config:
                py_class = config.get('target_class')
                if py_class and py_class.__name__ != 'Individual':
                    python_types.add(py_class.__name__)
        if _is_punning(python_types):
            rdf_punning[uri_str] = sorted(python_types)

    cache_punning = {}
    for uri, instance_set in reader._instance_cache.items():
        if isinstance(uri, str) and uri.startswith("LITERAL::"):
            continue
        python_types = {type(i).__name__ for i in instance_set}
        if _is_punning(python_types):
            cache_punning[str(uri)] = sorted(python_types)

    uri_to_types = {}
    for instance in viewer.get_all_instances():
        uri = getattr(instance, 'has_identifier', None)
        if uri:
            uri_to_types.setdefault(uri, set()).add(type(instance).__name__)

    viewer_punning = {
        uri: sorted(types)
        for uri, types in uri_to_types.items()
        if _is_punning(types)
    }

    rdf_uris    = set(rdf_punning.keys())
    cache_uris  = set(cache_punning.keys())
    viewer_uris = set(viewer_punning.keys())

    counts = {
        "rdf_graph": len(rdf_punning),
        "cache":     len(cache_punning),
        "viewer":    len(viewer_punning),
    }

    if rdf_uris == cache_uris == viewer_uris:
        passed, warning = True, None
    elif cache_uris == viewer_uris and len(cache_uris) > len(rdf_uris):
        passed = True
        warning = (
            f"Reader e Viewer sono consistenti ({len(cache_uris)} individui con punning), "
            f"ma il grafo RDF ne dichiara solo {len(rdf_uris)} come owl:NamedIndividual. "
            f"Verificare manualmente: {sorted(cache_uris - rdf_uris)}"
        )
    else:
        passed, warning = False, None

    return {
        "passed": passed,
        "warning": warning,
        "punning_count": counts,
        "punning_in_rdf_graph": rdf_punning,
        "punning_in_cache":     cache_punning,
        "punning_in_viewer":    viewer_punning,
        "discrepancies": {
            "in_rdf_not_in_cache":    sorted(rdf_uris   - cache_uris),
            "in_cache_not_in_rdf":    sorted(cache_uris  - rdf_uris),
            "in_cache_not_in_viewer": sorted(cache_uris  - viewer_uris),
            "in_viewer_not_in_cache": sorted(viewer_uris - cache_uris),
        }
    }


# --------------------------------------------------------------------------
# Batch test
# --------------------------------------------------------------------------

def _load_uris() -> list[str]:
    if not ONTOLOGIES_FILE.exists():
        raise FileNotFoundError(f"File non trovato: {ONTOLOGIES_FILE}")
    data = json.loads(ONTOLOGIES_FILE.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    if "uris" in data:
        entries = data["uris"]
        return [e["uri"] for e in entries] if entries and isinstance(entries[0], dict) else entries
    raise ValueError("Formato ontologies.json non riconosciuto (atteso lista o {\"uris\": [...]})")


def _append_result(out_path: Path | None, uri: str, entry: dict, indent: int):
    if not out_path:
        return
    try:
        current = json.loads(out_path.read_text(encoding="utf-8")) if out_path.stat().st_size > 0 else {}
    except Exception:
        current = {}
    current.setdefault("results", {})[uri] = entry
    try:
        out_path.write_text(
            json.dumps(current, indent=indent, default=str, ensure_ascii=False),
            encoding="utf-8"
        )
    except Exception as e:
        print(f"  ⚠️  Scrittura fallita per {uri}: {e}", file=sys.stderr)


def run_batch(output_file: str | None, indent: int, read_as: str = "owl"):
    uris = _load_uris()
    total = len(uris)
    print(f"📋 {total} URI caricati da {ONTOLOGIES_FILE.name}", file=sys.stderr)

    summary = {"total": total, "loader_passed": 0, "loader_failed": 0,
               "punning_passed": 0, "punning_failed": 0}
    results = {}

    out_path = Path(output_file) if output_file else None
    if out_path:
        out_path.write_text("", encoding="utf-8")

    for i, uri in enumerate(uris, 1):
        print(f"[{i}/{total}] {uri}", file=sys.stderr, end="  ")
        entry = {"uri": uri, "loader": None, "punning": None}

        try:
            reader = Reader()
            reader.load_instances(uri, read_as)
            entry["loader"] = {"passed": True}
            summary["loader_passed"] += 1
            print("✅ load", file=sys.stderr, end="  ")
        except Exception as e:
            entry["loader"] = {"passed": False, "error": str(e)}
            summary["loader_failed"] += 1
            print("❌ load", file=sys.stderr)
            results[uri] = entry
            _append_result(out_path, uri, entry, indent)
            continue

        try:
            viewer = OwlViewer(reader)
            punning_result = _check_punning_single(reader, viewer)
            entry["punning"] = punning_result
            counts = punning_result["punning_count"]
            if punning_result["passed"]:
                summary["punning_passed"] += 1
                if punning_result.get("warning"):
                    print(f"⚠️  punning (warning)  rdf={counts['rdf_graph']} "
                          f"cache={counts['cache']} viewer={counts['viewer']}", file=sys.stderr)
                    print(f"   ⚠️  {punning_result['warning']}", file=sys.stderr)
                else:
                    print("✅ punning", file=sys.stderr)
            else:
                summary["punning_failed"] += 1
                print(f"❌ punning  rdf={counts['rdf_graph']} "
                      f"cache={counts['cache']} viewer={counts['viewer']}", file=sys.stderr)
        except Exception as e:
            entry["punning"] = {"passed": False, "error": str(e)}
            summary["punning_failed"] += 1
            print(f"❌ punning: {e}", file=sys.stderr)

        results[uri] = entry
        _append_result(out_path, uri, entry, indent)

    print(f"\n{'='*60}", file=sys.stderr)
    print(f"Loader:  {summary['loader_passed']}/{total} passed", file=sys.stderr)
    print(f"Punning: {summary['punning_passed']}/{summary['loader_passed']} passed "
          f"(su ontologie caricate)", file=sys.stderr)

    if out_path:
        out_path.write_text(
            json.dumps({"summary": summary, "results": results},
                       indent=indent, default=str, ensure_ascii=False),
            encoding="utf-8"
        )
        print(f"📄 Report finale: {out_path}", file=sys.stderr)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=f"Esegui test Loader + Punning sugli URI in {ONTOLOGIES_FILE.name}."
    )
    parser.add_argument("--read-as", dest="read_as", default="owl",
                        help="Strategia di lettura (default: owl)")
    parser.add_argument("--out",     dest="output_file", default=None,
                        help="File JSON di output per il report")
    parser.add_argument("--indent",  dest="indent", type=int, default=2)

    args = parser.parse_args()
    run_batch(args.output_file, args.indent, args.read_as)


if __name__ == "__main__":
    main()