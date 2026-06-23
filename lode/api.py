# lode/api.py
from fastapi import FastAPI, File, UploadFile, Form, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from enum import Enum
from typing import Optional
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
import tempfile
import os
import traceback
import logging
from urllib.parse import urlencode
from functools import lru_cache
from uuid import uuid4
import hashlib

# Configura logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Internal modules
from lode.reader import Reader
from lode.reader import security
from lode.exceptions import LODEError, ArtefactValidationError

# When enabled, error pages include the full traceback (development only).
DEBUG = os.getenv("LODE_DEBUG", "").strip().lower() in ("1", "true", "yes", "on")

app = FastAPI(title="LODE 2.0 API", version="1.0.0")

# Fix Blocked loading mixed active content on style.css
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

templates = Jinja2Templates(directory="lode/templates")
app.mount("/static", StaticFiles(directory="lode/static"), name="static")

# Available semantic artefacts types for API in versin 0.1.X
ENABLED_FORMATS = {"owl"}

class ReadAsFormat(str, Enum):
    owl = "owl"
    rdf = "rdf"
    skos = "skos"

_ACCEPT_TO_SERIALIZATION: dict[str, tuple[str, str, str]] = {
    "text/turtle":            ("turtle", "text/turtle",         "ttl"),
    "application/rdf+xml":    ("xml",    "application/rdf+xml", "rdf"),
    "text/n3":                ("n3",     "text/n3",             "n3"),
}

_EXT_TO_SERIALIZATION = {
    "ttl": ("turtle", "text/turtle",         "ttl"),
    "rdf": ("xml",    "application/rdf+xml", "rdf"),
    "n3":  ("n3",     "text/n3",             "n3"),
}

import time
SPOOL_DIR = os.path.realpath(os.path.join(os.path.dirname(__file__), "spool"))
os.makedirs(SPOOL_DIR, exist_ok=True)
_SPOOL_TTL = 60 * 60

def _spool_path(token: str) -> str:
    # Spool tokens are opaque IDs we mint ourselves (uuid4 hex / "url_"+sha256).
    # Resolve and confirm the path stays inside SPOOL_DIR, so a crafted upload_id
    # cannot traverse out of it (path injection).
    path = os.path.realpath(os.path.join(SPOOL_DIR, f"{token}.rdf"))
    if os.path.commonpath((SPOOL_DIR, path)) != SPOOL_DIR:
        raise ArtefactValidationError("Invalid upload token", context={"token": token})
    return path

def _prune_spool():
    cutoff = time.time() - _SPOOL_TTL
    for name in os.listdir(SPOOL_DIR):
        p = os.path.join(SPOOL_DIR, name)
        try:
            if os.path.getmtime(p) < cutoff:
                os.unlink(p)
        except OSError:
            pass

# ----------------------------------------------------------
#  HELPERS FOR \extract endpoints using cache from the reader
# ----------------------------------------------------------

def _nav_qs(read_as: str, url, upload_id, lang) -> str:
    p = {"read_as": read_as, "lang": lang or ""}
    p["upload_id" if upload_id else "url"] = upload_id or (url or "")
    return urlencode(p)
    
def _render_view(request, reader, *, resource, lang, source_url, upload_id, read_as):
    viewer = reader.get_viewer()
    data = viewer.get_view_data(resource_uri=resource, language=lang)
    data["warnings"] = reader.get_warnings()
    return templates.TemplateResponse("viewer.html", {
        "request": request,
        "source_url": source_url,
        "upload_id": upload_id,
        "nav_qs": _nav_qs(read_as, source_url, upload_id, lang),
        **data,
    })

def _url_token(url, read_as, imported, closure) -> str:
    key = f"{url}|{read_as}|{imported}|{closure}".encode()
    return "url_" + hashlib.sha256(key).hexdigest()[:32]

def _load_url(url, read_as, imported, closure, warnings):
    # Enforce http(s)://host up front: a non-URL value (local path, file://, ...)
    # must never reach the loader and be opened as a local file.
    security.check_url_safe(url)
    _prune_spool()
    token = _url_token(url, read_as, imported, closure)
    path = _spool_path(token)
    if os.path.exists(path):
        # cache hit: ricostruisci dal Turtle salvato
        reader = Reader()
        reader.load_instances(path, read_as, imported=imported, closure=closure, warnings=warnings)
        return reader
    # cache miss: scarica e processa dalla URL
    reader = Reader()
    reader.load_instances(url, read_as, imported=imported, closure=closure, warnings=warnings)
    # persisti il grafo normalizzato per i prossimi hit
    try:
        with open(path, "wb") as f:
            f.write(reader._graph.serialize(format="turtle").encode("utf-8"))
    except OSError:
        pass
    return reader

