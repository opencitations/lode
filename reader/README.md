# RDF-to-Python Object Mapper

Sistema di mappatura automatica da grafi RDF/OWL a oggetti Python, con supporto per multiple semantiche (OWL, RDFS, SKOS).

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Components](#components)
- [Usage Examples](#usage-examples)
- [UML Diagrams](#uml-diagrams)

---

## 🎯 Overview

Questo sistema permette di:
- ✅ **Caricare** ontologie RDF da file locali o URL
- ✅ **Mappare** automaticamente tipi RDF → classi Python
- ✅ **Navigare** relazioni semantiche come oggetti Python
- ✅ **Supportare** multiple interpretazioni (OWL, RDFS, SKOS)

### Esempio di utilizzo
```python

# Navigazione OOP
cites = reader.get_instance("http://purl.org/spar/cito/cites")
domains = cites.get_has_domain()  # List[Concept]
ranges = cites.get_has_range()    # List[Concept]
```

---

## 🏗️ Architecture

Il sistema usa 3 pattern architetturali:

### 1. **Strategy Pattern** (semantiche multiple)
Ogni strategia definisce come interpretare il grafo RDF.

```
User Request → Loader → Strategy (OWL/RDFS/SKOS) → Factory → Python Objects
```

### 2. **Abstract Factory Pattern** (creazione istanze)
Ogni factory implementa la semantica specifica.

```
OwlFactory   → crea Relation, Attribute, Annotation, Concept, ...
RdfsFactory  → crea Property, Concept
SkosFactory  → crea Concept (con skos:broader, skos:narrower)
```

### 3. **Two-Phase Extraction** (dipendenze circolari)

**FASE 1**: Crea tutte le istanze **vuote**
```python
# Esempio: cito:cites e cito:CitationAct esistono ma non sono ancora collegati
cites = Relation(uri="http://purl.org/spar/cito/cites")
citation_act = Concept(uri="http://purl.org/spar/cito/CitationAct")
```

**FASE 2**: Popola con **riferimenti risolti**
```python
# Ora possiamo collegare domain/range perché le istanze esistono
cites.set_has_domain([citation_act])
cites.set_has_range([citation_act])
```

---

## 🚀 Quick Start

### Installazione
```bash
pip install rdflib requests
```

### Esempio Minimo
```python
from orchestrator import Reader

# 1. Inizializza reader
reader = Reader()

# 2. Carica ontologia (interpreta come OWL)
reader.load_instances("http://purl.org/spar/cito/", read_as="OWL")

# 3. Ottieni un'istanza specifica
cites = reader.get_instance("http://purl.org/spar/cito/cites")

# 4. Naviga le proprietà
print(f"URI: {cites.get_uri()}")
print(f"Label: {cites.get_has_label()[0].get_has_value()}")
print(f"Type: {type(cites).__name__}")  # Relation (ObjectProperty)

# 5. Naviga relazioni semantiche
for domain in cites.get_has_domain():
    print(f"Domain: {domain.get_uri()}")

for superprops in cites.get_is_subproperty_of():
    print(f"Subproperty of: {superprops.get_uri()}")
```

---

## 📦 Components

### 1. **Reader** (orchestrator.py)
**Entry point principale**. Coordina tutto il processo.

```python
class Reader:
    def load_instances(graph_path: str, read_as: str)
    def get_instance(uri: str) -> SemanticArtifact
    def get_all_instances() -> dict
    def clear_cache()
```

**Responsabilità**:
- Caricare RDF con `Loader`
- Selezionare `Strategy` appropriata
- Creare `Factory` corretta
- Eseguire estrazione 2-phase
- Gestire cache istanze

---

### 2. **MappingStrategy** (strategy.py)
**Definisce semantica di interpretazione**.

```python
class MappingStrategy(ABC):
    @abstractmethod
    def get_type_mapping() -> dict[URIRef, type]
    
    @abstractmethod
    def create_factory(graph, cache) -> SemanticFactory
```

**Strategie disponibili**:

| Strategy | Mapping | Factory |
|----------|---------|---------|
| `OwlMappingStrategy` | `owl:ObjectProperty → Relation`<br>`owl:DatatypeProperty → Attribute`<br>`owl:AnnotationProperty → Annotation`<br>`owl:Class → Concept` | `OwlFactory` |
| `RdfsMappingStrategy` | `rdfs:Class → Concept`<br>`rdf:Property → Property` | `RdfsFactory` |
| `SkosMappingStrategy` | `skos:Concept → Concept`<br>`skos:ConceptScheme → Model` | `SkosFactory` |

**Esempio**: Come OWL e RDFS interpretano lo stesso grafo

```turtle
# Ontologia
:Person a owl:Class .
:knows a owl:ObjectProperty ;
    rdfs:domain :Person ;
    rdfs:range :Person .
```

```python
# Con OwlMappingStrategy
reader.load_instances("ontology.ttl", read_as="OWL")
knows = reader.get_instance(":knows")
type(knows)  # Relation (perché owl:ObjectProperty)

# Con RdfsMappingStrategy  
reader.load_instances("ontology.ttl", read_as="RDFS")
knows = reader.get_instance(":knows")
type(knows)  # Property (RDFS non distingue ObjectProperty)
```

---

### 3. **SemanticFactory** (factory.py)
**Crea e popola istanze** secondo semantica specifica.

```python
class SemanticFactory(ABC):
    def create_empty_instance(uri, python_class) -> Instance
    def populate_instance(instance, uri)
    
    @abstractmethod
    def _populate_concept(instance, uri)
    @abstractmethod
    def _populate_relation(instance, uri)
    # ... altri metodi populate
```

**Factory specifiche**:

#### OwlFactory
Implementa semantica OWL completa:
- `_populate_relation()`: domain, range, inverse, characteristics (transitive, symmetric, ...)
- `_populate_attribute()`: domain, range (Datatype), functional
- `_populate_concept()`: subClassOf, equivalentClass, disjointWith, unionOf, intersectionOf
- `_populate_restriction()`: onProperty, someValuesFrom, allValuesFrom, cardinality

#### RdfsFactory
Semantica RDFS base:
- `_populate_property()`: domain, range, subPropertyOf
- `_populate_concept()`: subClassOf

#### SkosFactory
Semantica SKOS:
- `_populate_concept()`: broader, narrower, related, inScheme

---

### 4. **Models** (models.py)
**Gerarchia di classi Python** che rappresentano entità semantiche.

```
SemanticArtifact (base)
├── Resource
├── Concept (owl:Class, rdfs:Class)
├── Datatype (rdfs:Datatype)
├── PropertyBase
│   ├── Property (rdf:Property)
│   ├── Relation (owl:ObjectProperty)
│   ├── Attribute (owl:DatatypeProperty)
│   └── Annotation (owl:AnnotationProperty)
├── Restriction (owl:Restriction)
└── Model (owl:Ontology)
```

**Esempio di utilizzo**:

```python
# Concept (Classe OWL)
person = reader.get_instance("http://example.org/Person")
person.get_is_subclass_of()      # List[Concept]
person.get_is_equivalent_to()    # List[Concept]
person.get_is_disjoint_with()    # List[Concept]

# Relation (ObjectProperty)
knows = reader.get_instance("http://example.org/knows")
knows.get_has_domain()           # List[Concept]
knows.get_has_range()            # List[Concept]
knows.get_is_inverse_of()        # List[Relation]
knows.get_is_transitive()        # bool
knows.get_is_symmetric()         # bool

# Attribute (DatatypeProperty)
age = reader.get_instance("http://example.org/age")
age.get_has_domain()             # List[Concept]
age.get_has_range()              # List[Datatype]
age.get_is_functional()          # bool

# Restriction
restriction = reader.get_instance("http://example.org/_:b1")
restriction.get_on_property()           # Property
restriction.get_some_values_from()      # Concept
restriction.get_min_cardinality()       # int
```

---

### 5. **Loader** (loader.py)
**Carica grafi RDF** da file o URL con content negotiation.

```python
class Loader:
    def load(source: str) -> Dict[str, any]
    def get_graph() -> Graph
```

**Features**:
- ✅ Content negotiation automatica per URL
- ✅ Auto-detect formato (Turtle, RDF/XML, JSON-LD, N-Triples, N3)
- ✅ Supporto file locali e URL remoti

**Esempio**:
```python
# Da URL (content negotiation)
loader = Loader("http://purl.org/spar/cito/")

# Da file locale
loader = Loader("/path/to/ontology.owl")

# Formati supportati
loader = Loader("ontology.ttl")    # Turtle
loader = Loader("ontology.rdf")    # RDF/XML
loader = Loader("ontology.jsonld") # JSON-LD
loader = Loader("ontology.nt")     # N-Triples
```

---

## 💡 Usage Examples

### Esempio 1: Esplorare gerarchia di classi

```python
from orchestrator import Reader

reader = Reader()
reader.load_instances("http://purl.org/spar/cito/", read_as="OWL")

# Ottieni una classe
citation_act = reader.get_instance("http://purl.org/spar/cito/CitationAct")

# Esplora gerarchia
print(f"Class: {citation_act.get_uri()}")
print(f"Label: {citation_act.get_has_label()[0].get_has_value()}")

superclasses = citation_act.get_is_subclass_of()
for sc in superclasses:
    print(f"  Subclass of: {sc.get_uri()}")
```

### Esempio 2: Analizzare proprietà di una relazione

```python
reader = Reader()
reader.load_instances("http://xmlns.com/foaf/0.1/", read_as="OWL")

knows = reader.get_instance("http://xmlns.com/foaf/0.1/knows")

print(f"Property: {knows.get_uri()}")
print(f"Type: {type(knows).__name__}")

# Domain e range
print("\nDomain:")
for domain in knows.get_has_domain():
    print(f"  - {domain.get_uri()}")

print("\nRange:")
for range_class in knows.get_has_range():
    print(f"  - {range_class.get_uri()}")

# Caratteristiche OWL
print(f"\nSymmetric: {knows.get_is_symmetric()}")
print(f"Transitive: {knows.get_is_transitive()}")
```

### Esempio 3: Navigare tassonomia SKOS

```python
reader = Reader()
reader.load_instances("http://example.org/thesaurus.rdf", read_as="SKOS")

concept = reader.get_instance("http://example.org/concept/biology")

# Relazioni gerarchiche SKOS
for broader in concept.get_has_broader():
    print(f"Broader: {broader.get_uri()}")

for narrower in concept.get_has_narrower():
    print(f"Narrower: {narrower.get_uri()}")

for related in concept.get_has_related():
    print(f"Related: {related.get_uri()}")
```

### Esempio 4: Iterare su tutte le istanze

```python
reader = Reader()
reader.load_instances("http://purl.org/spar/cito/", read_as="OWL")

all_instances = reader.get_all_instances()

# Filtra per tipo
relations = [inst for inst in all_instances.values() 
             if isinstance(inst, Relation)]

print(f"Total relations: {len(relations)}")

for rel in relations:
    labels = rel.get_has_label()
    if labels:
        print(f"  - {labels[0].get_has_value()}: {rel.get_uri()}")
```

### Esempio 5: Confrontare interpretazioni

```python
# Stesso grafo, diverse interpretazioni
ontology_url = "http://xmlns.com/foaf/0.1/"

# OWL: distingue ObjectProperty vs DatatypeProperty
reader_owl = Reader()
reader_owl.load_instances(ontology_url, read_as="OWL")
knows_owl = reader_owl.get_instance("http://xmlns.com/foaf/0.1/knows")
print(type(knows_owl))  # Relation

# RDFS: tutto è Property
reader_rdfs = Reader()
reader_rdfs.load_instances(ontology_url, read_as="RDFS")
knows_rdfs = reader_rdfs.get_instance("http://xmlns.com/foaf/0.1/knows")
print(type(knows_rdfs))  # Property
```

---

## 📊 UML Diagrams

### Visualizzare i diagrammi

I diagrammi PlantUML possono essere visualizzati in vari modi:

#### Opzione 1: Online (PlantUML Server)
Incolla il contenuto dei file `.puml` su:
- https://www.plantuml.com/plantuml/uml/
- https://plantuml-editor.kkeisuke.com/

#### Opzione 2: VS Code
Installa l'estensione "PlantUML" e apri i file `.puml`

#### Opzione 3: Locale
```bash
# Installa PlantUML
sudo apt install plantuml

# Genera immagini
plantuml architecture.puml
plantuml sequence.puml
plantuml model_detail.puml
```

---

### 1. Architecture Overview (`architecture.puml`)

**Mostra**: Architettura completa del sistema con tutti i layer

**Componenti principali**:
- **Orchestration Layer**: `Reader` (entry point)
- **Strategy Layer**: Pattern Strategy con OWL/RDFS/SKOS
- **Factory Layer**: Abstract Factory per creare istanze
- **Model Layer**: Gerarchia classi Python
- **Data Loading**: `Loader` per RDF

**Pattern evidenziati**:
- Strategy Pattern
- Abstract Factory Pattern
- Separation of Concerns

---

### 2. Sequence Diagram (`sequence.puml`)

**Mostra**: Flusso temporale del processo di caricamento (2-phase)

**Fasi documentate**:
1. **Initialization**: Caricamento grafo + selezione strategy
2. **Phase 1**: Creazione istanze vuote (loop su tipi RDF)
3. **Phase 2**: Popolamento con dipendenze risolte
4. **Usage**: Esempi di accesso alle istanze

**Interazioni chiave**:
- `Reader` → `Loader` → `Graph`
- `Reader` → `Strategy` → `Factory`
- `Factory` → `Graph` (query SPARQL)
- `Factory` → `Cache` (risoluzione riferimenti)

---

### 3. Model Detail (`model_detail.puml`)

**Mostra**: Gerarchia completa delle classi del dominio

**Classi documentate**:
- `SemanticArtifact` (base astratta)
- `Concept` (OWL Class)
- `Property`, `Relation`, `Attribute`, `Annotation`
- `Restriction` (OWL anonymous classes)
- `Model` (OWL Ontology)
- `Datatype` (xsd types)
- `Label`, `Comment` (utilities)

**Relazioni mostrate**:
- Inheritance hierarchy
- Composition (Label, Comment)
- Associations (domain, range, subClassOf, ...)

---

## 🎓 Best Practices

### 1. Scegliere la strategia giusta

```python
# OWL: quando hai distinzione ObjectProperty/DatatypeProperty
reader.load_instances("ontology.owl", read_as="OWL")

# RDFS: per ontologie semplici senza semantica OWL
reader.load_instances("vocabulary.rdf", read_as="RDFS")

# SKOS: per thesauri e tassonomie
reader.load_instances("thesaurus.rdf", read_as="SKOS")
```

### 2. Gestire la cache

```python
# Carica una volta, riusa
reader = Reader()
reader.load_instances("large_ontology.owl", read_as="OWL")

# Usa get_instance() molte volte (istantaneo, usa cache)
for uri in uris_to_check:
    instance = reader.get_instance(uri)
    # ...

# Libera memoria quando hai finito
reader.clear_cache()
```

### 3. Controllare l'esistenza

```python
instance = reader.get_instance("http://example.org/MaybeExists")

if instance is None:
    print("Istanza non trovata nel grafo")
else:
    print(f"Trovata: {type(instance).__name__}")
```

### 4. Navigare in sicurezza

```python
labels = concept.get_has_label()

# ✅ Controlla se la lista è vuota
if labels:
    print(labels[0].get_has_value())
else:
    print("Nessuna label disponibile")

# ✅ Itera sempre (anche se vuota)
for label in labels:
    print(f"{label.get_has_language()}: {label.get_has_value()}")
```

---

## 🔧 Extending the System

### Aggiungere una nuova Strategy

```python
# 1. Crea la strategia
class MyCustomStrategy(MappingStrategy):
    def get_type_mapping(self) -> dict:
        return {
            URIRef("http://my.org/CustomType"): MyCustomClass,
            # ...
        }
    
    def create_factory(self, graph, cache):
        return MyCustomFactory(graph, cache)

# 2. Registra
from strategy import STRATEGY_REGISTRY
STRATEGY_REGISTRY['CUSTOM'] = MyCustomStrategy

# 3. Usa
reader.load_instances("data.rdf", read_as="CUSTOM")
```

### Aggiungere una nuova Factory

```python
class MyCustomFactory(SemanticFactory):
    def populate_instance(self, instance, uri):
        if isinstance(instance, MyCustomClass):
            self._populate_my_custom(instance, uri)
        else:
            super().populate_instance(instance, uri)
    
    def _populate_my_custom(self, instance, uri):
        # Implementa logica di popolamento custom
        pass
```

---

## 📚 References

### RDF/OWL Standards
- [RDF 1.1 Concepts](https://www.w3.org/TR/rdf11-concepts/)
- [OWL 2 Web Ontology Language](https://www.w3.org/TR/owl2-overview/)
- [RDFS 1.1](https://www.w3.org/TR/rdf-schema/)
- [SKOS Simple Knowledge Organization System](https://www.w3.org/TR/skos-reference/)

### Libraries
- [RDFLib Documentation](https://rdflib.readthedocs.io/)

### Design Patterns
- [Strategy Pattern](https://refactoring.guru/design-patterns/strategy)
- [Abstract Factory Pattern](https://refactoring.guru/design-patterns/abstract-factory)

---

## 📝 License

[Specifica la tua licenza]

---

## 👥 Contributors

[Aggiungi contributors]

---

## 🐛 Known Issues & Future Work

### Known Issues
- [ ] Performance con grafi molto grandi (>100k triples)
- [ ] Inferenza OWL non implementata (usa solo triples esplicite)

### Future Work
- [ ] Aggiungere supporto OWL 2 features (property chains, keys, ...)
- [ ] Implementare lazy loading per grafi giganti
- [ ] Aggiungere validazione SHACL/ShEx
- [ ] Export verso altri formati (JSON-LD, N-Quads, ...)
- [ ] Query builder per filtrare istanze

---

**Happy Mapping! 🎉**