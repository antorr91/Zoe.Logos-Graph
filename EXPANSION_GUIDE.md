# Data Expansion Guide

## Current state
- 184 species across 7 classes (Aves, Mammalia, Amphibia, Reptilia, Insecta, Actinopterygii, Cephalopoda)
- 232 curated papers organised by 16 research themes

## How to expand the database further

### Option 1: Quick curated expansion (already done)
Run `expand_curated.py` — adds 66+ species and additional papers with verified DOIs:
```cmd
python expand_curated.py
```

### Option 2: Massive API expansion (requires your Anthropic API key)

This fetches papers from **OpenAlex** (free, 250M+ papers) and uses **Anthropic Claude** to extract structured findings from abstracts.

**Setup:**
```cmd
:: Install required packages
pip install anthropic requests

:: Set your API key (Windows cmd)
set ANTHROPIC_API_KEY=sk-ant-api03-...your-key-here...

:: PowerShell:
$env:ANTHROPIC_API_KEY="sk-ant-api03-..."
```

**Run options:**
```cmd
:: Default: 5 papers per species via OpenAlex + Anthropic claim extraction
python expand_api.py

:: Test on first 10 species only (recommended first time)
python expand_api.py --limit 10

:: Only fill species without any papers
python expand_api.py --only-missing

:: Get more papers per species
python expand_api.py --papers-per-species 15

:: Skip the LLM and just collect papers from OpenAlex (free, no API cost)
python expand_api.py --no-llm

:: Combine: only species missing papers, no LLM, 10 papers each
python expand_api.py --only-missing --no-llm --papers-per-species 10
```

**Cost estimate (with Claude Haiku 4.5):**
- ~$0.0002 per paper for claim extraction
- 184 species × 5 papers = 920 papers ≈ **$0.20 total**
- Cached responses are reused on subsequent runs

**What gets updated:**
- `outputs/species_explorer.html` — papers added to each species' profile
- `outputs/graph_explorer.html` — graph data updated
- `outputs/compare.html` — comparison tool updated

After expansion, re-run `expand_curated.py` to regenerate `literature.html` with the new papers organised by theme.

### Tips
- Cache: OpenAlex responses are cached in `data/cache/openalex/`. Delete to force re-fetch.
- Incremental: the script saves every 10 species, so you can safely interrupt with Ctrl+C.
- Polite: includes user-agent identification and rate limiting (no need to throttle manually).

## What's working / what needs an API key

| Action | Needs Anthropic API? | Notes |
|--------|---------------------|-------|
| Add curated species/papers | ❌ No | Already done — 184 species ready |
| Fetch papers from OpenAlex | ❌ No | Free, just need internet |
| Extract findings from abstracts | ✅ Yes | Use --no-llm to skip |
| Generate HTML files | ❌ No | Just runs Python |
