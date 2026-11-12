"""Core entry points of the library: read an artefact, show it, export it, build its site.

CLI, web service and Python users all go through these functions: none of them
touches the Reader, the viewers or the builder directly. The code lives here and
not in `lode/__init__.py` so that the package root only lists the public names.
"""
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Union

if TYPE_CHECKING:
    from lode.artefact import Artefact


# ==========================================================================
# 1. READ
# ==========================================================================
def read(source: str, read_as: str, *, imported: Optional[bool] = None,
         closure: Optional[bool] = None, partial_import: Optional[bool] = None,
         warnings: bool = False, source_name: Optional[str] = None) -> "Artefact":
    """Read a semantic artefact and return it as an Artefact.

    `source` is a local path or a public http(s) URL; `read_as` is "owl", "skos"
    or "rdf". `imported`, `closure` and `partial_import` load the `owl:imports` of
    the artefact (depth 1, full closure, only the entities in use). `warnings`
    collects the reader warnings in `artefact.warnings`; the current checks are
    OWL-specific. `source_name` names the artefact when `source` is only a local
    copy of it (for example a cached download). Blocking: it may fetch remote
    documents.
    """
    # Local import on purpose: `import lode` must stay cheap for the CLI and for
    # `lode --help`, which should not pay for rdflib and the reader.
    from lode.reader import Reader

    reader = Reader()
    reader.load_instances(source, read_as, imported=imported, closure=closure,
                          partial_import=partial_import, warnings=warnings,
                          source_name=source_name)
    return reader.get_artefact()


# ==========================================================================
# 2. VIEW AND EXPORT
# ==========================================================================
def view_data(artefact: "Artefact", *, resource: Optional[str] = None,
              lang: Optional[str] = None) -> dict:
    """Return the dictionary the HTML templates render, for the whole artefact or one resource.

    The reader warnings are included under "warnings", already worded with the
    display names of the viewer. This is the data a web page needs: the page
    itself (Jinja2, request, minification) stays in the caller.
    """
    # Local import: the viewers pull in the YAML configuration, not needed to read.
    from lode.viewer import get_viewer

    viewer = get_viewer(artefact)
    data = viewer.get_view_data(resource_uri=resource, language=lang)
    data["warnings"] = viewer.format_warnings(artefact.warnings)
    return data


def format_warnings(artefact: "Artefact") -> list:
    """Return the reader warnings of an artefact, worded with the viewer's display names.

    Each item is a dict with "code" and "message". Empty unless the artefact was
    read with `warnings=True`.
    """
    from lode.viewer import get_viewer  # local import: see view_data()

    return get_viewer(artefact).format_warnings(artefact.warnings)


def export(artefact: "Artefact", fmt: str, resource: Optional[str] = None) -> Union[str, bytes]:
    """Serialize the triples of the artefact, or of one resource, in an rdflib format.

    `fmt` is an rdflib format name ("turtle", "xml", "json-ld", "nt"); the valid
    ones are listed in `lode.helpers.formats.SERIALIZATION_FORMATS`. Only the
    triples of the loaded artefact are returned, never those of its imports.
    """
    from lode.viewer import get_viewer  # local import: see view_data()

    viewer = get_viewer(artefact)
    return viewer.export_resource(resource, fmt) if resource else viewer.export_main(fmt)


# ==========================================================================
# 3. BUILD
# ==========================================================================
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
