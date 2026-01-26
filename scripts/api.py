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
from reader.reader import Reader

app = FastAPI(title="LODE 2.0 API", version="1.0.0")
templates = Jinja2Templates(directory="templates")


class ReadAsFormat(str, Enum):
    owl = "owl"
    rdf = "rdf"
    skos = "skos"

@app.post("/api/extract")
async def extract_resource(
    read_as: ReadAsFormat = Form(..., description="Format to interpret the RDF graph"),
    resource: Optional[str] = Form(None, description="URI of the resource to extract (optional, if not provided extracts all)"),
    semantic_artefact_url: Optional[str] = Form(None, description="URI or URL of the semantic artefact"),
    semantic_artefact_file: Optional[UploadFile] = File(None, description="RDF file to upload")
):
    """
    Extract a single resource or all resources from a semantic artefact.
    
    **Parameters:**
    - **read_as** (mandatory): Format interpretation (owl, rdf-rdfs, skos)
    - **resource** (optional): URI of the resource to extract. If not provided, extracts all resources
    - **semantic_artefact**: Either semantic_artefact_url OR semantic_artefact_file (mandatory)
    
    **Example extracting single resource using URL:**
```
    curl -X POST "http://localhost:8000/api/extract" \
         -F "read_as=owl" \
         -F "resource=http://example.org/MyClass" \
         -F "semantic_artefact_url=http://example.org/ontology.owl"
```
    
    **Example extracting all resources using file:**
```
    curl -X POST "http://localhost:8000/api/extract" \
         -F "read_as=owl" \
         -F "semantic_artefact_file=@ontology.owl"
```
    """
    
    # Validazione: almeno uno dei due semantic_artefact
    if not semantic_artefact_url and not semantic_artefact_file:
        raise HTTPException(
            status_code=400,
            detail="Either 'semantic_artefact_url' or 'semantic_artefact_file' must be provided"
        )
    
    if semantic_artefact_url and semantic_artefact_file:
        raise HTTPException(
            status_code=400,
            detail="Provide only ONE of 'semantic_artefact_url' or 'semantic_artefact_file'"
        )
    
    # Validazione URI se resource è fornito
    if resource and not resource.startswith(('http://', 'https://', 'urn:')):
        raise HTTPException(
            status_code=400,
            detail=f"'resource' must be a valid URI (starts with http://, https://, or urn:)"
        )
    
    temp_file_path = None
    
    try:
        # Gestione semantic_artefact
        if semantic_artefact_file:
            # Salva file temporaneo
            with tempfile.NamedTemporaryFile(delete=False, suffix=".rdf") as tmp:
                content = await semantic_artefact_file.read()
                tmp.write(content)
                temp_file_path = tmp.name
            
            graph_source = temp_file_path
        else:
            # Usa URL direttamente
            if not semantic_artefact_url.startswith(('http://', 'https://', 'file://')):
                raise HTTPException(
                    status_code=400,
                    detail="'semantic_artefact_url' must be a valid URI/URL"
                )
            graph_source = semantic_artefact_url
        
        # Carica grafo
        reader = Reader()
        reader.load_instances(graph_source, read_as.value)
        
        # Se resource non è fornito, estrai tutto
        if not resource:
            # get_instances() restituisce un dict: {class_name: [instance1, instance2, ...]}
            grouped_instances = reader.get_instances()
            
            all_instances = []
            for class_name, instances_list in grouped_instances.items():
                for instance in instances_list:
                    all_instances.append(reader.to_dict(instance))
            
            result = {
                "semantic_artefact": graph_source if semantic_artefact_url else "uploaded_file",
                "read_as": read_as.value,
                "total_resources": len(all_instances),
                "instances_by_type": {
                    class_name: len(instances) 
                    for class_name, instances in grouped_instances.items()
                },
                "instances": all_instances
            }
            return JSONResponse(content=result)
        
        # Altrimenti estrai risorsa specifica
        instance = reader.get_instance(resource)
        
        if instance is None:
            raise HTTPException(
                status_code=404,
                detail=f"Resource '{resource}' not found in the semantic artefact"
            )
        
        # Se instance è un set, prendi tutte le istanze
        if isinstance(instance, set):
            result = {
                "resource_uri": resource,
                "instances": [reader.to_dict(inst) for inst in instance]
            }
        else:
            result = {
                "resource_uri": resource,
                "instance": reader.to_dict(instance)
            }
        
        return JSONResponse(content=result)
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing semantic artefact: {str(e)}"
        )
    
    finally:
        # Cleanup
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)

@app.get("/api/extract")
async def extract_resource_get(
    read_as: ReadAsFormat,
    semantic_artefact_url: str,
    resource: Optional[str] = None
):
    """Versione GET - solo per URL, no file upload"""
    
    # Validazione URI se resource è fornito
    if resource and not resource.startswith(('http://', 'https://', 'urn:')):
        raise HTTPException(
            status_code=400,
            detail=f"'resource' must be a valid URI"
        )
    
    if not semantic_artefact_url.startswith(('http://', 'https://', 'file://')):
        raise HTTPException(
            status_code=400,
            detail="'semantic_artefact_url' must be a valid URI/URL"
        )
    
    try:
        reader = Reader()
        reader.load_instances(semantic_artefact_url, read_as.value)
        
        # Se resource non è fornito, estrai tutto
        if not resource:
            grouped_instances = reader.get_instances()
            
            all_instances = []
            for class_name, instances_list in grouped_instances.items():
                for instance in instances_list:
                    all_instances.append(reader.to_dict(instance))
            
            result = {
                "semantic_artefact": semantic_artefact_url,
                "read_as": read_as.value,
                "total_resources": len(all_instances),
                "instances_by_type": {
                    class_name: len(instances) 
                    for class_name, instances in grouped_instances.items()
                },
                "instances": all_instances
            }
            return JSONResponse(content=result)
        
        # Altrimenti estrai risorsa specifica
        instance = reader.get_instance(resource)
        
        if instance is None:
            raise HTTPException(
                status_code=404,
                detail=f"Resource '{resource}' not found"
            )
        
        if isinstance(instance, set):
            result = {
                "resource_uri": resource,
                "instances": [reader.to_dict(inst) for inst in instance]
            }
        else:
            result = {
                "resource_uri": resource,
                "instance": reader.to_dict(instance)
            }
        
        return JSONResponse(content=result)
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error: {str(e)}"
        )

@app.get("/api/info")
async def root():
    return {
        "message": "LODE 2.0 API",
        "version": "1.0.0",
        "endpoints": {
            "extract": "/api/extract [GET, POST]"
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