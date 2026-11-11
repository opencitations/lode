"""Layer boundaries: models and viewers must not depend on the reader.

The Reader builds an Artefact and the viewers read only from it; these tests
read the source files, so they need no network and no fixtures.
"""
import ast
from pathlib import Path

LODE = Path(__file__).resolve().parent.parent / "lode"


def _imports(path: Path) -> set:
    """Return the modules imported anywhere in a file, lazy imports included."""
    names = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module)
    return names


def _offenders(package: str, forbidden: str, allowed: tuple = ()) -> list:
    """List the files of `package` that import `forbidden`, except those in `allowed`."""
    bad = []
    for path in (LODE / package).rglob("*.py"):
        if path.name in allowed:
            continue
        for name in _imports(path):
            if name == forbidden or name.startswith(forbidden + "."):
                bad.append(f"{path.relative_to(LODE)} imports {name}")
    return bad


def test_viewer_does_not_import_reader():
    """Viewers get everything from the Artefact, never from the reader package."""
    assert _offenders("viewer", "lode.reader") == []


def test_models_do_not_import_reader_or_viewer():
    """The model is the lowest layer: it knows neither who fills it nor who shows it."""
    assert _offenders("models", "lode.reader") == []
    assert _offenders("models", "lode.viewer") == []


def test_reader_does_not_import_viewer():
    """The reader never depends on the viewers: the factory lives in lode.viewer."""
    assert _offenders("reader", "lode.viewer") == []
