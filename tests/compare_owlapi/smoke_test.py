"""Diagnostic smoke test. Prints raw ROBOT TSV outputs so we can see
exactly what the parser is failing to read.

Usage:
    uv run python -m tests.compare_owlapi.smoke_test [URI]
"""
import csv
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

import requests

from .robot_runner import (
    ROBOT_JAR, ROBOT_TIMEOUT_SEC,
    check_robot_available, _run_robot,
    _parse_entities, _parse_measure_tsv,
)


DEFAULT_URI = "https://w3id.org/spar/fabio"


def main(uri: str = DEFAULT_URI) -> int:
    print(f"=== Preflight ===")
    print(f"ROBOT_JAR  = {ROBOT_JAR}  (exists={ROBOT_JAR.exists()})")
    try:
        check_robot_available()
        print("preflight  = OK")
    except Exception as e:
        print(f"preflight  = FAIL: {e}")
        return 1

    print(f"\n=== Download {uri} ===")
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        local = tmpdir / "ontology.owl"
        try:
            r = requests.get(uri, headers={
                "Accept": "text/turtle, application/rdf+xml, application/ld+json, */*;q=0.1"
            }, timeout=30, allow_redirects=True)
            r.raise_for_status()
            local.write_bytes(r.content)
            print(f"size       = {local.stat().st_size} bytes")
        except Exception as e:
            print(f"download   = FAIL: {e}")
            return 1

        cls_tsv = tmpdir / "classes.tsv"
        prop_tsv = tmpdir / "properties.tsv"
        ind_tsv = tmpdir / "individuals.tsv"

        print(f"\n=== Running ROBOT export commands ===")
        for label, out, include in [
            ("classes", cls_tsv, "classes"),
            ("properties", prop_tsv, "properties"),
            ("individuals", ind_tsv, "individuals"),
        ]:
            try:
                _run_robot([
                    "export",
                    "--input", str(local),
                    "--header", "ID|Type",
                    "--include", include,
                    "--format", "tsv",
                    "--export", str(out),
                ], cwd=tmpdir)
                print(f"  {label:12s} OK -> {out.name} ({out.stat().st_size} bytes)")
            except Exception as e:
                print(f"  {label:12s} FAIL: {e}")

        # Print raw content of each TSV (first 20 lines)
        for label, path in [("classes", cls_tsv), ("properties", prop_tsv), ("individuals", ind_tsv)]:
            print(f"\n--- raw {label}.tsv (first 20 lines) ---")
            if not path.exists():
                print("  (file not created)")
                continue
            with path.open(encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if i >= 20:
                        print("  ...")
                        break
                    print(f"  {i}: {line.rstrip()!r}")

        # Try parsing
        print(f"\n=== Parsed entities ===")
        try:
            entities = _parse_entities(cls_tsv, prop_tsv, ind_tsv)
            for t, s in entities.items():
                print(f"  {t:20s} {len(s)}")
        except Exception as e:
            print(f"FAIL parse: {e}")
            traceback.print_exc()

    return 0


if __name__ == "__main__":
    uri = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URI
    sys.exit(main(uri))