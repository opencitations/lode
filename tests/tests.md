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
```

# modules.py

Reads URIs from `ontologies.json` and runs two tests on each ontology: **Loader** (checks that the ontology can be loaded) and **Modules** (verifies that `imported` and `closure` variants actually pull in triples when `owl:imports` are declared and reachable).

Outcomes (per variant – `imported` / `closure`):
- if declared imports == 0 → Pass (no_imports)
- if declared imports > 0, all unreachable → Fail (all_imports_unreachable)
- if declared imports > 0, some reachable, but added == 0 → Fail (imports_reachable_but_not_added)
- if declared imports > 0, added > 0 → Pass (ok)
- if load error on any variant → Fail (load_error)

## Usage
```bash
python modules.py [--input ontologies.json] [--read-as owl] [--out modules_report.json] [--indent 2]
```