# api.py

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from enum import Enum
from typing import Optional
import tempfile
import os

# Internal modules
from reader.reader import Reader

app = FastAPI(title="LODE 2.0 API", version="1.0.0")
templates = Jinja2Templates(directory="scripts/templates")
app.mount("/static", StaticFiles(directory="scripts/static"), name="static")

class ReadAsFormat(str, Enum):
    owl = "owl"
    rdf = "rdf"
    skos = "skos"

@app.get("/api/view", response_class=HTMLResponse)
async def view_semantic_artefact_get(
    request: Request,
    read_as: ReadAsFormat,
    semantic_artefact_url: str,
    resource: Optional[str] = None  # AGGIUNGI QUESTO
):
    """Visualizza semantic artefact da URL."""
    try:
        reader = Reader()
        reader.load_instances(semantic_artefact_url, read_as.value)
        
        viewer = reader.get_viewer()
        data = viewer.get_view_data(resource_uri=resource) 
        
        return templates.TemplateResponse("viewer.html", {
            "request": request,
            **data
        })
    except Exception as e:
        return templates.TemplateResponse("viewer.html", {
            "request": request,
            "error": str(e)
        })

@app.post("/api/view", response_class=HTMLResponse)
async def view_semantic_artefact_post(
    request: Request,
    read_as: ReadAsFormat = Form(...),
    semantic_artefact_file: UploadFile = File(...),
    resource: Optional[str] = Form(None)  
):
    """Visualizza semantic artefact da file."""
    temp_file_path = None
    
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".rdf") as tmp:
            content = await semantic_artefact_file.read()
            tmp.write(content)
            temp_file_path = tmp.name
        
        reader = Reader()
        reader.load_instances(temp_file_path, read_as.value)
        
        viewer = reader.get_viewer()
        data = viewer.get_view_data(resource_uri=resource) 
        
        return templates.TemplateResponse("viewer.html", {
            "request": request,
            **data
        })
    except Exception as e:
        return templates.TemplateResponse("viewer.html", {
            "request": request,
            "error": str(e)
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


# Nuova route per l'interfaccia web
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