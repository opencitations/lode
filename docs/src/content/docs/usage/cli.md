---
title: CLI Reference
description: LODE command line interface
---

## Commands

### `lode serve`

Start the web server.

```bash
lode serve [--port PORT]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--port` | `8000` | Port to listen on |

### `lode build`

Generate a self-contained static documentation site.

```bash
lode build (--url URL | --file FILE) --read-as FORMAT [OPTIONS]
```

| Option | Required | Description |
|--------|----------|-------------|
| `--url` | one of | Public http(s) URL of the artefact |
| `--file` | one of | Local file path |
| `--read-as` | yes | Artefact type: `owl`, `rdf`, `skos` |
| `--out` | no | Output directory (default `./lode_output`) |
| `--lang` | no | Language tag for labels (default `en`) |
| `--imported` | no | Load `owl:imports` at depth 1 |
| `--closure` | no | Load the full `owl:imports` closure |

## Examples

```bash
# from a URL
lode build --url http://purl.org/spar/fabio --read-as owl --out ./fabio

# from a local file
lode build --file ontology.ttl --read-as owl --out ./docs

# with Italian labels and imports
lode build --url http://purl.org/spar/fabio --read-as owl --lang it --imported --out ./fabio
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LODE_SPOOL_DIR` | `$TMPDIR/lode-spool` | Cache for fetched URLs and uploads |
| `LODE_BUILD_DIR` | `$TMPDIR/lode-builds` | Workspace for ZIP build jobs |
| `LODE_DEBUG` | `false` | Show full tracebacks in error pages |
