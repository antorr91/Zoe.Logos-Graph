#!/usr/bin/env python3
"""
fetch_papers_v3.py — Modular paper fetcher for Zoe.Logos-Graph.

Pipeline per species:
  1. Multi-source retrieval (OpenAlex + PubMed + Semantic Scholar)
  2. Hard peer-review filters (no preprint, no editorial, ...)
  3. Deduplication across sources
  4. Relevance scoring with multiple weighted factors
  5. Variable quota: 3-15 papers per species depending on availability
  6. LLM extraction (Claude Sonnet, batches of 3): research question,
     methods, findings, themes, study type, confidence
  7. Output: papers_extracted.json + review_papers.html

USAGE:
  set ANTHROPIC_API_KEY=sk-ant-...
  set OPENALEX_EMAIL=a.m.c.torrisi@qmul.ac.uk
  set NCBI_API_KEY=your-key            (optional, faster PubMed)
  set SEMANTIC_SCHOLAR_KEY=your-key    (optional, faster Semantic Scholar)
  python fetch_papers_v3.py
  python fetch_papers_v3.py --limit 5    # process only first 5 species (test)
  python fetch_papers_v3.py --skip-llm   # skip LLM extraction (cheap dry run)
"""
from __future__ import annotations
import os, sys, json, time, argparse, re
from pathlib import Path
from datetime import datetime

# Allow running this script from any cwd by adding our package to sys.path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from zoelogos_fetcher.sources import OpenAlexSource, PubMedSource, SemanticScholarSource
from zoelogos_fetcher.filters import filter_peer_review, deduplicate, rank_papers
from zoelogos_fetcher.filters.scoring import quota_for_species
from zoelogos_fetcher.extract import LLMExtractor
from zoelogos_fetcher.review  import write_review_html

# ── Paths ────────────────────────────────────────────────────────────────────
PROJ          = HERE
OUT_DIR       = PROJ / 'data' / 'papers'
OUT_DIR.mkdir(parents=True, exist_ok=True)
SPECIES_HTML  = PROJ / 'outputs' / 'species_explorer.html'
APPROVED_PATH = PROJ / 'data' / 'discovery' / 'approved_species.json'
CACHE_DIR     = OUT_DIR / 'cache'
CACHE_DIR.mkdir(exist_ok=True)


# ── Input species: merge existing + newly approved ───────────────────────────
def load_target_species() -> list[dict]:
    """Returns list of {sci, common, group, class_, order_, family}."""
    targets = []

    # Existing species from species_explorer.html
    if SPECIES_HTML.exists():
        html = SPECIES_HTML.read_text(encoding='utf-8')
        m = re.search(r'const EMBEDDED_DB = (\[.*?\]);', html, re.DOTALL)
        if m:
            for sp in json.loads(m.group(1)):
                targets.append({
                    'sci':     sp['sci'],
                    'common':  sp.get('en', ''),
                    'group':   'existing',
                    'class_':  sp.get('class_', ''),
                    'order_':  sp.get('order_', ''),
                    'family':  sp.get('family', ''),
                })
            print(f'  Loaded {len(targets)} existing species from species_explorer.html')

    # Newly approved species from discovery step
    if APPROVED_PATH.exists():
        with APPROVED_PATH.open(encoding='utf-8') as f:
            data = json.load(f)
        new_sp = data.get('species', [])
        existing_sci = {t['sci'].lower() for t in targets}
        added = 0
        for sp in new_sp:
            if sp['sci'].lower() not in existing_sci:
                targets.append({
                    'sci':    sp['sci'],
                    'common': sp.get('common', ''),
                    'group':  sp.get('group', 'new'),
                    'class_': sp.get('class_', ''),
                    'order_': sp.get('order_', ''),
                    'family': sp.get('family', ''),
                })
                added += 1
        print(f'  Loaded {added} new species from approved_species.json')

    return targets


def cache_path(sci: str) -> Path:
    safe = re.sub(r'[^a-z0-9]+', '_', sci.lower())
    return CACHE_DIR / f'{safe}.json'


def fetch_for_species(sp: dict, sources: list) -> list[dict]:
    """Multi-source retrieval for one species. Returns merged raw records."""
    cp = cache_path(sp['sci'])
    if cp.exists() and cp.stat().st_size > 50:
        try:
            return json.loads(cp.read_text(encoding='utf-8'))
        except Exception:
            pass
    all_recs = []
    for src in sources:
        try:
            recs = src.search_species(sp['sci'], sp.get('common', ''),
                                      max_results=40)
            all_recs.extend(recs)
        except Exception as e:
            print(f'  ! {src.name} failed for {sp["sci"]}: {e}', file=sys.stderr)
    cp.write_text(json.dumps(all_recs, ensure_ascii=False, indent=2),
                  encoding='utf-8')
    return all_recs


