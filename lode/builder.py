# lode/builder.py
import re
import shutil
from pathlib import Path
from urllib.parse import quote
from jinja2 import Environment, FileSystemLoader, select_autoescape
import importlib.resources
from lode.api import _minify
from lode.models.model import Model
from rdflib import URIRef
from rdflib.namespace import split_uri
from lode.viewer.base_viewer import SERIALIZATION_FORMATS

_SER = [(f["fmt"], f["ext"]) for f in SERIALIZATION_FORMATS]

def _get_template_env(static_path: str = "static") -> Environment:
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
        if name == "static":
            return f"{static_path}/{path}"
        return "/"
    
    env.globals["url_for"] = url_for
    return env

def _prefix_map(graph):
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
    prefix, ns, local = graph.namespace_manager.compute_qname(URIRef(str(uri)), generate=True)
    prefix = _safe_segment(prefix or "default") or "default"
    return f"{prefix}/{_safe_segment(local)}"


def _local_name(uri: str) -> str:
    return uri.split('#', 1)[1] if '#' in uri else uri.rstrip('/').rsplit('/', 1)[-1]

def _copy_static(out_dir: Path) -> None:
    static_src = Path(__file__).parent / "static"
    static_dst = out_dir / "static"
    if static_src.exists() and not static_dst.exists():
        shutil.copytree(static_src, static_dst)

def build_html(viewer, out_dir: Path, lang: str = "en", reader=None) -> None:
    from collections import defaultdict

    out_dir.mkdir(parents=True, exist_ok=True)
    _copy_static(out_dir)
    
    ontology_ns = viewer._get_ontology_ns()
    graph = reader._graph if reader else viewer.reader._graph

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
            if not (u.startswith(ontology_ns) or viewer._has_local_triples(u)):
                continue
            if _rel_slug(u, graph).rsplit("/", 1)[-1] == "":   # namespace IRI, no local
                continue
            materialized.add(str(u))

    def _keep(uri):
        return str(uri) in materialized

    def resource_url_resource(uri, section=None):
        if not _keep(uri):
            return uri
        rel = _rel_slug(uri, graph)
        if rel.rsplit("/", 1)[-1] == "":      # namespace IRI
            return "../../index.html"
        return f"../{rel}.html"

    def resource_url_index(uri, section=None):
        if not _keep(uri):
            return uri
        rel = _rel_slug(uri, graph)
        if rel.rsplit("/", 1)[-1] == "":
            return "index.html"
        return f"resources/{rel}.html"

    env_index = _get_template_env(static_path="static")
    env_resource = _get_template_env(static_path="../../static")
    
    if reader is not None:
        for fmt, ext in _SER:
            out = reader._graph.serialize(format=fmt)
            if isinstance(out, bytes):
                out = out.decode("utf-8")
            (out_dir / f"ontology.{ext}").write_text(out, encoding="utf-8")

    template_index = env_index.get_template("viewer.html")
    template_resource = env_resource.get_template("viewer.html")

    toc_config = viewer.get_toc_config() if hasattr(viewer, "get_toc_config") else []

    # --- index.html ---
    data = viewer.get_view_data(language=lang)
    data["request"] = _FakeRequest("/")
    data["is_static"] = True
    data["resource_url"] = resource_url_index
    data["export_base"] = "ontology"
    (out_dir / "index.html").write_text(_minify(template_index.render(**data)), encoding="utf-8")
    print("  [build] index.html")

    if not toc_config:
        return

    res_dir = out_dir / "resources"
    res_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for class_key, section_id, _ in toc_config:
        for inst in grouped.get(class_key, []):
            uri = inst.get_has_identifier()
            if not uri:
                continue
            native = uri.startswith(ontology_ns)
            if not (native or viewer._has_local_triples(uri)):
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
            page.write_text(_minify(template_resource.render(**data_r)), encoding="utf-8")
            count += 1

class _FakeRequest:
    def __init__(self, path: str):
        self.url = _FakeURL(path)
        self.method = "GET"
        self.query_params = _FakeQueryParams()
        self.is_static = True

class _FakeQueryParams:
    def get(self, key: str, default: str = "") -> str:
        return default

    # Accesso diretto tipo request.query_params.read_as
    def __getattr__(self, key: str) -> str:
        return ""

class _FakeURL:
    def __init__(self, path: str):
        self.path = path

    def __str__(self) -> str:
        return self.path