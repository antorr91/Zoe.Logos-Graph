#!/usr/bin/env python3
"""
auto_approve_and_export.py — Bypass the heavy HTML pages.

Does three things:
  1. Auto-approves all 89 newly discovered species (creates approved_species.json
     directly from discovered_species.json, no HTML needed).
  2. Exports a clean CSV of every paper found so far (one row per paper:
     species, title, year, journal, DOI link, citations, themes, relevance).
  3. Reports which species still need to be fetched (i.e., the new ones).

After this, you run:
    python fetch_papers_v3.py --skip-llm
and only the new 89 species get processed (existing 184 are already cached).

USAGE:
    python auto_approve_and_export.py
"""
from __future__ import annotations
import json, csv, sys
from pathlib import Path
from datetime import datetime

PROJ = Path(__file__).resolve().parent
DISCOVERY_DIR = PROJ / 'data' / 'discovery'
PAPERS_DIR    = PROJ / 'data' / 'papers'

# ── 1. Auto-approve all discovered species ────────────────────────────────────
def auto_approve():
    src = DISCOVERY_DIR / 'discovered_species.json'
    if not src.exists():
        print(f'! Missing: {src}')
        print('  Run discover_species.py first.')
        return False
    data = json.loads(src.read_text(encoding='utf-8'))
    candidates = data.get('candidates', [])
    approved = {
        'generated':  datetime.now().isoformat(),
        'count':      len(candidates),
        'species':    candidates,
    }
    out = DISCOVERY_DIR / 'approved_species.json'
    out.write_text(json.dumps(approved, ensure_ascii=False, indent=2),
                   encoding='utf-8')
    print(f'✓ Approved {len(candidates)} species')
    print(f'  Wrote {out}')
    return True


# ── 2. Export CSV of all papers found so far ─────────────────────────────────
def export_papers_csv():
    src = PAPERS_DIR / 'papers_extracted.json'
    if not src.exists():
        print(f'  (No papers_extracted.json yet, skipping CSV export)')
        return
    data = json.loads(src.read_text(encoding='utf-8'))
    rows = []
    for sp in data.get('species', []):
        for p in sp.get('papers', []):
            doi = p.get('doi', '')
            link = f'https://doi.org/{doi}' if doi else (
                f'https://pubmed.ncbi.nlm.nih.gov/{p.get("pmid","")}'
                if p.get('pmid') else '')
            rows.append({
                'species_scientific': sp.get('sci', ''),
                'species_common':     sp.get('common', ''),
                'class':              sp.get('class_', ''),
                'family':             sp.get('family', ''),
                'paper_title':        (p.get('title') or '')[:300],
                'year':               p.get('year', ''),
                'journal':            p.get('venue', ''),
                'citations':          p.get('cited_by', 0),
                'is_open_access':     'yes' if p.get('is_oa') else 'no',
                'link':               link,
                'doi':                doi,
                'themes':             '; '.join(p.get('themes', [])),
                'study_type':         p.get('study_type', ''),
                'setting':            p.get('methods_setting', ''),
                'relevance':          p.get('relevance', ''),
                'score':              round(p.get('score', 0), 2),
            })
    out_csv = PAPERS_DIR / 'all_papers.csv'
    if not rows:
        print('  No papers to export')
        return
    with out_csv.open('w', newline='', encoding='utf-8-sig') as f:
        # utf-8-sig = adds BOM so Excel opens it with correct encoding
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f'✓ Wrote CSV: {out_csv}')
    print(f'  {len(rows)} papers exported (open in Excel)')

    # Also write per-species link list (plain text, lightweight)
    out_txt = PAPERS_DIR / 'all_papers_links.txt'
    with out_txt.open('w', encoding='utf-8') as f:
        for sp in data.get('species', []):
            f.write(f"\n=== {sp.get('sci','')} ({sp.get('common','')}) ===\n")
            for p in sp.get('papers', []):
                doi = p.get('doi', '')
                link = f'https://doi.org/{doi}' if doi else ''
                f.write(f"  [{p.get('year','????')}] {(p.get('title') or '')[:120]}\n")
                if link:
                    f.write(f"    {link}\n")
                f.write(f"    Journal: {p.get('venue','')}  ·  "
                        f"Cites: {p.get('cited_by',0)}  ·  "
                        f"Themes: {', '.join(p.get('themes',[]))}\n")
    print(f'✓ Wrote plain-text link list: {out_txt}')


# ── 3. Report what's still to fetch ──────────────────────────────────────────
def report_pending():
    appr = DISCOVERY_DIR / 'approved_species.json'
    cache_dir = PAPERS_DIR / 'cache'
    if not appr.exists():
        return
    new_species = json.loads(appr.read_text(encoding='utf-8')).get('species', [])
    import re
    def safe(s): return re.sub(r'[^a-z0-9]+', '_', s.lower())
    todo = []
    for sp in new_species:
        cache_path = cache_dir / f'{safe(sp["sci"])}.json'
        if not cache_path.exists() or cache_path.stat().st_size < 50:
            todo.append(sp['sci'])
    print(f'\n=== {len(todo)} new species still need fetching ===')
    if todo and len(todo) <= 20:
        for s in todo: print(f'  • {s}')
    elif todo:
        for s in todo[:10]: print(f'  • {s}')
        print(f'  ... and {len(todo)-10} more')
    print(f'\nNext step:')
    print(f'  python fetch_papers_v3.py --skip-llm')
    print(f'  (existing 184 species use cache, only the new ones get fetched)')


if __name__ == '__main__':
    print('Zoe.Logos-Graph — auto-approve + export\n')
    if auto_approve():
        export_papers_csv()
        report_pending()
