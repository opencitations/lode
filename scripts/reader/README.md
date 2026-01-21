# Reader - Generic RDF Orchestrator

## Table of Contents
- [Overview](#overview)
- [Installation](#installation)
- [Usage](#usage)
  - [Quick Start](#quick-start)
  - [Retrieve Single Instance](#retrieve-single-instance)
  - [Retrieve All Instances](#retrieve-all-instances)
  - [Access Original RDF Triples](#access-original-rdf-triples)
  - [Get Complete Triples Map](#get-complete-triples-map)
  - [Cleanup](#cleanup)
- [Typical Viewer Pattern](#typical-viewer-pattern)
- [Testing](#testing)
  - [Run Tests](#run-tests)
- [API Reference](#api-reference)

## Overview

`Reader` is a generic RDF orchestrator that parses RDF graphs and populates Python model instances based on configurable strategies (OWL, SKOS, RDF, RDFS).

**Key Features:**
- Strategy-based RDF parsing (OWL, SKOS, RDF, RDFS)
- Automatic Python model population from RDF triples
- Instance caching and retrieval
- Provenance tracking (instance → RDF triples mapping)
- Extensible configuration system

## Installation
```bash
pip install rdflib
```

**Dependencies:**
- `rdflib`
- `loader.py` (RDF graph loader)
- `config_manager.py` (strategy configuration)
- `models.py` (Python data models)

## Usage

### Quick Start
```python
from reader import Reader

# Initialize reader
reader = Reader()

# Load and process RDF graph
reader.load_instances(
    graph_path="path/to/ontology.owl",  # Path to RDF file
    read_as="owl"                        # Strategy: "owl", "skos", "rdf"
)
```

### Retrieve Single Instance
```python
# Get all instances for a URI
instances = reader.get_instance("http://example.org/resource1")

# Get specific type instance for a URI
from models import Class

class_instance = reader.get_instance(
    uri="http://example.org/MyClass",
    instance_type=Concept  # Filter by Python model type
)
```

**Returns:**
- `None` if URI not found
- Single instance if `instance_type` specified
- Set of instances if no type filter

### Retrieve All Instances
```python
# Returns dict: {"ClassName": [instance1, instance2, ...]}
grouped = reader.get_instances()

# Example: iterate by type
for class_name, instances in grouped.items():
    print(f"{class_name}: {len(instances)} instances")
    for instance in instances:
        print(f"  - {instance}")
```

**Returns:** `dict[str, list]` - Dictionary mapping class names to instance lists

### Access Original RDF Triples
```python
# Get RDF triples that generated a specific instance
triples = reader.get_triples_for_instance(my_instance)

# Returns: set of tuples (subject, predicate, object)
for s, p, o in triples:
    print(f"{s} {p} {o}")
```

### Get Complete Triples Map
```python
# Get complete mapping: instance → set of triples
triples_map = reader.get_all_triples_map()

# Returns: dict[instance, set[tuple]]
for instance, triples in triples_map.items():
    print(f"Instance: {instance}")
    for s, p, o in triples:
        print(f"  Triple: {s} {p} {o}")
```

### Cleanup
```python
# Clear internal cache and logic state
reader.clear_cache()
```

## Typical Viewer Pattern
```python
from reader import Reader

# Initialize and load
reader = Reader()
reader.load_instances("ontology.owl", "owl")

# Get organized instances
instances_by_type = reader.get_instances()

# Get provenance data
triples_map = reader.get_all_triples_map()

# Render viewer with structural and provenance data
for cls_name, instances in instances_by_type.items():
    print(f"\n=== {cls_name} ===")
    
    for instance in instances:
        # Display instance
        print(f"\nInstance: {instance}")
        
        # Show original RDF triples
        source_triples = triples_map.get(instance, set())
        if source_triples:
            print("Source triples:")
            for s, p, o in source_triples:
                print(f"  {s} {p} {o}")
```

## Testing

### Run Tests

The test suite is located in `test/html_generator_v2/`.
```bash

python run test/html_generator_v2.py

```

**Test Structure:**
```
test/
└── html_generator_v2/
    ├── test_reader.py          # Reader tests
    ├── test_logic.py           # Logic strategy tests
    ├── test_config.py          # Configuration tests
    └── fixtures/               # Test RDF files
```

## API Reference

### `Reader` Class

#### `__init__()`
Initialize Reader instance.

#### `load_instances(graph_path: str, read_as: str)`
Load and process RDF graph.

**Parameters:**
- `graph_path` (str): Path to RDF file
- `read_as` (str): Strategy name ("owl", "skos", "rdf", "rdfs")

#### `get_instance(uri: str, instance_type=None)`
Retrieve instance(s) by URI.

**Parameters:**
- `uri` (str): Resource URI
- `instance_type` (type, optional): Filter by Python class

**Returns:** Instance, set of instances, or None

#### `get_instances() -> dict`
Get all instances grouped by type.

**Returns:** `dict[str, list]` - Class name → instances list

#### `get_triples_for_instance(instance) -> set`
Get RDF triples for specific instance.

**Parameters:**
- `instance`: Python instance object

**Returns:** `set[tuple]` - Set of (s, p, o) triples

#### `get_all_triples_map() -> dict`
Get complete instance → triples mapping.

**Returns:** `dict[instance, set[tuple]]` - Full provenance map

#### `clear_cache()`
Clear internal caches and reset state.

---

## Architecture

The Reader implements a 6-phase extraction process:

1. **Phase 1:** Classify from predicates
2. **Phase 2:** Create from types
3. **Phase 3:** Populate properties
4. **Phase 4:** Process group axioms
5. **Phase 5:** Fallback for uncategorized resources
6. **Phase 6:** Create statements (RDF only)

Processing is delegated to strategy-specific Logic classes configured via `config_manager`.