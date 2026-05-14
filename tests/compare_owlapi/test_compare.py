"""Pytest entry point + CLI summary aggregator.

Run modes:
1) Pytest parametric (one test per URI, parallelism via -n with pytest-xdist):
       uv run pytest tests/compare_owlapi/test_compare.py

2) Standalone batch with multiprocessing.Pool (recommended for full corpus):
       uv run python -m tests.compare_owlapi.test_compare --batch
"""
import argparse
import csv
import json
import multiprocessing as mp
import sys
from pathlib import Path

import pytest

from .runner import compare_one, preflight, REPORTS_DIR


ONTOLOGIES_JSON = Path(__file__).parent.parent / "ontologies_spar.json"
SUMMARY_CSV = REPORTS_DIR / "_summary.csv"
POOL_WORKERS = 8


def _load_uris():
    with open(ONTOLOGIES_JSON, encoding="utf-8") as f:
        data = json.load(f)
    return [e["uri"] for e in data["uris"]]


# -------- pytest mode --------

@pytest.fixture(scope="session", autouse=True)
def _check_preflight():
    err = preflight()
    if err:
        pytest.exit(f"OWLAPI compare preflight failed: {err}")


@pytest.mark.parametrize("uri", _load_uris())
def test_owlapi_vs_lode(uri):
    """Per-URI smoke test. Asserts only that pipeline produced a report.

    Real validation lives in the JSON reports / summary CSV; the pytest
    pass/fail is operational (did the pipeline run), not semantic.
    """
    result = compare_one(uri)
    assert result["status"] in ("ok", "download_error", "robot_error", "lode_error"), \
        f"unexpected status: {result}"


# -------- batch mode --------

def run_batch():
    err = preflight()
    if err:
        print(f"ERROR: {err}", file=sys.stderr)
        sys.exit(1)

    uris = _load_uris()
    print(f"Comparing {len(uris)} ontologies with pool of {POOL_WORKERS} workers...")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    with mp.Pool(POOL_WORKERS) as pool:
        results = []
        for i, r in enumerate(pool.imap_unordered(compare_one, uris), 1):
            results.append(r)
            print(f"[{i}/{len(uris)}] {r['status']:16s} {r['uri']}")

    write_summary(results)
    print(f"\nSummary: {SUMMARY_CSV}")
    _print_status_breakdown(results)


def write_summary(results):
    """Aggregate per-URI deltas into one CSV row each."""
    rows = []
    for r in results:
        if r["status"] != "ok":
            rows.append({
                "uri": r["uri"], "status": r["status"],
                "error": r.get("error", ""),
            })
            continue

        report = json.loads(Path(r["report_path"]).read_text(encoding="utf-8"))
        counts = report["counts"]
        row = {"uri": r["uri"], "status": "ok", "error": ""}
        for t, vals in counts.items():
            key = t.split(":")[-1].lower()
            row[f"{key}_lode"] = vals["lode"]
            row[f"{key}_owlapi"] = vals["owlapi"]
            row[f"{key}_delta"] = vals["delta"]
        row["total_triples"] = report["axiom_coverage"]["lode_total_triples"]
        row["lode_statements"] = report["axiom_coverage"]["lode_statement_instances"]
        rows.append(row)

    if not rows:
        return
    fieldnames = sorted({k for r in rows for k in r.keys()})
    # Pin uri/status/error first for readability
    head = ["uri", "status", "error"]
    fieldnames = head + [f for f in fieldnames if f not in head]

    SUMMARY_CSV.parent.mkdir(parents=True, exist_ok=True)
    with SUMMARY_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)


def _print_status_breakdown(results):
    from collections import Counter
    c = Counter(r["status"] for r in results)
    for status, n in c.most_common():
        print(f"  {status:16s} {n}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", action="store_true",
                        help="Run all URIs in a multiprocessing.Pool")
    args = parser.parse_args()
    if args.batch:
        run_batch()
    else:
        print("Use --batch for full run, or invoke via pytest.")