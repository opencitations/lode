# lode/api.py
"""LODE 2.0 — HTTP API.

Endpoints:
    GET  /               web form
    GET  /health         liveness probe
    GET  /extract        render an artefact (HTML, or RDF via content negotiation)
    POST /extract        same, from an uploaded file
    GET  /build          static documentation site, as a ZIP archive
    POST /build          same, from an uploaded file
"""

# ==========================================================================
# 1. IMPORTS
# ==========================================================================
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode
from uuid import uuid4
import hashlib
import logging
import os
import re
import shutil
import tempfile
import threading
import time
import traceback

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool
from starlette.middleware.gzip import GZipMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
import minify_html

# Internal modules
from lode.reader import Reader
from lode.reader import security
from lode.exceptions import LODEError, ArtefactValidationError
from lode.viewer.base_viewer import SERIALIZATION_FORMATS


# ==========================================================================
# 2. APP SETUP
# ==========================================================================
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# When enabled, error pages include the full traceback (development only).
DEBUG = os.getenv("LODE_DEBUG", "").strip().lower() in ("1", "true", "yes", "on")

app = FastAPI(title="LODE 2.0 API", version="1.0.0")

# Compress HTML responses on the wire.
app.add_middleware(GZipMiddleware, minimum_size=1000)
# Fix "blocked loading mixed active content" on style.css behind a proxy.
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

templates = Jinja2Templates(directory="lode/templates")
app.mount("/static", StaticFiles(directory="lode/static"), name="static")

# Beautify produced HTML.
templates.env.trim_blocks = True
templates.env.lstrip_blocks = True


# ==========================================================================
# 3. FORMATS
# ==========================================================================
# Semantic artefact types enabled in version 0.1.X
ENABLED_FORMATS = {"owl"}


class ReadAsFormat(str, Enum):
    owl = "owl"
    rdf = "rdf"
    skos = "skos"

def _check_format_enabled(read_as: "ReadAsFormat") -> None:
    if read_as.value not in ENABLED_FORMATS:
        raise ArtefactValidationError(
            f"Format '{read_as.value}' is not available yet",
            context={"requested": read_as.value, "supported": sorted(ENABLED_FORMATS)},
        )

# ==========================================================================
# 4. SPOOL — disk cache for uploads and fetched URLs
# ==========================================================================
SPOOL_DIR = os.path.realpath(os.path.join(os.path.dirname(__file__), "spool"))
os.makedirs(SPOOL_DIR, exist_ok=True)
_SPOOL_TTL = 4 * 60 * 60      # entries are cached for 4 hours
_SPOOL_MAX_BYTES = 1024 ** 3  # 1 GB total budget shared by uploads + URLs


def _spool_path(token: str) -> str:
    # Spool tokens are opaque IDs we mint ourselves (uuid4 hex / "url_"+sha256).
    # Resolve and confirm the path stays inside SPOOL_DIR, so a crafted upload_id
    # cannot traverse out of it (path injection).
    path = os.path.realpath(os.path.join(SPOOL_DIR, f"{token}.rdf"))
    if os.path.commonpath((SPOOL_DIR, path)) != SPOOL_DIR:
        raise ArtefactValidationError("Invalid upload token", context={"token": token})
    return path


def _prune_spool():
    """Evict expired entries, then enforce the total-size budget by deleting the
    oldest (by cache-write time) until back under the cap. Uploads and URL caches
    share the same budget. Best-effort across workers (races caught via OSError).
    """
    cutoff = time.time() - _SPOOL_TTL
    survivors = []  # (mtime, size, path) of entries still within the TTL
    for name in os.listdir(SPOOL_DIR):
        p = os.path.join(SPOOL_DIR, name)
        try:
            st = os.stat(p)
        except OSError:
            continue
        if st.st_mtime < cutoff:
            try:
                os.unlink(p)
            except OSError:
                pass
            continue
        survivors.append((st.st_mtime, st.st_size, p))

    total = sum(size for _, size, _ in survivors)
    if total <= _SPOOL_MAX_BYTES:
        return
    survivors.sort()  # oldest cache-write time first
    for _, size, p in survivors:
        if total <= _SPOOL_MAX_BYTES:
            break
        try:
            os.unlink(p)
            total -= size
        except OSError:
            pass


# ==========================================================================
# 5. BUILD WORKSPACE — quota and concurrency for /build
# ==========================================================================
# Builds write hundreds of files each, so they get their own directory with an
# explicit budget instead of filling up /tmp.
BUILD_DIR = os.path.realpath(
    os.getenv("LODE_BUILD_DIR", os.path.join(os.path.dirname(__file__), "builds"))
)
os.makedirs(BUILD_DIR, exist_ok=True)
_BUILD_TTL = 30 * 60                          # orphans (aborted downloads) age out
_BUILD_MAX_BYTES = 2 * 1024 ** 3              # 2 GB for all pending builds
_BUILD_SLOTS = threading.BoundedSemaphore(2)  # concurrent builds, per worker process
_BUILD_WAIT = 5                               # seconds a request waits for a slot


