# lode/api.py
from fastapi import FastAPI, File, UploadFile, Form, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from enum import Enum
from typing import Optional
import tempfile
import os
import traceback
import logging

# Configura logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Internal modules
from lode.reader import Reader

app = FastAPI(title="LODE 2.0 API", version="1.0.0")
templates = Jinja2Templates(directory="lode/templates")
app.mount("/static", StaticFiles(directory="lode/static"), name="static")

class ReadAsFormat(str, Enum):
    owl = "owl"
    rdf = "rdf"
    skos = "skos"

_ACCEPT_TO_SERIALIZATION: dict[str, tuple[str, str, str]] = {
    "text/turtle":            ("turtle", "text/turtle",         "ttl"),
    "application/rdf+xml":    ("xml",    "application/rdf+xml", "rdf"),
    "text/n3":                ("n3",     "text/n3",             "n3"),
}

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
    try:
        logger.info(f"=== REQUEST START ===")
        logger.info(f"URL: {url}")
        logger.info(f"Format: {read_as.value}")
        logger.info(f"Resource: {resource}")

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
    except Exception as e:
        logger.error(f"=== ERROR ===")
        logger.error(f"Type: {type(e).__name__}")
        logger.error(f"Message: {str(e)}")
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        logger.error(f"=============")

        return templates.TemplateResponse("viewer.html", {
            "request": request,
            "source_url": None,
            "error": f"{type(e).__name__}: {str(e)}\n\nFull traceback:\n{traceback.format_exc()}"
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
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".rdf") as tmp:
            content = await file.read()
            tmp.write(content)
            temp_file_path = tmp.name
        
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
    except Exception as e:
        logger.error(f"=== ERROR ===")
        logger.error(f"Type: {type(e).__name__}")
        logger.error(f"Message: {str(e)}")
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        logger.error(f"=============")
        
        return templates.TemplateResponse("viewer.html", {
            "request": request,
            "error": f"{type(e).__name__}: {str(e)}\n\nFull traceback:\n{traceback.format_exc()}"
        })
    finally:
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