def _resolve_reader(read_as: str, url, upload_id, imported, closure, warnings):
    if upload_id:
        path = _spool_path(upload_id)
        if not os.path.exists(path):
            raise ArtefactValidationError("Upload expired, please re-upload",
                                        context={"upload_id": upload_id})
        reader = Reader()
        reader.load_instances(path, read_as, imported=imported, closure=closure, warnings=warnings)
        return reader
    if url:
        return _load_url(url, read_as, imported, closure, warnings)
    raise ArtefactValidationError("Missing 'url' or 'upload_id'")

# ----------------------------------------------------------
#  ERROR RENDERING
# ----------------------------------------------------------

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

def _check_format_enabled(read_as: "ReadAsFormat") -> None:
    if read_as.value not in ENABLED_FORMATS:
        raise ArtefactValidationError(
            f"Format '{read_as.value}' is not available yet",
            context={"requested": read_as.value, "supported": sorted(ENABLED_FORMATS)}
        )

@app.middleware("http")
async def limit_upload_size(request: Request, call_next):
    """Reject oversized POST bodies early, before reading them, when the client
    declares a Content-Length. (Chunked bodies omit it: those are still capped
    in read_upload_capped; the hard limit belongs at the reverse proxy.)"""
    if request.method == "POST":
        declared = request.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > security.MAX_BYTES:
            exc = ArtefactValidationError(
                "File too large", context={"bytes": int(declared), "max": security.MAX_BYTES}
            )
            return templates.TemplateResponse(
                "error.html", {"request": request, "error": _error_payload(exc)}, status_code=400
            )
    return await call_next(request)

@app.get("/extract")
async def extract_get(
    request: Request,
    read_as: ReadAsFormat,
    url: Optional[str] = None,   
    upload_id: Optional[str] = None,
    resource: Optional[str] = None,
    lang: Optional[str] = None,
    imported: Optional[bool] = None,
    closure: Optional[bool] = None,
    format: Optional[str] = None, 
    warnings: bool = False
):
        _check_format_enabled(read_as)
        
        reader = _resolve_reader(read_as.value, url, upload_id, imported, closure, warnings)
        
        # Content negotiation
        accept = request.headers.get("accept", "text/html")
        serial = None
        if format and format.lower() in _EXT_TO_SERIALIZATION:
            serial = _EXT_TO_SERIALIZATION[format.lower()]
        elif accept in _ACCEPT_TO_SERIALIZATION:
            serial = _ACCEPT_TO_SERIALIZATION[accept]
        if serial:
            rdflib_fmt, mime_type, ext = serial
            if resource:
                serialized = reader.get_viewer().export_resource(resource, rdflib_fmt)
                filename = resource.rstrip("/").split("#")[-1].split("/")[-1] or "resource"
            else:
                serialized = reader._graph.serialize(format=rdflib_fmt)
                filename = (url.rstrip("/").split("/")[-1] if url else "graph") or "graph"
            return Response(content=serialized, media_type=mime_type,
                            headers={"Content-Disposition": f'inline; filename="{filename}.{ext}"'})

        logger.info(f"=== REQUEST SUCCESS ===")
        return _render_view(request, reader, resource=resource, lang=lang,
                            source_url=url, upload_id=upload_id, read_as=read_as.value)

@app.post("/extract", response_class=HTMLResponse)
async def extract_post(
    request: Request,
    read_as: ReadAsFormat = Form(...),
    file: UploadFile = File(...),
    resource: Optional[str] = Form(None),
    lang: Optional[str] = None,
    imported: Optional[str] = Form(None),
    closure: Optional[str] = Form(None),
    warnings: bool = False,
):
    """Visualizza semantic artefact da file."""
    logger.info(f"=== FILE UPLOAD START ===")
    logger.info(f"Filename: {file.filename}")
    logger.info(f"Format: {read_as.value}")

    # SECURITY CHECKS
    _check_format_enabled(read_as)
    security.check_extension(file.filename)
    content = await security.read_upload_capped(file)
    security.check_is_text(content)
    security.check_safe_xml(content.decode("utf-8-sig"))

    _prune_spool()
    token = uuid4().hex
    path = _spool_path(token)
    with open(path, "wb") as f:
        f.write(content)

    reader = Reader()
    reader.load_instances(path, read_as.value, imported=imported, closure=closure, warnings=warnings)
    return _render_view(request, reader, resource=resource, lang=lang,
                        source_url=None, upload_id=token, read_as=read_as.value)

@app.get("/", response_class=HTMLResponse)
async def input_web_interface(request: Request):
    """Interfaccia web per l'API"""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "formats": [format.value for format in ReadAsFormat]
    })

@app.get("/health")
async def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)