def _prune_builds() -> int:
    """Drop orphaned build directories and return the bytes still in use.

    A build is orphaned when its BackgroundTask never fired, i.e. the client
    opened the connection and never finished reading the archive.
    """
    cutoff = time.time() - _BUILD_TTL
    total = 0
    for name in os.listdir(BUILD_DIR):
        p = os.path.join(BUILD_DIR, name)
        try:
            st = os.stat(p)
        except OSError:
            continue
        if st.st_mtime < cutoff:
            shutil.rmtree(p, ignore_errors=True)
            continue
        for root, _dirs, files in os.walk(p):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
    return total


# ==========================================================================
# 6. HTML HELPERS
# ==========================================================================
def _minify(html: str) -> str:
    # 1. estrai e metti da parte i blocchi render-markdown (newline-sensitive)
    stash = []

    def _hold(m):
        stash.append(m.group(0))
        return f"\x00MD{len(stash)-1}\x00"

    protected = re.sub(
        r'<(span|div|a|p)\b[^>]*\brender-markdown\b[^>]*>.*?</\1>',
        _hold, html, flags=re.S,
    )
    # 2. minifica la struttura
    out = minify_html.minify(protected, minify_css=False, minify_js=False)
    # 3. reinserisci i blocchi intatti
    for i, block in enumerate(stash):
        out = out.replace(f"\x00MD{i}\x00", block)
    return out

def _nav_qs(read_as: str, url, upload_id, lang, imported, closure) -> str:
    p = {"read_as": read_as, "lang": lang or ""}
    p["upload_id" if upload_id else "url"] = upload_id or (url or "")
    if imported:
        p["imported"] = "true"
    if closure:
        p["closure"] = "true"
    return urlencode(p)

def _render_view(request, reader, *, resource, lang, source_url, upload_id, read_as,
                 imported=None, closure=None):
    viewer = reader.get_viewer()
    data = viewer.get_view_data(resource_uri=resource, language=lang)
    data["warnings"] = reader.get_warnings()
    resp = templates.TemplateResponse("viewer.html", {
        "request": request,
        "source_url": source_url,
        "upload_id": upload_id,
        "nav_qs": _nav_qs(read_as, source_url, upload_id, lang, imported, closure),
        **data,
    })
    resp.body = _minify(resp.body.decode("utf-8")).encode("utf-8")
    resp.headers["content-length"] = str(len(resp.body))
    return resp


# ==========================================================================
# 7. READER RESOLUTION
# ==========================================================================
def _url_token(url, read_as, imported, closure) -> str:
    key = f"{url}|{read_as}|{imported}|{closure}".encode()
    return "url_" + hashlib.sha256(key).hexdigest()[:32]


def _load_url(url, read_as, imported, closure, warnings, use_cache=True):
    # Enforce http(s)://host up front: a non-URL value (local path, file://, ...)
    # must never reach the loader and be opened as a local file.
    security.check_url_safe(url)
    _prune_spool()
    token = _url_token(url, read_as, imported, closure)
    path = _spool_path(token)
    if use_cache and os.path.exists(path):
        # cache hit: ricostruisci dal Turtle salvato
        reader = Reader()
        reader.load_instances(path, read_as, imported=imported, closure=closure,
                              warnings=warnings)
        return reader
    if not use_cache:
        # cache=false: drop the stale copy so the fresh fetch replaces it
        try:
            os.unlink(path)
        except OSError:
            pass
    # cache miss (or forced refresh): scarica e processa dalla URL
    reader = Reader()
    reader.load_instances(url, read_as, imported=imported, closure=closure,
                          warnings=warnings)
    # persisti il grafo normalizzato per i prossimi hit
    try:
        with open(path, "wb") as f:
            f.write(reader._graph.serialize(format="turtle").encode("utf-8"))
    except OSError:
        pass
    return reader


def _resolve_reader(read_as: str, url, upload_id, imported, closure, warnings,
                    use_cache=True):
    if upload_id:
        # Uploads are not re-fetched, so the cache flag does not apply to them.
        path = _spool_path(upload_id)
        if not os.path.exists(path):
            raise ArtefactValidationError("Upload expired, please re-upload",
                                          context={"upload_id": upload_id})
        reader = Reader()
        reader.load_instances(path, read_as, imported=imported, closure=closure,
                              warnings=warnings)
        return reader
    if url:
        return _load_url(url, read_as, imported, closure, warnings, use_cache=use_cache)
    raise ArtefactValidationError("Missing 'url' or 'upload_id'")


