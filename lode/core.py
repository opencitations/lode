"""Core entry points of the library: read an artefact, show it, export it, build its site.

CLI, web service and Python users all go through these functions: none of them
touches the Reader, the viewers or the builder directly. The code lives here and
not in `lode/__init__.py` so that the package root only lists the public names.
"""
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Union

from lode import profiles

if TYPE_CHECKING:
    from lode.artefact import Artefact
    from lode.viewer.view_data import ViewData


# ==========================================================================
# 1. READ
# ==========================================================================
def read(source: str, read_as: str, *, imported: Optional[bool] = None,
         closure: Optional[bool] = None, partial_import: Optional[bool] = None,
         warnings: bool = False, source_name: Optional[str] = None) -> "Artefact":
    """Read a semantic artefact whose format is given by name, and return it.

    For callers that hold the format as a string, such as the CLI and the web service:
    this is the only place where `read_as` becomes a class. It names an enabled profile,
    matched ignoring case, and the result is that profile's Artefact subclass
    (OwlOntology, SkosVocabulary...); an unknown or disabled format raises
    ArtefactValidationError listing the valid ones. `source` is a local path or a public
    http(s) URL. `imported`, `closure` and `partial_import` load the `owl:imports` of
    the artefact (depth 1, full closure, only the entities in use). `warnings`
    collects the reader warnings in `artefact.warnings`; the current checks are
    OWL-specific. `source_name` names the artefact when `source` is only a local
    copy of it (for example a cached download). Blocking: it may fetch remote
    documents.
    """
    # The profile registry is cheap to import; the class it returns brings in rdflib
    # and the reader only now, so `import lode` and `lode --help` stay fast.
    profile = profiles.get_enabled(read_as)
    return profile.artefact_class()(source, imported=imported, closure=closure,
                                    partial_import=partial_import, warnings=warnings,
                                    source_name=source_name)


# ==========================================================================
# 2. VIEW AND EXPORT
# ==========================================================================

def view(artefact: "Artefact", *, resource: Optional[str] = None,
         lang: Optional[str] = None, links=None) -> "ViewData":
    """Return the data of a page as the viewer contract defines it, for the whole artefact or one resource.

    This is the data a page needs: the page itself (the template, the request, the minification)
    stays in the caller. `links` says where resources and exports live (see lode.viewer.links).
    """
    from lode.viewer import get_viewer  # local import: the viewers pull in the YAML configuration, not needed to read

    return get_viewer(artefact).view(resource_uri=resource, language=lang, links=links)

def template_dirs(artefact: "Artefact") -> list:
    """Return the folders the page templates of this artefact are searched in, first match wins.

    The base templates come last; a format may put in front the ones it replaces. The adapters
    that render pages (web service, static builder) build their Jinja loader from this list.
    """
    from lode.viewer import get_viewer  # local import: the viewers pull in the YAML configuration, not needed to read

    return get_viewer(artefact).template_dirs()

def format_warnings(artefact: "Artefact") -> list:
    """Return the reader warnings of an artefact, worded with the viewer's display names.

    Each item is a dict with "code" and "message". Empty unless the artefact was
    read with `warnings=True`.
    """
    from lode.viewer import get_viewer  # local import: the viewers pull in the YAML configuration, not needed to read

    return get_viewer(artefact).format_warnings(artefact.warnings)


def export(artefact: "Artefact", fmt: str, resource: Optional[str] = None) -> Union[str, bytes]:
    """Serialize the triples of the artefact, or of one resource, in an rdflib format.

    `fmt` is an rdflib format name ("turtle", "xml", "json-ld", "nt"); the valid
    ones are listed in `lode.helpers.formats.SERIALIZATION_FORMATS`. Only the
    triples of the loaded artefact are returned, never those of its imports.
    """
    from lode.viewer import get_viewer  # local import: the viewers pull in the YAML configuration, not needed to read

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
