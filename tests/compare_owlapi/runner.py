"""Per-ontology comparison runner.

Module-level function (`compare_one`) so multiprocessing.Pool can pickle it
on Windows (spawn start method).
"""
import json
import logging
import tempfile
from pathlib import Path
from typing import Optional

import requests

from .robot_runner import (
    extract_entities_and_metrics, RobotError, check_robot_available,
)
from .lode_extractor import extract_entity_iris, extract_unmapped_classes
from .differ import build_report


REPORTS_DIR = Path(__file__).parent / "reports"
DOWNLOAD_TIMEOUT_SEC = 30


def _safe_filename(uri: str) -> str:
    """URI -> filesystem-safe stem (used for cache and report filenames)."""
    return "".join(c if c.isalnum() else "_" for c in uri).strip("_")[:200]


def _download(uri: str, dest: Path) -> None:
    """Fetch ontology with content negotiation. Raises on non-200 or network err."""
    headers = {
        "Accept": (
            "text/turtle, application/rdf+xml, application/ld+json, "
            "application/n-triples, */*;q=0.1"
        )
    }
    r = requests.get(uri, headers=headers, timeout=DOWNLOAD_TIMEOUT_SEC,
                     allow_redirects=True)
    r.raise_for_status()
    dest.write_bytes(r.content)


def _run_lode(local_path: str):
    """Parse with LODE reader, return populated logic. Imports applied lazily."""
    from lode.reader import Reader
    reader = Reader()
    reader.load_instances(local_path, "owl")
    return reader._logic


def compare_one(uri: str) -> dict:
    """Full pipeline for one ontology. Always returns a dict; never raises.

    On failure: dict has 'error' key and minimal context. Caller aggregates.
    """
    import shutil
    result = {"uri": uri, "status": "ok"}
    report_path = REPORTS_DIR / f"{_safe_filename(uri)}.json"

    # Use mkdtemp + manual cleanup instead of TemporaryDirectory context manager.
    # On Windows under multiprocessing.Pool with 8 workers, the context manager
    # cleanup has been observed to race with ROBOT subprocess access.
    tmp = tempfile.mkdtemp(prefix="lode_owlapi_")
    local_file = Path(tmp) / "ontology.owl"
    try:
        # 1) Download once, share with both pipelines
        try:
            _download(uri, local_file)
        except Exception as e:
            result.update(status="download_error", error=str(e)[:300])
            _write_report(report_path, result)
            return result

        # Sanity check: the downloaded file must exist and be non-empty
        if not local_file.exists() or local_file.stat().st_size == 0:
            result.update(status="download_error",
                          error=f"empty or missing file at {local_file}")
            _write_report(report_path, result)
            return result

        # 2) ROBOT (OWLAPI reference)
        try:
            robot_iris, robot_metrics = extract_entities_and_metrics(str(local_file))
        except RobotError as e:
            result.update(status="robot_error", error=str(e)[:300])
            _write_report(report_path, result)
            return result

        # 3) LODE
        try:
            logic = _run_lode(str(local_file))
        except Exception as e:
            result.update(status="lode_error", error=str(e)[:300])
            _write_report(report_path, result)
            return result

        # 4) Diff and persist
        try:
            lode_iris = extract_entity_iris(logic)
            unmapped = extract_unmapped_classes(logic)
            full = build_report(uri, lode_iris, robot_iris, robot_metrics,
                                logic, unmapped)
            _write_report(report_path, full)
            result["report_path"] = str(report_path)
        finally:
            # Clean LODE caches (memory hygiene in worker)
            try:
                logic._instance_cache.clear()
                logic._triples_map.clear()
            except Exception:
                pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    return result


def _write_report(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str))


def preflight() -> Optional[str]:
    """Verify ROBOT/Java available. Return error string or None."""
    try:
        check_robot_available()
        return None
    except RobotError as e:
        return str(e)