---
title: API Endpoints
description: LODE REST API reference
---

Interactive docs available at `/docs` (Swagger) and `/redoc` (ReDoc) when the server is running.

## GET /

Web input form.

## GET /health

Liveness probe. Returns `{"status": "ok"}`. Used by Docker and Kubernetes health checks.

## GET /extract

Render an artefact as HTML or RDF.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `read_as` | enum | yes | `owl` \| `rdf` \| `skos` |
| `url` | string | one of | Public http(s) URL |
| `upload_id` | string | one of | Token from a previous upload |
| `resource` | string | no | IRI of a single resource |
| `lang` | string | no | Language tag, e.g. `en` |
| `imported` | bool | no | Load `owl:imports` depth 1 |
| `closure` | bool | no | Load full `owl:imports` closure |
| `format` | string | no | Force serialization: `ttl`, `rdf`, `jsonld`, `nt` |
| `warnings` | bool | no | Include reader warnings |
| `cache` | bool | no | Use URL cache (default `true`) |

Returns HTML by default. Returns RDF when `format` is set or the `Accept` header requests a serialization MIME type.

## POST /extract

Same as `GET /extract` but accepts a file upload (`multipart/form-data`).

## GET /build

Generate a static documentation site as a ZIP archive. Same parameters as `GET /extract` minus `resource` and `format`.

## POST /build

Same as `GET /build` but accepts a file upload.
