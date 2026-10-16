"""Static-site builder: renders an artefact as a folder of plain HTML pages.

Produces an index page, one page per documented resource and the serializations
of the whole artefact and of each resource, ready to publish on any static host.
"""
import re
import shutil
from pathlib import Path
from urllib.parse import quote
from jinja2 import Environment, FileSystemLoader, select_autoescape
import importlib.resources
from rdflib import URIRef
from rdflib.namespace import split_uri

# internal modules
from lode.viewer.base_viewer import SERIALIZATION_FORMATS
from lode.helpers.html_utils import minify as _minify
from lode.models.model import Model
from lode.exceptions import ArtefactValidationError


_SER = [(f["fmt"], f["ext"]) for f in SERIALIZATION_FORMATS]

def _get_template_env(static_path: str = "static") -> Environment:
    """Create the Jinja2 environment used to render the static pages.

    `static_path` is the relative path from the page to the static folder, so it
    differs between the index and the resource pages. The web app's url_for does
    not exist here, hence the minimal replacement registered below.
    """
    try:
        pkg_path = importlib.resources.files("lode").joinpath("templates")
        template_dir = str(pkg_path)
    except Exception:
        template_dir = str(Path(__file__).parent / "templates")
    
    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(["html"]),
    )
    
    def url_for(name: str, path: str = "") -> str:
        """Resolve static files relative to the page; every other route goes to the root."""
        if name == "static":
            return f"{static_path}/{path}"
        return "/"
    
    env.globals["url_for"] = url_for
    return env

def _prefix_map(graph):
    """Map each namespace IRI of the graph to its prefix ('default' for the empty one)."""
    return {str(ns): (p or 'default') for p, ns in graph.namespaces()}

def _safe_segment(seg: str) -> str:
    """Restrict a slug path segment to a filesystem-safe whitelist.

    Prefix and local name come from IRIs in the loaded ontology, i.e. from
    user-controlled input: path separators, '..', NUL etc. must never reach
    the filesystem (path injection). An empty result means "no usable local
    part" and is treated by callers as a namespace IRI (page skipped).
    """
    seg = re.sub(r"[^A-Za-z0-9._-]", "-", seg).strip("-.")
    if not seg or set(seg) == {"."}:
        return ""
    return seg[:100]


def _rel_slug(uri, graph):
    """Return the 'prefix/local' path of a resource, with both parts made filesystem-safe.

    The local part is empty for a bare namespace IRI: callers skip those.
    """
    prefix, ns, local = graph.namespace_manager.compute_qname(URIRef(str(uri)), generate=True)
    prefix = _safe_segment(prefix or "default") or "default"
    return f"{prefix}/{_safe_segment(local)}"


def _local_name(uri: str) -> str:
    """Return the part of an IRI after '#', or its last path segment."""
    return uri.split('#', 1)[1] if '#' in uri else uri.rstrip('/').rsplit('/', 1)[-1]

def _check_artefact_name(name: str) -> str:
    """Return `name` if it is a plain file stem, else raise.

    The name is user-chosen (CLI) and becomes file names in the output folder
    and links in every page: path separators or '..' would let the root files
    escape the output directory.
    """
    if not re.fullmatch(r"[A-Za-z0-9._-]+", name) or set(name) == {"."}:
        raise ArtefactValidationError(
            "Invalid artefact name: use only letters, digits, '.', '_' and '-' (no extension)",
            context={"artefact_name": name},
        )
    return name


def _copy_static(out_dir: Path) -> None:
    """Copy the package's static assets into the output folder, once.

    An existing static folder is left untouched, so rebuilding does not overwrite it.
    """
    static_src = Path(__file__).parent / "static"
    static_dst = out_dir / "static"
    if static_src.exists() and not static_dst.exists():
        shutil.copytree(static_src, static_dst)

