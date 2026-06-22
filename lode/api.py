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
from urllib.parse import urlparse

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
    url: str,
    resource: Optional[str] = None,
    lang: Optional[str] = None,
    imported: Optional[bool] = None,
    closure: Optional[bool] = None, 
    warnings: bool = False
):
        _check_format_enabled(read_as)

        parsed_url = urlparse(url)
        if parsed_url.scheme not in ("http", "https") or not parsed_url.netloc:
            raise ArtefactValidationError(
                "Invalid URL: only absolute HTTP/HTTPS URLs are allowed",
                context={"url": url}
            )

        reader = Reader()
        reader.load_instances(url, read_as.value, imported=imported, closure=closure, warnings=warnings)

        accept = request.headers.get("accept", "text/html")
        if accept in _ACCEPT_TO_SERIALIZATION:
            rdflib_fmt, mime_type, ext = _ACCEPT_TO_SERIALIZATION[accept]
            serialized = reader._graph.serialize(format=rdflib_fmt)
            filename = url.rstrip("/").split("/")[-1] or "graph"
            return Response(
                content=serialized,
                media_type=mime_type,
                headers={"Content-Disposition": f'attachment; filename="{filename}.{ext}"'}
            )

        viewer = reader.get_viewer()
        data = viewer.get_view_data(resource_uri=resource, language=lang)
        data['warnings'] = reader.get_warnings()

        logger.info(f"=== REQUEST SUCCESS ===")
        return templates.TemplateResponse("viewer.html", {
            "request": request,
            "source_url": url,
            **data
        })

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
        viewer = reader.get_viewer()
        data = viewer.get_view_data(resource_uri=resource, language=lang) 
        data['warnings'] = reader.get_warnings() 
        
        logger.info(f"=== UPLOAD SUCCESS ===")
        return templates.TemplateResponse("viewer.html", {
            "request": request,
            "source_url": None,
            **data
        })
    
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