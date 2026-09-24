---
title: Web Form
description: How to use the LODE web interface
---

Start the server and open `http://localhost:8000`.

## Input

| Field | Description |
|-------|-------------|
| **URL** | Public http(s) URL of the artefact |
| **File** | Upload a local `.ttl`, `.rdf`, `.owl`, `.n3`, `.jsonld` file |
| **Format** | Artefact type (`owl` is currently available) |
| **Language** | Preferred language for labels (e.g. `en`, `it`) |
| **Load imports** | Also fetch `owl:imports` at depth 1 |
| **Load closure** | Fetch the full `owl:imports` closure |

## Output

LODE renders the ontology as a browsable HTML page with:

- a table of contents grouped by entity type
- definitions, labels and annotations for each entity
- embedded links between related entities
- export buttons for RDF serializations (Turtle, JSON-LD, RDF/XML, N-Triples)

## API docs

Interactive API documentation is available at:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
