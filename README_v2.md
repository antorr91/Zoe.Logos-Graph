# Zoe.Logos — Evidence-backed Comparative Atlas of Animal Communication

**v0.0 architecture · April 2026**

A structured knowledge graph linking taxa, signal types, behavioural contexts, communicative functions, scientific literature, recordings, and bioacoustic annotations.

This is not a chatbot, a flat species catalogue, or a generic animal-calls database. It is a system designed to make animal-communication knowledge **explorable, comparable, and auditable**.

---

## The central object: CommunicationClaim

```
Taxon → Signal Type → Context → Function
              ↑
       CommunicationClaim          ← the biological assertion
              ↑
        ClaimEvidence              ← method, paper, support level, confidence
              ↑
       Paper / Recording / Annotation
```

A `CommunicationClaim` is an assertion like:
> *Megaptera novaeangliae* produces `song` in `breeding context` with putative function `mate attraction`.

Each claim has zero or more `ClaimEvidence` records that document **how we know** — which paper, which method, what evidence text, what support level (explicit / implicit / inferred / uncertain), and what extraction provenance (manual / seed / LLM / curated).

The same claim can have multiple evidence records from different studies, methods, or extraction passes.

---

## Architecture (v2 schema)

```
┌──────────────────────────────────────────────────────┐
│  1. TAXONOMIC BACKBONE                               │
│     species, species_synonyms, species_metadata      │
└──────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────┐
│  2. CONTROLLED VOCABULARY                            │
│     signal_terms (with parent_id for hierarchy),     │
│     context_terms, function_terms (level: bio/comm/  │
│     pragmatic), research_topics, method_terms        │
└──────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────┐
│  3. LITERATURE                                       │
│     papers, paper_species, open_literature           │
└──────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────┐
│  4. CLAIMS LAYER                                     │
│     communication_claims (species + signal + context │
│       + function + research_topic + curation_status) │
│     claim_evidence (claim_id + paper_id + method_id  │
│       + evidence_text + support_level + confidence)  │
└──────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────┐
│  5. BIOACOUSTIC RESOURCES                            │
│     recording_assets (audio files / external links)  │
│     signal_annotations (time-frequency segments)     │
│     spectrograms (generated images)                  │
└──────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────┐
│  6. CURATION QUEUE                                   │
│     review_queue (issues, severity, suggested fix)   │
└──────────────────────────────────────────────────────┘
```

---

## Pipeline

```bash
# 0. Migrate v1 → v2 (one-time, preserves v1 data)
python scripts/db_migrate_v2.py

# 1. Generate base species records (curated 130+ species)
python scripts/00_generate_species_db.py

# 2. Enrich with Wikipedia images and summaries
python scripts/02_fetch_species_metadata.py

# 3. Import recordings (Xeno-canto + curated + local)
python scripts/13_import_recordings.py
#    Set XC_API_KEY env var for Xeno-canto v3.

# 4. Generate spectrograms with librosa
python scripts/12_generate_spectrograms.py
#    pip install librosa soundfile matplotlib numpy

# 5. Fetch literature (Crossref + OpenAlex)
python scripts/06_fetch_literature.py
python scripts/08_fetch_pubmed.py

# 6. Extract claims from abstracts (uses Claude API)
python scripts/09_extract_claims.py --limit 200
#    Set ANTHROPIC_API_KEY env var.

# 7. Build community graph
python scripts/11_community_detection.py

# 8. Export web JSON
python scripts/07_export_web.py

# 9. Generate evidence summaries / scoping reviews
python scripts/10_generate_review.py --mode species --query "Megaptera novaeangliae"
python scripts/10_generate_review.py --mode function --query "alarm call"
```

---

## Model species (MVP focus)

The v2 atlas targets ~130 species across well-studied taxa:

**Cetaceans** — humpback whale, sperm whale, orca, bottlenose dolphin, beluga, harbour porpoise
**Birds (oscines)** — zebra finch, Bengalese finch, canary, great tit, Japanese tit, white-crowned sparrow, song sparrow, mockingbird, ravens
**Birds (parrots)** — African grey parrot, budgerigar, scarlet macaw
**Primates** — vervet monkey, Campbell's monkey, marmoset, chimpanzee, bonobo, gorilla, gibbon, lemur, macaque
**Bats** — big brown bat, Mexican free-tailed bat, large flying fox
**Rodents** — house mouse, Norway rat, ground squirrel
**Carnivores** — domestic dog, cat, grey wolf, ferret, spotted hyena
**Ungulates** — horse, cattle, sheep, goat, pig, red deer, reindeer
**Elephants** — Asian and African
**Amphibians** — túngara frog, tree frogs, Xenopus, common frog, bullfrog
**Insects** — honey bee, field cricket, fruit fly, Pacific cricket, locust
**Fish** — midshipman fish, zebrafish, cod, tilapia
**Reference species** — *Homo sapiens*

---

## Foundational literature

The atlas includes 12 foundational works in animal communication and language evolution, each annotated with:

- Central thesis
- Key claims
- Open debates
- Relevance to specific species

Texts include: Hauser-Chomsky-Fitch (2002), Pinker & Bloom (1990), Marler (1970), Seyfarth-Cheney-Marler (1980), Tomasello (2008), Fitch (2010), Cheney & Seyfarth (1990), Zuberbuehler (2003), Searcy & Nowicki (2005), Pepperberg (2009), Sebeok (2001), Pinker (1994).

---

## Distinguishing zoosemiotic concepts

The v2 schema makes explicit several distinctions that v1 conflated:

| Distinction | v1 problem | v2 solution |
|---|---|---|
| Communication vs signalling vs perception | echolocation = "vocal communication" | `comm_level` field on species_metadata |
| Biological vs communicative vs pragmatic function | "mate attraction" = "predator warning" = "flee response" | `function_terms.level` |
| Vocal vs non-vocal acoustic | bee waggle dance = "vocal" | `signal_terms.modality` and `signal_channel` |
| Method belongs to evidence | "method" attached to claim | `method_id` on `claim_evidence`, not on `claim` |
| Research topic vs context | "vocal learning" as behavioural context | separate `research_topics` table |
| Iconic / indexical / symbolic | not represented | `species_metadata.semiotic_class` |

---

## What this is NOT

- **Not a "systematic review" generator.** `10_generate_review.py` produces *evidence summaries* and *scoping reviews*. A true systematic review requires PRISMA, registered protocol, and risk-of-bias analysis. Document outputs are explicitly labelled.
- **Not a substitute for primary literature.** Every claim links back to its evidence and supporting paper. The atlas is a navigation layer over the literature, not a replacement.
- **Not complete.** ~93% of v1 claims were seed-only (not paper-backed). v2 schema makes this visible via `curation_status` and the `review_queue`.

---

## Contributing

The `review_queue` table identifies items needing curation:

```sql
SELECT item_type, issue, COUNT(*)
FROM review_queue
WHERE status='open'
GROUP BY item_type, issue
ORDER BY severity DESC;
```

Contributions welcome via pull request. See `data/annotations/ANNOTATION_GUIDELINES_v1.md`.

---

## License

Code: MIT. Data and curated annotations: CC BY 4.0. Audio recordings retain their original licenses.
