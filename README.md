# Lode

[![Run tests](https://github.com/opencitations/lode/actions/workflows/tests.yml/badge.svg)](https://github.com/opencitations/lode/actions/workflows/tests.yml)
[![Coverage](https://opencitations.github.io/lode/coverage/coverage-badge.svg)](https://opencitations.github.io/lode/coverage/)
[![License: ISC](https://img.shields.io/badge/License-ISC-blue.svg)](https://opensource.org/licenses/ISC)

LODE 2.0 is an open source service that automatically extracts entities from semantic artefacts (OWL, RDF/RDFS, SKOS) and renders them, together with their textual definitions, as a human-readable HTML page designed for browsing and navigation through embedded links. This new reengineered version of LODE is maintained by OpenCitations. 

**Try it online:** a hosted instance of the web service is available at https://lode.opencitations.net/, with no installation needed.


## Installation

```bash
pip install oc-lode

# with the web service (`lode serve`)
pip install "oc-lode[server]"
```

 ## Usage

```bash
# Build static documentation from an ontology URL or a local file
lode build --url <url> --read-as <owl|rdf|skos> [--out ./docs] [--lang en] [--artefact-name index] [--imported] [--closure]
lode build --file <path> --read-as <owl|rdf|skos> [--out ./docs]

# Run the web service locally (requires the [server] extra)
lode serve --port 8000
```

## Documentation

Full documentation is available at: https://opencitations.github.io/lode/

## Prerequisites

This project uses [UV](https://docs.astral.sh/uv/) for dependency management.

### Setup

```bash
# Clone the repository
git clone https://github.com/opencitations/lode.git

# Enter the repo
cd lode

# Install dependencies
uv sync --all-extras --dev

# run locally
uv run python main.py

# open at 
localhost:8000
```

## Docker

### Build

```bash
docker build -t lode .
```

### Run

```bash
docker run -p 8080:8080 lode
```

### Run from Docker Hub

```bash
docker run -p 8080:8080 opencitations/lode:latest
```

Replace `latest` with the desired version tag.

The app will be available at `localhost:8080`.

## Running tests

```bash
uv run pytest tests/
```

## How to cite

If you use LODE, please cite both the paper and the software:

Pasqual, V., Nazari, A., Peroni, S. (2026). Supporting the understanding of ontologies for scientific knowledge graphs with the new version of LODE. In *Proceedings of the 6th International Workshop on Scientific Knowledge: Representation, Discovery, and Assessment (Sci-K 2026), co-located with the 25th International Semantic Web Conference (ISWC) 2026, Bari, Italy*, CEUR Workshop Proceedings, Vol. 4291, pp. 12–26. https://ceur-ws.org/Vol-4291/paper1.pdf

```bibtex
@inproceedings{pasqual2026lode,
  author    = {Pasqual, Valentina and Nazari, Ahmadreza and Peroni, Silvio},
  title     = {Supporting the Understanding of Ontologies for Scientific Knowledge Graphs with the New Version of LODE},
  booktitle = {Proceedings of the 6th International Workshop on Scientific Knowledge: Representation, Discovery, and Assessment (Sci-K 2026), co-located with the 25th International Semantic Web Conference (ISWC) 2026, Bari, Italy},
  series    = {CEUR Workshop Proceedings},
  volume    = {4291},
  pages     = {12--26},
  publisher = {CEUR-WS.org},
  issn      = {1613-0073},
  year      = {2026},
  url       = {https://ceur-ws.org/Vol-4291/paper1.pdf}
}
```

To cite the software (all versions), use this BibTeX entry:

```bibtex
@software{lode,
  author    = {Pasqual, Valentina and Peroni, Silvio and Nazari, Ahmadreza},
  title     = {LODE - Live OWL Documentation Environment},
  year      = {2026},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.21805185},
  url       = {https://github.com/opencitations/lode}
}
```

<!-- ### Building documentation locally

```bash
cd docs
npm install
npm run dev
``` -->

## License

This project is licensed under the ISC License - see the [LICENSE.md](https://github.com/opencitations/lode/blob/main/LICENSE.md) file for details.