def _spool_upload(content: bytes) -> str:
    """Persist a validated upload and return its spool token."""
    _prune_spool()
    token = uuid4().hex
    with open(_spool_path(token), "wb") as f:
        f.write(content)
    return token


async def _read_validated_upload(file: UploadFile) -> bytes:
    """Run every upload check in one place, then return the raw bytes."""
    security.check_extension(file.filename)
    content = await security.read_upload_capped(file)
    security.check_is_text(content)
    security.check_safe_xml(content.decode("utf-8-sig"))
    return content


# ==========================================================================
# 8. ZIP BUILD HELPERS
# ==========================================================================
def _slug(name: Optional[str]) -> str:
    """Safe directory/file stem derived from a URL or filename.

    Must never yield '.' or '..': those would let make_archive(base_dir=...)
    escape the build directory and archive its parent.
    """
    if not name:
        return "ontology"
    raw = name.rstrip("/").split("#")[0].split("/")[-1]
    raw = re.sub(r"\.(ttl|rdf|owl|n3|nt|jsonld|xml)$", "", raw, flags=re.I)
    raw = re.sub(r"[^A-Za-z0-9._-]", "-", raw).strip("-.")
    if not raw or raw in {".", ".."}:
        return "ontology"
    return raw[:64]


def _zip_response(reader, slug: str, lang: Optional[str] = None) -> FileResponse:
    """Render the whole static site and return it as a ZIP download.

    Blocking and disk-heavy: callers must keep it off the event loop.
    """
    from lode.builder import build_html  # lazy: evita l'import circolare

    if not _BUILD_SLOTS.acquire(timeout=_BUILD_WAIT):
        raise HTTPException(503, "Server busy: too many concurrent builds",
                            headers={"Retry-After": "30"})
    workdir = None
    try:
        if _prune_builds() > _BUILD_MAX_BYTES:
            raise HTTPException(503, "Build storage full, retry shortly",
                                headers={"Retry-After": "60"})

        workdir = tempfile.mkdtemp(prefix="build_", dir=BUILD_DIR)
        site_dir = Path(workdir) / slug
        site_dir.mkdir(parents=True, exist_ok=True)

        build_html(reader.get_viewer(), site_dir, lang=lang or "en", reader=reader)

        zip_path = shutil.make_archive(
            os.path.join(workdir, f"{slug}-lode"), "zip",
            root_dir=workdir, base_dir=slug,
        )
        # The loose pages are redundant once archived: halve the disk peak.
        shutil.rmtree(site_dir, ignore_errors=True)
    except BaseException:
        if workdir:
            shutil.rmtree(workdir, ignore_errors=True)
        raise
    finally:
        # Free the slot as soon as the build ends, not when the client is done
        # downloading: a slow reader must not hold a build slot hostage.
        _BUILD_SLOTS.release()

    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=f"{slug}-lode.zip",
        background=BackgroundTask(shutil.rmtree, workdir, True),
    )


# ==========================================================================
# 9. ERROR RENDERING
# ==========================================================================
def _error_payload(exc: Exception) -> dict:
    is_lode = isinstance(exc, LODEError)
    return {
        "type": type(exc).__name__,
        "message": str(exc),
        "context": exc.context if is_lode else {},
        "request_id": exc.request_id if is_lode else None,
        # Never leak the traceback to the user in production: it is always logged
        # server-side; it is only surfaced in the page when LODE_DEBUG is set.
        "traceback": traceback.format_exc() if (not is_lode and DEBUG) else None,
    }


@app.exception_handler(LODEError)
async def lode_error_handler(request: Request, exc: LODEError):
    logger.error(f"{type(exc).__name__}: {exc}")
    return templates.TemplateResponse(
        "error.html", {"request": request, "error": _error_payload(exc)}, status_code=400
    )


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, exc: Exception):
    logger.exception("Unexpected error")
    return templates.TemplateResponse(
        "error.html", {"request": request, "error": _error_payload(exc)}, status_code=500
    )


# ==========================================================================
# 10. MIDDLEWARE
# ==========================================================================
@app.middleware("http")
async def limit_upload_size(request: Request, call_next):
    """Reject oversized POST bodies early, before reading them, when the client
    declares a Content-Length. (Chunked bodies omit it: those are still capped
    in read_upload_capped; the hard limit belongs at the reverse proxy.)"""
    if request.method == "POST":
        declared = request.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > security.MAX_BYTES:
            exc = ArtefactValidationError(
                "File too large",
                context={"bytes": int(declared), "max": security.MAX_BYTES},
            )
            return templates.TemplateResponse(
                "error.html", {"request": request, "error": _error_payload(exc)},
                status_code=400,
            )
    return await call_next(request)


