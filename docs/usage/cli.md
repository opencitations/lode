# CLI reference

## Commands

### `lode serve`

Start the web server (requires the `[server]` extra).

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
| `--read-as` | yes | Artefact type: `owl`, `rdf`, `skos` - Currently only `owl` is available |
| `--out` | no | Output directory (default `./lode_output`) |
| `--lang` | no | Language tag for labels (default `en`) |
| `--artefact-name` | no | File name (without extension) of the root page and its serializations (if omitted, falls back to `index`, so the site starts at `index.html`). Only letters, digits, `.`, `_` and `-` are allowed |
| `--imported` | no | Load `owl:imports` at depth 1 |
| `--closure` | no | Load the full `owl:imports` closure |
| `--partial-import` | no | Load only the imported entities that are actually used |
## Examples

```bash
# from a URL
lode build --url http://purl.org/spar/fabio --read-as owl --out ./fabio

# from a local file
lode build --file ontology.ttl --read-as owl --out ./site

# with Italian labels and imports
lode build --url http://purl.org/spar/fabio --read-as owl --lang it --imported --out ./fabio

# rename the root page: writes fabio.html, fabio.ttl, fabio.rdf, ...
lode build --url http://purl.org/spar/fabio --read-as owl --artefact-name fabio --out ./site
```

The artefact name applies only to the root files. Resource pages keep the name
derived from their IRI, and their "Back to full documentation" button points to
`<artefact-name>.html`.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LODE_SPOOL_DIR` | `$TMPDIR/lode-spool` | Cache for fetched URLs and uploads |
| `LODE_BUILD_DIR` | `$TMPDIR/lode-builds` | Workspace for ZIP build jobs |
| `LODE_LOG_LEVEL` | `WARNING` | Log verbosity (`DEBUG`, `INFO`, `WARNING`, ...) |
| `LODE_DEBUG` | `false` | Show full tracebacks in error pages |
