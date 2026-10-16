# Getting started

## Requirements

- Python 3.10 or later
- pip

## Installation

```bash
pip install oc-lode

# with the web service (`lode serve`)
pip install "oc-lode[server]"
```

### Which install do I need?

The base install is enough for the CLI and for using LODE as a library: `lode build`
and the `lode.reader` / `lode.viewer` modules. It installs `rdflib`, `jinja2`,
`requests`, `minify-html` and `pyyaml`.

The web service and the REST API (`lode serve`, `lode.api`) need the `[server]` extra,
which adds `fastapi`, `uvicorn`, `gunicorn` and `python-multipart`.

| You want to... | Install |
|----------------|---------|
| Build static docs with `lode build` | `pip install oc-lode` |
| Run `lode serve` or import `lode.api` | `pip install "oc-lode[server]"` |

!!! warning
    Without the extra, `lode serve` exits with
    `Server dependencies missing: pip install oc-lode[server]`, and
    `import lode.api` fails with `ModuleNotFoundError: No module named 'fastapi'`.

## First run

Start the web server (requires the `[server]` extra):

```bash
lode serve --port 8000
```

Open `http://localhost:8000` in your browser, paste an ontology URL and click **Extract**.

Or generate a static site from a local file:

```bash
lode build --file my_ontology.ttl --read-as owl --out ./site
```

## Development install

```bash
git clone https://github.com/opencitations/lode.git
cd lode
uv sync --all-extras --dev
uv run python main.py
```