def _write_warnings_report(warnings: list, out_dir: Path) -> None:
    """Write the reader warnings to report.txt in the output folder.

    Written only when there is something to report, so a build without warnings
    leaves no file. An older report.txt is not removed: it may be the user's own.
    """
    if not warnings:
        return
    lines = [f"[{w['code']}] {w['message']}" for w in warnings]
    (out_dir / "report.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

def build_html(viewer, out_dir: Path, lang: str = "en", reader=None,
               artefact_name: str = "index") -> None:
    """Write the whole static site for a viewer into `out_dir`.

    Writes the index page, the serializations of the artefact and, under resources/,
    one page plus serializations for each resource that belongs to the ontology
    namespace or has local triples. Blocking and disk-heavy; existing files are
    overwritten. A page is never written outside resources/, whatever the IRI.
    `artefact_name` is the file stem of the root files (<name>.html, <name>.ttl, ...):
    links back to the index use it, so a renamed index stays reachable. Resource
    files are not affected, they are named after their IRI.
    """
    from collections import defaultdict

    artefact_name = _check_artefact_name(artefact_name)
    out_dir.mkdir(parents=True, exist_ok=True)
    _copy_static(out_dir)
    if reader is not None:
        _write_warnings_report(viewer.format_warnings(reader.get_warnings()), out_dir)

    ontology_ns = viewer._get_ontology_ns()
    graph = reader._graph if reader else viewer.reader._graph
    main_graph = viewer.reader.get_main_graph()

    def _in_main_graph(uri) -> bool:
        """Tell whether the loaded artefact itself says something about this IRI.

        Resources described only by imported modules get no page: their export
        would be empty, as exports carry the triples of the loaded artefact only.
        """
        return (URIRef(str(uri)), None, None) in main_graph

    grouped = defaultdict(list)
    for inst in viewer.get_all_instances():
        grouped[type(inst).__name__].append(inst)

    toc_config = viewer.get_toc_config() if hasattr(viewer, "get_toc_config") else []

    # URI that will actually get a file (same criterion as the loop below)
    materialized = set()
    for class_key, _sid, _t in toc_config:
        for inst in grouped.get(class_key, []):
            u = inst.get_has_identifier()
            if not u:
                continue
            if not (u.startswith(ontology_ns) or _in_main_graph(u)):
                continue
            if _rel_slug(u, graph).rsplit("/", 1)[-1] == "":   # namespace IRI, no local
                continue
            materialized.add(str(u))

    def _keep(uri):
        """Tell whether a resource gets its own page, and so can be linked to."""
        return str(uri) in materialized

    def resource_url_resource(uri, section=None):
        """Link to a resource from a resource page; unpublished IRIs stay absolute."""
        if not _keep(uri):
            return uri
        rel = _rel_slug(uri, graph)
        if rel.rsplit("/", 1)[-1] == "":      # namespace IRI
            return f"../../{artefact_name}.html"
        return f"../{rel}.html"

    def resource_url_index(uri, section=None):
        """Link to a resource from the index page; unpublished IRIs stay absolute."""
        if not _keep(uri):
            return uri
        rel = _rel_slug(uri, graph)
        if rel.rsplit("/", 1)[-1] == "":
            return f"{artefact_name}.html"
        return f"resources/{rel}.html"

    env_index = _get_template_env(static_path="static")
    env_resource = _get_template_env(static_path="../../static")
    
    if reader is not None:
        for fmt, ext in _SER:
            out = reader.get_main_graph().serialize(format=fmt)
            if isinstance(out, bytes):
                out = out.decode("utf-8")
            (out_dir / f"{artefact_name}.{ext}").write_text(out, encoding="utf-8")

    template_index = env_index.get_template("viewer.html")
    template_resource = env_resource.get_template("viewer.html")

    toc_config = viewer.get_toc_config() if hasattr(viewer, "get_toc_config") else []

    # --- index.html ---
    data = viewer.get_view_data(language=lang)
    data["request"] = _FakeRequest("/")
    data["is_static"] = True
    data["resource_url"] = resource_url_index
    data["export_base"] = artefact_name
    (out_dir / f"{artefact_name}.html").write_text(_minify(template_index.render(**data)), encoding="utf-8")
    print(f"  [build] {artefact_name}.html")

    if not toc_config:
        return

    res_dir = out_dir / "resources"
    res_dir.mkdir(parents=True, exist_ok=True)

    for class_key, section_id, _ in toc_config:
        for inst in grouped.get(class_key, []):
            uri = inst.get_has_identifier()
            if not uri:
                continue
            native = uri.startswith(ontology_ns)
            if not (native or _in_main_graph(uri)):
                continue

            rel = _rel_slug(uri, graph)
            if rel.rsplit("/", 1)[-1] == "":   # namespace IRI, no local part
                continue

            page = res_dir / f"{rel}.html"
            # Defense in depth: even if a slug ever slipped through the
            # whitelist, never write outside the resources directory.
            if not page.resolve().is_relative_to(res_dir.resolve()):
                continue
            page.parent.mkdir(parents=True, exist_ok=True)

            for fmt, ext in _SER:
                out = viewer.export_resource(uri, fmt)
                if isinstance(out, bytes):
                    out = out.decode("utf-8")
                (res_dir / f"{rel}.{ext}").write_text(out, encoding="utf-8")

            data_r = viewer.get_view_data(resource_uri=uri, language=lang)
            data_r["request"] = _FakeRequest(f"resources/{rel}.html")
            data_r["is_static"] = True
            data_r["resource_url"] = resource_url_resource
            data_r["export_base"] = _local_name(uri)
            data_r["artefact_name"] = artefact_name
            page.write_text(_minify(template_resource.render(**data_r)), encoding="utf-8")

class _FakeRequest:
    """Minimal stand-in for a web request, so the viewer templates render without a web app."""

    def __init__(self, path: str):
        """Build a GET request for `path` with no query parameters."""
        self.url = _FakeURL(path)
        self.method = "GET"
        self.query_params = _FakeQueryParams()
        self.is_static = True

class _FakeQueryParams:
    """Query parameters that are always empty: a static page has no query string."""

    def get(self, key: str, default: str = "") -> str:
        """Return the default for any key."""
        return default

    # Direct access such as request.query_params.read_as
    def __getattr__(self, key: str) -> str:
        """Return an empty string for any attribute."""
        return ""

class _FakeURL:
    """Minimal URL object exposing only the path, as the templates need."""

    def __init__(self, path: str):
        """Store the page path."""
        self.path = path

    def __str__(self) -> str:
        """Return the page path."""
        return self.path