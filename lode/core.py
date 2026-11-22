"""Core entry points of the library for callers that name the format with a string.

The CLI and the web service go through these functions: none of them touches the Reader,
the viewers or the builder directly. Library users read with the class of the format
(OwlOntology, SkosVocabulary) and reach the viewer through `artefact.viewer`. The code lives
here and not in `lode/__init__.py` so that the package root only lists the public names.
"""
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Union

from lode import profiles

if TYPE_CHECKING:
    from lode.artefact import Artefact


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
# 2. EXPORT
# ==========================================================================
def export(artefact: "Artefact", fmt: str, resource: Optional[str] = None) -> Union[str, bytes]:
    """Serialize the triples of the artefact, or of one resource, in an rdflib format.

    `fmt` is an rdflib format name ("turtle", "xml", "json-ld", "nt"); the valid
    ones are listed in `lode.helpers.formats.SERIALIZATION_FORMATS`. Only the
    triples of the loaded artefact are returned, never those of its imports.
    """
    viewer = artefact.viewer
    return viewer.export_resource(resource, fmt) if resource else viewer.export_main(fmt)


# ==========================================================================
# 3. BUILD
# ==========================================================================
def build_site(artefact: "Artefact", out_dir: Union[str, Path], *, lang: str = "en",
               artefact_name: str = "index") -> None:
    """Write the static documentation site of an artefact into `out_dir`.

    The viewer is the one of `artefact.profile`. Blocking and disk-heavy: existing
    files in `out_dir` with the same names are overwritten. `artefact_name` is the
    file stem of the root page and its serializations.
    """
    # Local import for the same reason as in read(): the builder pulls in jinja2.
    from lode.builder import build_html

    build_html(artefact.viewer, Path(out_dir), lang=lang, artefact_name=artefact_name)
