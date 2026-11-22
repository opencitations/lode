# LODE 2.0

:::{warning} Beta version
LODE 2 is under development and in beta: anything described in this documentation may change.
:::

Live OWL Documentation Environment — extract and document semantic artefacts as browsable, interlinked HTML. Maintained by [OpenCitations](https://opencitations.net).

[Get started](getting_started.md) · [View on GitHub](https://github.com/opencitations/lode)

## Features

- Extracts and documents OWL classes, properties, individuals, restrictions and more
- Renders browsable HTML with embedded navigation links
- Serves a dynamic web interface and REST API
- Generates self-contained static sites from the CLI
- Content negotiation: returns RDF serializations on request
- Docker-ready with configurable storage via environment variables

## Quick start

```bash
pip install "oc-lode[server]"
lode serve --port 8000
```

Open `http://localhost:8000` to use the web form, or `http://localhost:8000/docs` for the interactive API.
