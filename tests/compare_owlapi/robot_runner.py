"""ROBOT CLI wrapper. Invokes robot.jar as subprocess for each ontology.

Why subprocess: ROBOT wraps OWLAPI 5.x Manchester (the reference impl).
Fresh JVM per ontology = isolation. Parallelizable across 474-corpus.

Strategy: separate `export` calls per entity category. The 'Type' column
emits OWLAPI EntityType labels (Class, ObjectProperty, DataProperty,
AnnotationProperty, Datatype). For individuals it emits the rdf:type class
instead, so individuals are detected by presence in the dedicated export.
"""
import csv
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Set, Tuple

from .mapping import ROBOT_TYPE_TO_LODE


def _find_robot_jar() -> Path:
    """Locate robot.jar. Search order:
    1. ROBOT_JAR env var
    2. <this_dir>/robot.jar
    3. <repo>/tools/robot.jar
    4. <repo>/robot.jar
    """
    here = Path(__file__).parent
    candidates = []
    env = os.environ.get("ROBOT_JAR")
    if env:
        candidates.append(Path(env))
    candidates += [
        here / "robot.jar",
        here.parent.parent / "tools" / "robot.jar",
        here.parent.parent / "robot.jar",
    ]
    for p in candidates:
        if p.exists():
            return p
    return candidates[0] if env else here / "robot.jar"


ROBOT_JAR = _find_robot_jar()
ROBOT_TIMEOUT_SEC = 60


class RobotError(Exception):
    """ROBOT invocation failed (non-zero exit, timeout, or parse error)."""


def _run_robot(args: list, cwd: Path) -> subprocess.CompletedProcess:
    """Invoke robot.jar with given args. Raises RobotError on failure."""
    cmd = ["java", "-jar", str(ROBOT_JAR)] + args
    try:
        return subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True,
            timeout=ROBOT_TIMEOUT_SEC, check=True,
        )
    except subprocess.TimeoutExpired:
        raise RobotError(f"timeout after {ROBOT_TIMEOUT_SEC}s | cmd_tail={' '.join(args[:3])}")
    except subprocess.CalledProcessError as e:
        err = (e.stderr or "").strip() or (e.stdout or "").strip() or "(no output)"
        raise RobotError(f"exit {e.returncode} | cmd_tail={' '.join(args[:3])} | {err[:600]}")


def extract_entities_and_metrics(input_path: str) -> Tuple[Dict[str, Set[str]], Dict[str, int]]:
    """Run ROBOT on `input_path`, return (entities_by_type, axiom_metrics).

    entities_by_type keys are the OWLAPI EntityType labels:
      Class, ObjectProperty, DataProperty, AnnotationProperty,
      NamedIndividual, Datatype.

    Three exports + one measure:
      1. classes (default): Type column = 'Class'
      2. properties:        Type column = 'ObjectProperty' / 'DataProperty' /
                                          'AnnotationProperty' / 'Datatype'
      3. individuals:       presence in export = NamedIndividual; Type column
                            holds rdf:type class IRIs (ignored here)
      4. measure --metrics extended
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        cls_tsv = tmpdir / "classes.tsv"
        prop_tsv = tmpdir / "properties.tsv"
        ind_tsv = tmpdir / "individuals.tsv"
        measure_tsv = tmpdir / "measure.tsv"

        # 1) Classes. Header 'IRI' (not 'ID') ensures full IRIs in output;
        #    the ID column is always CURIE-formatted regardless of --entity-format.
        _run_robot([
            "export",
            "--input", input_path,
            "--header", "IRI|Type",
            "--include", "classes",
            "--format", "tsv",
            "--export", str(cls_tsv),
        ], cwd=tmpdir)

        # 2) Properties (object/data/annotation; datatypes appear here too,
        #    distinguished by the 'Type' cell value).
        _run_robot([
            "export",
            "--input", input_path,
            "--header", "IRI|Type",
            "--include", "properties",
            "--format", "tsv",
            "--export", str(prop_tsv),
        ], cwd=tmpdir)

        # 3) Individuals
        _run_robot([
            "export",
            "--input", input_path,
            "--header", "IRI|Type",
            "--include", "individuals",
            "--format", "tsv",
            "--export", str(ind_tsv),
        ], cwd=tmpdir)

        # 4) Metrics
        _run_robot([
            "measure",
            "--input", input_path,
            "--format", "tsv",
            "--metrics", "extended",
            "--output", str(measure_tsv),
        ], cwd=tmpdir)

        entities = _parse_entities(cls_tsv, prop_tsv, ind_tsv)
        metrics = _parse_measure_tsv(measure_tsv)
        return entities, metrics


def _parse_entities(cls_tsv: Path, prop_tsv: Path, ind_tsv: Path) -> Dict[str, Set[str]]:
    """Merge per-category exports into {EntityType -> {IRIs}}.

    For classes/properties, use the 'Type' column to disambiguate.
    For individuals, presence in ind_tsv = NamedIndividual (Type column
    contains rdf:type classes, not the entity-type tag).
    """
    out: Dict[str, Set[str]] = {t: set() for t in ROBOT_TYPE_TO_LODE}

    for path in (cls_tsv, prop_tsv):
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                iri = (row.get("IRI") or row.get("ID") or "").strip()
                etype = (row.get("Type") or "").strip()
                if not iri or not etype:
                    continue
                # 'Type' may emit multiple values for punned entities,
                # pipe-separated (default ROBOT --split). Each value is a
                # multi-word OWLAPI label like 'Annotation property'.
                for t in (s.strip() for s in etype.split("|")):
                    if t in out:
                        out[t].add(iri)

    if ind_tsv.exists():
        with ind_tsv.open(encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                iri = (row.get("IRI") or row.get("ID") or "").strip()
                if iri:
                    out["Named individual"].add(iri)

    return out


def _parse_measure_tsv(path: Path) -> Dict[str, int]:
    """Parse `robot measure` TSV. Returns {metric_name -> int_value}."""
    out: Dict[str, int] = {}
    if not path.exists():
        return out
    with path.open(encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        for row in reader:
            if len(row) < 2:
                continue
            name, value = row[0].strip(), row[1].strip()
            try:
                out[name] = int(value)
            except ValueError:
                pass
    return out


def check_robot_available() -> None:
    """Raise RobotError with actionable message if robot.jar / java missing."""
    if not ROBOT_JAR.exists():
        raise RobotError(
            f"robot.jar not found at {ROBOT_JAR}. "
            f"Download from https://github.com/ontodev/robot/releases/tag/v1.9.8"
        )
    if shutil.which("java") is None:
        raise RobotError("java not on PATH. Install JRE/JDK 11+.")