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
