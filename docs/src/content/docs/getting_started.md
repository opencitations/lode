---
title: Getting Started
description: Install and run LODE 2.0
---

## Requirements

- Python 3.10 or later
- pip

## Installation

```bash
pip install lode2
```

## First run

Start the web server:

```bash
lode serve --port 8000
```

Open `http://localhost:8000` in your browser, paste an ontology URL and click **Extract**.

Or generate a static site from a local file:

```bash
lode build --file my_ontology.ttl --read-as owl --out ./docs
```

## Development install

```bash
git clone https://github.com/opencitations/lode.git
cd lode
uv sync --all-extras --dev
uvicorn lode.api:app --reload --port 8000
```