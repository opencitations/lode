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

# ----------------------------------------------------------
#  HELPERS FOR \extract endpoints using cache from the reader
# ----------------------------------------------------------

def _nav_qs(read_as: str, url, upload_id, lang) -> str:
    p = {"read_as": read_as, "lang": lang or ""}
    p["upload_id" if upload_id else "url"] = upload_id or (url or "")
    return urlencode(p)

from uuid import uuid4
from collections import OrderedDict
import threading

_UPLOAD_CACHE: "OrderedDict[str, Reader]" = OrderedDict()
_UPLOAD_MAX = 32
_UPLOAD_LOCK = threading.Lock()

def _cache_upload(reader: Reader) -> str:
    token = uuid4().hex
    with _UPLOAD_LOCK:
        _UPLOAD_CACHE[token] = reader
        _UPLOAD_CACHE.move_to_end(token)
        while len(_UPLOAD_CACHE) > _UPLOAD_MAX:
            _UPLOAD_CACHE.popitem(last=False)
    return token

def _get_upload(token: str):
    with _UPLOAD_LOCK:
        r = _UPLOAD_CACHE.get(token)
        if r is not None:
            _UPLOAD_CACHE.move_to_end(token)
        return r
    
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

@lru_cache(maxsize=32)
def _load_url(url: str, read_as: str, imported, closure, warnings):
    reader = Reader()
    reader.load_instances(url, read_as, imported=imported, closure=closure, warnings=warnings)
    return reader

def _resolve_reader(read_as: str, url, upload_id, imported, closure, warnings):
    if upload_id:
        reader = _get_upload(upload_id)
        if reader is None:
            raise ArtefactValidationError("Upload expired, please re-upload",
                                          context={"upload_id": upload_id})
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
    temp_file_path = None
    
    try:
        logger.info(f"=== FILE UPLOAD START ===")
        logger.info(f"Filename: {file.filename}")
        logger.info(f"Format: {read_as.value}")

        # SECURITY CHECKS: validate before writing to disk
        _check_format_enabled(read_as)
        security.check_extension(file.filename)
        content = await security.read_upload_capped(file)   # chunked read + size cap (anti-DoS)
        security.check_is_text(content)                     # binary rejection
        security.check_safe_xml(content.decode("utf-8-sig"))  # XXE / billion laughs

        # Write temp file (valid input only)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".rdf") as tmp:
            tmp.write(content)
            temp_file_path = tmp.name

        # Initialise Reader and calls the Loader -> Reader -> Viewer and populates it
        reader = Reader()
        reader.load_instances(temp_file_path, read_as.value, imported=imported, closure=closure, warnings=warnings)

        # Cache the parsed Reader so resource navigation / export work without the file
        token = _cache_upload(reader)

        logger.info(f"=== UPLOAD SUCCESS ===")
        return _render_view(request, reader, resource=resource, lang=lang,
                            source_url=None, upload_id=token, read_as=read_as.value)
    finally:
        # Security: Flushes the temp file once its is loaded
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)

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