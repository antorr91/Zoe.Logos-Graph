# fetch_papers_v3 — Modular paper fetcher

A 3-source academic paper retrieval and LLM-based extraction system for
Zoe.Logos-Graph, inspired by Elicit / Semantic Scholar.

## What it does

For each species in your database (and the newly approved ones from the
discovery step), it:

1. **Retrieves** papers from three sources: OpenAlex, PubMed, Semantic Scholar
2. **Filters** hard for peer-review: drops preprints (arXiv, bioRxiv, SSRN…),
   editorials, comments, retractions, papers without DOI or abstract
3. **Deduplicates** across sources by DOI / (title, year)
4. **Ranks** by relevance: keyword overlap, citations, journal quality,
   recency, species-name match
5. **Applies variable quota**: 15 papers for famous species (≥50 available),
   8 for well-studied, 5 for moderate, all available for niche ones
6. **Extracts** each abstract with Claude Sonnet (Elicit-style): research
   question, methods (recording type/sample/setting/analysis), key findings,
   implications, limitations, themes, study type, relevance, confidence
7. **Outputs** `papers_extracted.json` + `review_papers.html`

## How to install

Unzip into your project root. You will end up with:

```
E:\zoe-logos-graph\
├── fetch_papers_v3.py
├── zoelogos_fetcher/
│   ├── __init__.py
│   ├── http_util.py
│   ├── sources/      (openalex, pubmed, semantic_scholar)
│   ├── filters/      (peer_review, dedup, scoring)
│   ├── extract/      (schema, llm)
│   └── review/       (html_builder)
└── ...
```

## How to run

Set environment variables (the Anthropic key is the only mandatory one):

```cmd
set ANTHROPIC_API_KEY=sk-ant-...           REM REQUIRED for LLM extraction
set OPENALEX_EMAIL=a.m.c.torrisi@qmul.ac.uk    REM polite pool, faster
set NCBI_API_KEY=...                       REM optional, faster PubMed (10/s vs 3/s)
set SEMANTIC_SCHOLAR_KEY=...               REM optional, faster Semantic Scholar
```

To test the pipeline on 3 species without spending LLM money:

```cmd
python fetch_papers_v3.py --limit 3 --skip-llm
```

This will:
- Retrieve papers from 3 sources for the first 3 species
- Apply all filters, dedup, ranking, quota
- Skip LLM extraction
- Write `data/papers/papers_extracted.json` and `review_papers.html`

If the output looks good, run for real:

```cmd
python fetch_papers_v3.py
```

This processes all your species (184 existing + 89 newly approved = 273).
Expected: ~2-3 hours, ~$3-4 in Anthropic API costs.

## Resume / partial runs

The script caches API responses per species in `data/papers/cache/`. If you
interrupt and restart, retrieval skips already-fetched species.

You can also resume from a given index with `--start N`.

## Output

After completion:
- `data/papers/papers_extracted.json` — full dataset with extractions
- `data/papers/review_papers.html` — interactive review page (open in browser)

In the review page you can filter by relevance, study type, search by title
or species. Select the papers you want to keep, then "Export approved" to
get `approved_papers.json` for merging into the database.

## Costs and timing (estimates)

- 273 species × ~6 papers average = ~1640 papers
- Sonnet batch=3 → ~550 API calls
- At Sonnet 4.5 pricing (~$3 input / $15 output per M tokens): ~$3-4 total
- Total wall-clock time: ~2-3 hours for retrieval+LLM, less if you use
  api keys for NCBI and Semantic Scholar (faster sources)
