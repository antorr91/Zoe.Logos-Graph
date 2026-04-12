# Zoe.Logos-Graph

**LLM-based knowledge graph for animal communication literature**

> *The scientific value of Zoe.Logos-Graph comes from disciplined structure, not from vague generation.*

---

## What this is

Zoe.Logos-Graph is a research software pipeline that:

1. Reads scientific abstracts on animal vocal communication
2. Extracts structured knowledge using an LLM
3. Validates and normalises the extracted records
4. Builds a knowledge graph linking species, vocalisations, contexts, functions, methods, and papers
5. Supports exploration of comparative communication patterns across species

This is not a chatbot. It is a structured scientific extraction and graph system.

---

## Core question

> Can an LLM extract useful, normalised, graph-ready knowledge from scientific abstracts about animal communication?

---

## v1 Scope

### In scope
- Scientific abstracts only
- Topic: animal vocal communication and comparative communication literature
- Structured JSON record per abstract
- Small knowledge graph from those records
- Notebook or minimal app visualisation

### Out of scope (v1)
- Full-text parsing at scale
- Automated biological truth claims beyond the text
- Audio inference from text alone
- Foundation-model training
- Large multimodal pipelines

---

## Graph ontology

### Node types

| Node | Description |
|---|---|
| `Paper` | A scientific publication |
| `Species` | A biological species |
| `VocalisationType` | A type of vocalisation (e.g. call, song, alarm) |
| `BehaviouralContext` | Context in which vocalisation occurs |
| `CommunicationFunction` | Inferred communicative function |
| `AnalysisMethod` | Analytical or computational method used |
| `DatasetResource` | A named dataset or recording archive |

### Edge types

| Edge | Meaning |
|---|---|
| `PAPER_STUDIES_SPECIES` | Paper focuses on a species |
| `PAPER_REPORTS_VOCALISATION` | Paper describes a vocalisation type |
| `VOCALISATION_OCCURS_IN_CONTEXT` | Vocalisation linked to behavioural context |
| `VOCALISATION_HAS_FUNCTION` | Vocalisation linked to communicative function |
| `PAPER_USES_METHOD` | Paper employs an analysis method |
| `PAPER_LINKS_DATASET` | Paper references a dataset |
| `SPECIES_PRODUCES_VOCALISATION` | Species linked to vocalisation type |

---

## Pipeline stages

```
abstracts → annotation → LLM extraction → validation → normalisation → graph → exploration
```

1. **Corpus collection** — gather relevant abstracts
2. **Annotation** — create gold examples and guidelines
3. **LLM extraction** — generate structured JSON from abstracts
4. **Validation** — check JSON validity and field constraints
5. **Normalisation** — resolve species names, harmonise labels
6. **Graph construction** — convert records into nodes and edges
7. **Exploration** — visualise in notebook or small app

---

## Repository structure

```
zoe-logos-graph/
├── README.md
├── data/
│   ├── raw/            # Original abstracts (txt, json, csv)
│   ├── annotations/    # Gold-standard annotated records
│   ├── processed/      # Validated and normalised records
│   └── graph/          # Graph export files (GraphML, JSON-LD)
├── notebooks/
│   └── 01_schema_and_guidelines.ipynb  # field definitions and annotation guidelines
├── src/
│   ├── schema.py        # Pydantic schema definition
│   ├── validation.py    # Record validation logic
│   ├── prompts.py       # LLM extraction prompts
│   ├── extraction.py    # Extraction pipeline
│   ├── normalisation.py # Species and term normalisation
│   ├── graph_builder.py # Graph construction from records
│   └── utils.py         # Shared utilities
├── configs/
│   └── config.yaml      # Model, paths, extraction settings
├── outputs/             # Generated graphs and reports
├── requirements.txt
└── pyproject.toml
```

---

## Quickstart

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Validate a record
python -m src.validation --input data/annotations/pilot.json

# Run extraction on a set of abstracts
python -m src.extraction --input data/raw/abstracts.json --output data/processed/

# Build the graph
# From gold annotations (no extraction step needed)
python -m src.graph_builder --input data/annotations/pilot.json --output outputs/graph.graphml

# From LLM-extracted records
python -m src.graph_builder --input data/processed/extracted.json --output outputs/graph.graphml

# Explore the schema and guidelines
jupyter lab notebooks/01_schema_and_guidelines.ipynb
```

---

## v1 Success criteria

- [ ] Schema is stable and documented
- [ ] At least 10 pilot abstracts annotated consistently
- [ ] Extraction pipeline produces valid JSON reliably
- [ ] Graph is interpretable and visually useful
- [ ] System surfaces meaningful links between species, vocalisations, and contexts

---

## Annotation principles

- Extract only what is supported by the abstract
- Prefer explicit statements over inferred interpretations
- Preserve uncertainty when the abstract is vague
- Normalise species names and behaviour terms where possible
- Keep `main_outcome` short and faithful to the paper

---

## Immediate next steps

1. Finalise the schema (`src/schema.py`)
2. Write annotation guidelines (`notebooks/01_schema_and_guidelines.ipynb`)
3. Create 10 pilot examples (`data/annotations/`)
4. Build JSON validator (`src/validation.py`)
5. Draft first extraction prompt (`src/prompts.py`)
6. Build graph from gold annotations before using model outputs

---

## Domain alignment

Computational ethology · vocal behaviour · animal cognition · bioacoustics · LLM-based information extraction · knowledge graph construction
