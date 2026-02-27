# punning.py

Reads URIs from `ontologies.json` and runs two tests on each ontology: **Loader** (checks that the ontology can be loaded) and **Punning** (verifies consistency across RDF graph, Reader (cache), and viewer).

Outcomes:
- if N punning instances in RDF = Reader (cache) = Viewer --> Pass
- if N punning instances in RDF < Reader (cache) = Viewer --> Pass, Warn with manual check
- if N punning instances in RDF != Reader (cache) OR Reader (cache) != Viewer OR RDF != Viewer --> Fail
- if N punning instances in RDF > Reader (cache) = Viewer --> Fail

## Usage

```bash
python punning.py [--read-as owl] [--out punning_report.json] [--indent 2]
