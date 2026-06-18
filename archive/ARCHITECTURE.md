# Zoe.Logos — Architecture Reference

**v2.1 · May 2026**

---

## Core mental model

```
Taxon / Species
  → CommunicationClaim          ← biological/scientific assertion
      → SignalTerm
      → ContextTerm
      → FunctionTerm
      → ResearchTopicTerm
      → ClaimEvidence            ← how we know it
          → Paper
          → RecordingAsset
          → SignalAnnotation
          → Spectrogram
```

**CommunicationClaim** = "Species X produces signal Y in context Z with putative function W"
**ClaimEvidence** = the specific text, method, and source that supports that assertion

A claim can have **multiple evidence records** from different papers, recordings, or annotations.
`method_id` belongs to `ClaimEvidence`, not to `CommunicationClaim`.

---

## Canonical schema (src/db.py)

| Table | Purpose |
|---|---|
| `species` | Taxonomic backbone — GBIF-validated |
| `species_metadata` | Images, summaries, semiotic annotation |
| `papers` | Scientific literature |
| `paper_species` | Paper ↔ species links |
| `open_literature` | Curated DOI links per species |
| `signal_terms` | Controlled vocab — signal/vocalisation types |
| `signal_aliases` | Alias → canonical signal |
| `context_terms` | Controlled vocab — behavioural contexts |
| `function_terms` | Controlled vocab — communicative functions |
| `method_terms` | Controlled vocab — research methods |
| `research_topic_terms` | Scientific topics (separate from context/function) |
| `communication_claims` | Normalised biological assertions |
| `claim_evidence` | Evidence supporting claims |
| `recording_assets` | Audio files or external recordings |
| `signal_annotations` | Labelled time-frequency segments |
| `spectrograms` | Generated spectrogram images |
| `vocab_suggestions` | Unknown/ambiguous labels for review |

---

## Key conceptual distinctions

```
context        = observable behavioural situation  e.g. "predator response"
function       = putative communicative role        e.g. "predator warning"
research_topic = scientific phenomenon studied      e.g. "vocal learning", "dialects"
method         = how the evidence was generated     e.g. "playback experiment"
```

method_id belongs to ClaimEvidence, NOT to CommunicationClaim.

---

## Pipeline run order

```bash
python scripts/db_init.py
python scripts/00_generate_species_db.py
python scripts/01_match_taxa.py
python scripts/02_fetch_species_metadata.py
python scripts/06_fetch_literature.py
python scripts/08_fetch_pubmed.py
python scripts/09_extract_claims.py --limit 200   # needs ANTHROPIC_API_KEY
python scripts/13_import_recordings.py
python scripts/12_generate_spectrograms.py
python scripts/11_community_detection.py
python scripts/07_export_web.py
python scripts/05_build_graph.py

# Repair / verify:
python fix_all.py
python setup_v2.py
```

---

## Curation statuses

seed → extracted → curated → needs_review → rejected

## Evidence support levels

explicit | implicit | inferred | uncertain

## Semiotic classes (species_metadata.semiotic_class)

icon | index | symbol | mixed | unknown

---

## Files still needing update (TODO)

- src/services/claim_ingest.py    — write to claim_evidence not legacy table
- src/prompts.py                  — v2 extraction prompt
- scripts/09_extract_claims.py    — PaperExtractionResult validation
- scripts/07_export_web.py        — read claim_evidence, not legacy fields
- scripts/05_build_graph.py       — replace with 14_build_evidence_graph.py

## src/db_v2.py status

Compatibility wrapper only — re-exports from src/db.py.
Do NOT add new schema definitions there.

## Known limitations

- 57% of papers have no abstract (LLM extraction limited)
- 98/4436 evidence records are LLM-extracted (rest are seed-only)
- vocab_suggestions, method_terms, research_topic_terms are empty
- 30 duplicate species were merged (May 2026)
