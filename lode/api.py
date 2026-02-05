# lode/api.py
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse
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

@app.get("/api/view", response_class=HTMLResponse)
async def view_semantic_artefact_get(
    request: Request,
    read_as: ReadAsFormat,
    semantic_artefact_url: str,
    resource: Optional[str] = None,
    language: Optional[str] = None
):
    """Visualizza semantic artefact da URL."""
    try:
        logger.info(f"=== REQUEST START ===")
        logger.info(f"URL: {semantic_artefact_url}")
        logger.info(f"Format: {read_as.value}")
        logger.info(f"Resource: {resource}")
        
        reader = Reader()
        reader.load_instances(semantic_artefact_url, read_as.value)
        
        viewer = reader.get_viewer()
        data = viewer.get_view_data(resource_uri=resource, language=language) 
        
        logger.info(f"=== REQUEST SUCCESS ===")
        return templates.TemplateResponse("viewer.html", {
            "request": request,
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

@app.post("/api/view", response_class=HTMLResponse)
async def view_semantic_artefact_post(
    request: Request,
    read_as: ReadAsFormat = Form(...),
    semantic_artefact_file: UploadFile = File(...),
    resource: Optional[str] = Form(None),
    language: Optional[str] = Form(None)  
):
    """Visualizza semantic artefact da file."""
    temp_file_path = None
    
    try:
        logger.info(f"=== FILE UPLOAD START ===")
        logger.info(f"Filename: {semantic_artefact_file.filename}")
        logger.info(f"Format: {read_as.value}")
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".rdf") as tmp:
            content = await semantic_artefact_file.read()
            tmp.write(content)
            temp_file_path = tmp.name
        
        reader = Reader()
        reader.load_instances(temp_file_path, read_as.value)
        
        viewer = reader.get_viewer()
        data = viewer.get_view_data(resource_uri=resource, language=language) 
        
        logger.info(f"=== UPLOAD SUCCESS ===")
        return templates.TemplateResponse("viewer.html", {
            "request": request,
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

@app.get("/api/info")
async def root():
    return {
        "message": "LODE 2.0 API",
        "version": "1.0.0",
        "endpoints": {
            "extract": "/api/extract [GET, POST] - Extract resources as JSON",
            "view": "/api/view [GET] - View resources as HTML"
        }
    }

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