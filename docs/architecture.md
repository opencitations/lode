# Architecture

:::{warning} Beta version · unstable
LODE 2 is under development and in beta: anything described in this documentation may change. This page describes internals that can change without notice.
:::

LODE is built in layers. Data flows in one direction, from the document you give it to the documentation it produces, and each layer knows only the one before it. A new format is a **profile** that plugs into this flow. The cards below follow it in order, and each one says what the step does, what you can change, and where to read more.

::::{div}
:class: text-center
```{mermaid}
%%{init: {"themeVariables": {"fontSize": "16px"}, "flowchart": {"nodeSpacing": 30, "rankSpacing": 30, "padding": 12}}}%%
flowchart TB
    doc(["Document<br/>OWL · RDF · SKOS"])
    reader["2 · Reader"]
    model[["3 · Model"]]
    artefact["4 · Artefact"]
    viewer["5 · Viewer"]
    html(["HTML"])
    rdf(["RDF serializations<br/>Turtle · RDF/XML · N3"])
    profile{{"1 · Profile"}}

    doc --> reader
    reader -- populates --> artefact
    artefact --> viewer
    viewer --> html
    viewer --> rdf
    reader -. instantiates .-> model
    profile -. configures .-> reader
    profile -. configures .-> viewer

    classDef flow fill:#dbeafe,stroke:#60a5fa,color:#1f2937
    classDef shared fill:#fef3c7,stroke:#f59e0b,color:#1f2937
    classDef io fill:#e5e7eb,stroke:#9ca3af,color:#1f2937
    class reader,artefact,viewer flow
    class model,profile shared
    class doc,html,rdf io
```
::::

The numbers are those of the cards below. Solid arrows are the data flow; dotted ones are what the steps rely on.

::::{grid} 1 1 1 1

:::{card} 1. Profile
**What it is.** The package `lode/profiles/<format>/` that tells LODE how to read and show one format. It is the only place that knows which formats exist.
+++
[Profile](examples/profile.ipynb)
:::

:::{card} 2. Reader
**What it does.** Turns an RDF graph into model entities, following a YAML mapper and, where YAML is not enough, a reader class.
+++
[Reader](examples/reader.ipynb)
:::

:::{card} 3. Model
**What it is.** The entity classes of `lode.models` (`Concept`, `Relation`, `Statement`, ...). The reader creates them, the artefact holds them, the viewer reads them.
+++
[Model](examples/model.ipynb)
:::

:::{card} 4. Artefact
**What it is.** The hand-over between the reader and everything after it: entities, graph, warnings and format. Viewers, the builder and the API depend on it only.
+++
[Artefact](examples/artefact.ipynb)
:::

:::{card} 5. Viewer
**What it does.** Turns the artefact into the dictionaries the HTML templates render, and into RDF serializations.
+++
[Viewer](viewer.md)
:::
::::

## Dependency rules

- The viewer does not import the reader.
- The model imports neither the reader nor the viewer.
- The reader does not import the viewer.
- The core (reader, viewer, model, helpers) reaches a profile only through the registry in `lode.profiles`. It never imports a profile package.
- A profile does not import another profile.

`tests/unit/core/test_architecture.py` checks these rules on the source files, so a violation fails the test suite.
