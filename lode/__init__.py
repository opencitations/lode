"""LODE: Live OWL Documentation Environment, maintained by OpenCitations."""

"""LODE: Live OWL Documentation Environment, maintained by OpenCitations.

Typical use as a library:

    import lode

    artefact = lode.read("vocabulary.ttl", "skos")
    for concept in artefact.instances("Concept"):
        print(concept.get_has_identifier())

    lode.build_site(artefact, "site")
"""
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Union

if TYPE_CHECKING:
    from lode.artefact import Artefact

__all__ = ["read", "build_site"]


def read(source: str, read_as: str, *, imported: Optional[bool] = None,
         closure: Optional[bool] = None, partial_import: Optional[bool] = None,
         warnings: bool = False) -> "Artefact":
    """Read a semantic artefact and return it as an Artefact.

    `source` is a local path or a public http(s) URL; `read_as` is "owl", "skos"
    or "rdf". `imported`, `closure` and `partial_import` load the `owl:imports` of
    the artefact (depth 1, full closure, only the entities in use). `warnings`
    collects the reader warnings in `artefact.warnings`; the current checks are
    OWL-specific. Blocking: it may fetch remote documents.
    """
    # Local imports on purpose: `import lode` must stay cheap for the CLI and
    # for `lode --help`, which should not pay for rdflib and the reader.
    from lode.reader import Reader

    reader = Reader()
    reader.load_instances(source, read_as, imported=imported, closure=closure,
                          partial_import=partial_import, warnings=warnings)
    return reader.get_artefact()


def build_site(artefact: "Artefact", out_dir: Union[str, Path], *, lang: str = "en",
               artefact_name: str = "index") -> None:
    """Write the static documentation site of an artefact into `out_dir`.

    The viewer is chosen from `artefact.read_as`. Blocking and disk-heavy: existing
    files in `out_dir` with the same names are overwritten. `artefact_name` is the
    file stem of the root page and its serializations.
    """
    # Local imports for the same reason as in read(): the builder pulls in jinja2.
    from lode.builder import build_html
    from lode.viewer import get_viewer

    build_html(get_viewer(artefact), Path(out_dir), lang=lang, artefact_name=artefact_name)