# ── Pipeline per species (no LLM) ────────────────────────────────────────────
def pipeline_for_species(sp: dict, sources: list, verbose: bool = True) -> dict:
    raw = fetch_for_species(sp, sources)
    # Filter and dedup
    filtered, fst = filter_peer_review(raw)
    deduped, dst = deduplicate(filtered)
    ranked = rank_papers(deduped)
    # Apply quota
    quota = quota_for_species(len(ranked))
    top = ranked[:quota]
    if verbose:
        print(f'  {sp["sci"]:35} raw={fst["in"]:3}  '
              f'peer={fst["kept"]:3}  uniq={dst["out"]:3}  '
              f'quota={quota}  → {len(top)}')
    return {
        'sci':     sp['sci'],
        'common':  sp.get('common', ''),
        'group':   sp.get('group', ''),
        'class_':  sp.get('class_', ''),
        'order_':  sp.get('order_', ''),
        'family':  sp.get('family', ''),
        'stats':   {'raw': fst['in'], 'filtered': fst['kept'],
                    'unique': dst['out'], 'quota': quota,
                    'kept': len(top)},
        'papers':  top,
    }


# ── LLM extraction stage ─────────────────────────────────────────────────────
def llm_enrich(species_record: dict, extractor: LLMExtractor) -> dict:
    """Adds LLM-extracted fields to each paper in the species record."""
    sci = species_record['sci']
    papers = species_record.get('papers', [])
    if not papers:
        return species_record
    print(f'  LLM extracting for {sci} ({len(papers)} papers)...')
    enriched = extractor.extract_all(papers, target_species=sci)
    species_record['papers'] = enriched
    return species_record


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0,
                    help='Process only first N species (for testing)')
    ap.add_argument('--skip-llm', action='store_true',
                    help='Skip LLM extraction (fast, no API cost)')
    ap.add_argument('--model', type=str, default='claude-sonnet-4-5-20250929',
                    help='Anthropic model id')
    ap.add_argument('--start', type=int, default=0,
                    help='Skip the first N species (resume option)')
    args = ap.parse_args()

    print(f'Zoe.Logos-Graph — fetch_papers_v3')
    print(f'Started: {datetime.now().isoformat()}')

    targets = load_target_species()
    if args.start:
        targets = targets[args.start:]
        print(f'  Skipping first {args.start} → {len(targets)} remaining')
    if args.limit:
        targets = targets[:args.limit]
        print(f'  Limited to first {len(targets)} species (test mode)')

    # Init sources
    sources = [OpenAlexSource(), PubMedSource(), SemanticScholarSource()]
    print(f'  Sources: {[s.name for s in sources]}')

    # Init LLM extractor
    extractor = None
    if not args.skip_llm:
        if not os.environ.get('ANTHROPIC_API_KEY'):
            print('! ANTHROPIC_API_KEY not set — set it or pass --skip-llm',
                  file=sys.stderr)
            sys.exit(1)
        extractor = LLMExtractor(model=args.model, batch_size=3)
        print(f'  LLM: {args.model}, batch=3')

    # Pipeline
    results = []
    print(f'\nProcessing {len(targets)} species:\n')
    print('=' * 78)

    for i, sp in enumerate(targets, 1):
        print(f'[{i}/{len(targets)}] {sp["sci"]}')
        rec = pipeline_for_species(sp, sources)
        if extractor and rec['papers']:
            rec = llm_enrich(rec, extractor)
            # checkpoint after each LLM-processed species
            tmp_path = OUT_DIR / 'papers_extracted_partial.json'
            tmp_path.write_text(json.dumps(results + [rec],
                                            ensure_ascii=False, indent=2),
                                encoding='utf-8')
        results.append(rec)

    # Final output
    out = {
        'generated':  datetime.now().isoformat(),
        'n_species':  len(results),
        'n_papers':   sum(len(r.get('papers', [])) for r in results),
        'species':    results,
    }
    if extractor:
        out['llm_stats'] = extractor.stats()

    final_path = OUT_DIR / 'papers_extracted.json'
    final_path.write_text(json.dumps(out, ensure_ascii=False, indent=2),
                          encoding='utf-8')
    print(f'\nWrote {final_path}')

    # Build review HTML
    species_dict = {r['sci']: r for r in results}
    review_path = OUT_DIR / 'review_papers.html'
    write_review_html(species_dict, review_path)
    print(f'Wrote {review_path}')

    if extractor:
        st = extractor.stats()
        print(f'\nLLM usage: {st["calls"]} calls, '
              f'{st["in_tokens"]} in / {st["out_tokens"]} out tokens, '
              f'~${st["cost_usd"]} estimated cost')

    print('\nDONE.')
    print(f'  Next: open {review_path}, select papers to approve,')
    print(f'  click "Export approved" → produces approved_papers.json')


if __name__ == '__main__':
    main()