# ==========================================================================
# 11. ROUTES — pages
# ==========================================================================
@app.get("/", response_class=HTMLResponse)
async def input_web_interface(request: Request):
    """Interfaccia web per l'API"""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "formats": [format.value for format in ReadAsFormat],
        "enabled_formats": sorted(ENABLED_FORMATS),
    })


@app.get("/health")
async def health_check():
    return {"status": "ok"}


# ==========================================================================
# 12. ROUTES — /extract
# ==========================================================================
@app.get("/extract")
def extract_get(
    request: Request,
    read_as: ReadAsFormat,
    url: Optional[str] = None,
    upload_id: Optional[str] = None,
    resource: Optional[str] = None,
    lang: Optional[str] = None,
    imported: Optional[bool] = None,
    closure: Optional[bool] = None,
    format: Optional[str] = None,
    warnings: bool = False,
    cache: bool = True,
):
    _check_format_enabled(read_as)

    reader = _resolve_reader(read_as.value, url, upload_id, imported, closure,
                             warnings, use_cache=cache)

    # Content negotiation
    accept = request.headers.get("accept", "text/html")
    serial = None

    if format:
        fmt_l = format.lower()
        serial = next((f for f in SERIALIZATION_FORMATS if f["ext"] == fmt_l), None)
    else:
        for part in accept.split(","):
            mime = part.split(";", 1)[0].strip()
            serial = next((f for f in SERIALIZATION_FORMATS if f["mime"] == mime), None)
            if serial:
                break

    if serial:
        if resource:
            serialized = reader.get_viewer().export_resource(resource, serial["fmt"])
            filename = resource.rstrip("/").split("#")[-1].split("/")[-1] or "resource"
        else:
            serialized = reader._graph.serialize(format=serial["fmt"])
            filename = (url.rstrip("/").split("/")[-1] if url else "graph") or "graph"
        return Response(content=serialized, media_type=serial["mime"],
                        headers={"Content-Disposition": f'inline; filename="{filename}.{serial["ext"]}"'})
    
    logger.info("=== REQUEST SUCCESS ===")
    return _render_view(request, reader, resource=resource, lang=lang,
                        source_url=url, upload_id=upload_id, read_as=read_as.value,
                        imported=imported, closure=closure)


@app.post("/extract", response_class=HTMLResponse)
async def extract_post(
    request: Request,
    read_as: ReadAsFormat = Form(...),
    file: UploadFile = File(...),
    resource: Optional[str] = Form(None),
    lang: Optional[str] = Form(None),
    imported: Optional[str] = Form(None),
    closure: Optional[str] = Form(None),
    warnings: bool = Form(False),
):
    """Visualizza semantic artefact da file."""
    logger.info("=== FILE UPLOAD START ===")
    logger.info(f"Filename: {file.filename}")
    logger.info(f"Format: {read_as.value}")

    _check_format_enabled(read_as)
    content = await _read_validated_upload(file)
    token = _spool_upload(content)

    reader = Reader()
    await run_in_threadpool(
        reader.load_instances, _spool_path(token), read_as.value,
        imported=imported, closure=closure, warnings=warnings,
    )
    return _render_view(request, reader, resource=resource, lang=lang,
                        source_url=None, upload_id=token, read_as=read_as.value,
                        imported=imported, closure=closure)


# ==========================================================================
# 13. ROUTES — /build
# ==========================================================================
@app.get("/build")
def build_get(
    read_as: ReadAsFormat,
    url: Optional[str] = None,
    upload_id: Optional[str] = None,
    lang: Optional[str] = None,
    imported: Optional[bool] = None,
    closure: Optional[bool] = None,
    warnings: bool = False,
    cache: bool = True,
):
    """Static documentation site as a ZIP. Sync on purpose: FastAPI runs
    non-async endpoints in the threadpool, keeping the event loop free."""
    _check_format_enabled(read_as)
    reader = _resolve_reader(read_as.value, url, upload_id, imported, closure,
                             warnings, use_cache=cache)
    return _zip_response(reader, _slug(url), lang)


@app.post("/build")
async def build_post(
    read_as: ReadAsFormat = Form(...),
    file: UploadFile = File(...),
    lang: Optional[str] = Form(None),
    imported: Optional[str] = Form(None),
    closure: Optional[str] = Form(None),
    warnings: bool = Form(False),
):
    _check_format_enabled(read_as)
    content = await _read_validated_upload(file)
    token = _spool_upload(content)

    reader = Reader()
    await run_in_threadpool(
        reader.load_instances, _spool_path(token), read_as.value,
        imported=imported, closure=closure, warnings=warnings,
    )
    return await run_in_threadpool(_zip_response, reader, _slug(file.filename), lang)


# ==========================================================================
# 14. ENTRY POINT
# ==========================================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)