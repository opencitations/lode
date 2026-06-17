# lode/builder.py
import shutil
from pathlib import Path
from urllib.parse import quote
from jinja2 import Environment, FileSystemLoader, select_autoescape
import importlib.resources


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


def _uri_to_slug(uri: str) -> str:
    for prefix in ('https://', 'http://'):
        if uri.startswith(prefix):
            uri = uri[len(prefix):]
            break
    return uri.replace('/', '_').replace('#', '_')

def _resource_url(uri: str, section: str) -> str:
    """Genera path relativo alla pagina di una risorsa."""
    slug = _uri_to_slug(uri)
    return f"resources/{section}/{slug}.html"


def _copy_static(out_dir: Path) -> None:
    static_src = Path(__file__).parent / "static"
    static_dst = out_dir / "static"
    if static_src.exists() and not static_dst.exists():
        shutil.copytree(static_src, static_dst)


def build_html(viewer, out_dir: Path, lang: str = "en") -> None:
    from collections import defaultdict

    out_dir.mkdir(parents=True, exist_ok=True)
    _copy_static(out_dir)

    env_index = _get_template_env(static_path="static")
    env_resource = _get_template_env(static_path="../../static")

    template_index = env_index.get_template("viewer.html")
    template_resource = env_resource.get_template("viewer.html")

    toc_config = viewer.get_toc_config() if hasattr(viewer, "get_toc_config") else []

    def resource_url_index(uri: str, section: str) -> str:
        return f"resources/{section}/{_uri_to_slug(uri)}.html"

    def resource_url_resource(uri: str, section: str) -> str:
        return f"../../resources/{section}/{_uri_to_slug(uri)}.html"

    # --- index.html ---
    data = viewer.get_view_data(language=lang)
    data["request"] = _FakeRequest("/")
    data["is_static"] = True
    data["resource_url"] = resource_url_index
    html = template_index.render(**data)
    (out_dir / "index.html").write_text(html, encoding="utf-8")
    print(f"  [build] index.html")

    if not toc_config:
        return

    # Raggruppa istanze per nome classe Python
    grouped = defaultdict(list)
    for inst in viewer.get_all_instances():
        grouped[type(inst).__name__].append(inst)

    for class_key, section_id, section_title in toc_config:
        instances = grouped.get(class_key, [])
        if not instances:
            continue

        section_dir = out_dir / "resources" / section_id
        section_dir.mkdir(parents=True, exist_ok=True)

        for inst in instances:
            uri = inst.get_has_identifier()
            if not uri:
                continue

            slug = _uri_to_slug(uri)
            data_r = viewer.get_view_data(resource_uri=uri, language=lang)
            data_r["request"] = _FakeRequest(f"resources/{section_id}/{slug}.html")
            data_r["is_static"] = True
            data_r["resource_url"] = resource_url_resource
            html_r = template_resource.render(**data_r)
            (section_dir / f"{slug}.html").write_text(html_r, encoding="utf-8")

        print(f"  [build] resources/{section_id}/ ({len(instances)} files)")

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