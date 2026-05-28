#!/usr/bin/env python3
"""
expand_api.py — Massive data expansion using OpenAlex + Anthropic API.

What it does:
1. For each existing species, fetches papers from OpenAlex (free, no key needed)
2. Optionally uses Anthropic API to extract structured findings from abstracts
3. Adds papers to the species DB
4. Regenerates HTML files

Requirements:
  pip install anthropic requests

Usage:
  # Set your API key
  set ANTHROPIC_API_KEY=sk-ant-api03-...    (Windows cmd)
  $env:ANTHROPIC_API_KEY="sk-ant-api03-..."  (PowerShell)
  export ANTHROPIC_API_KEY="sk-ant-api03-..." (Mac/Linux)

  # Run
  python expand_api.py

  # Options
  python expand_api.py --papers-per-species 10     # default 5
  python expand_api.py --no-llm                    # skip LLM extraction (only fetch from OpenAlex)
  python expand_api.py --only-missing              # only species without papers
  python expand_api.py --limit 20                  # process only first 20 species (testing)
"""
from __future__ import annotations
import os, re, json, time, sys, argparse
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import quote
from urllib.error import HTTPError, URLError

PROJ = Path(__file__).parent
OUT = PROJ / 'outputs'
EMAIL = "antorr91@example.com"  # for OpenAlex polite pool (change to your email)

# ── ARGUMENTS ──────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument('--papers-per-species', type=int, default=5,
                    help='Max papers to fetch per species from OpenAlex (default 5)')
parser.add_argument('--no-llm', action='store_true',
                    help='Skip LLM claim extraction (only fetch & save papers)')
parser.add_argument('--only-missing', action='store_true',
                    help='Only process species with no current papers')
parser.add_argument('--limit', type=int, default=None,
                    help='Process only first N species (for testing)')
parser.add_argument('--cache-dir', type=str, default='data/cache/openalex',
                    help='Where to cache OpenAlex responses')
args = parser.parse_args()

CACHE = PROJ / args.cache_dir
CACHE.mkdir(parents=True, exist_ok=True)

USE_LLM = not args.no_llm
if USE_LLM:
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        print("⚠ ANTHROPIC_API_KEY not set in environment. Running with --no-llm (only fetching papers).")
        USE_LLM = False
    else:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            print(f"✓ Anthropic API key loaded")
        except ImportError:
            print("⚠ anthropic package not installed. Run: pip install anthropic")
            print("  Falling back to --no-llm mode")
            USE_LLM = False

# ── HELPERS ────────────────────────────────────────────────────────────────
def fetch_url(url, timeout=30, retries=3):
    """Fetch URL with polite headers."""
    req = Request(url, headers={
        'User-Agent': f'Zoe.Logos-Graph/1.0 (mailto:{EMAIL})',
        'Accept': 'application/json',
    })
    for attempt in range(retries):
        try:
            with urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except (HTTPError, URLError) as e:
            if attempt < retries - 1:
                wait = 2 ** attempt
                print(f"    retry {attempt+1}/{retries} after {wait}s ({e})")
                time.sleep(wait)
            else:
                raise

def abstract_from_inverted(inv_idx):
    """Reconstruct abstract text from OpenAlex inverted index."""
    if not inv_idx: return ""
    word_positions = []
    for word, positions in inv_idx.items():
        for p in positions:
            word_positions.append((p, word))
    word_positions.sort()
    return ' '.join(w for _, w in word_positions)

def search_openalex(query, per_page=10):
    """Search OpenAlex for papers matching query."""
    cache_key = re.sub(r'[^a-z0-9]+', '_', query.lower())[:80]
    cache_f = CACHE / f"{cache_key}_n{per_page}.json"
    if cache_f.exists():
        return json.loads(cache_f.read_text())

    url = (f"https://api.openalex.org/works?"
           f"search={quote(query)}&per-page={per_page}"
           f"&select=id,title,doi,publication_year,primary_location,abstract_inverted_index,concepts,cited_by_count"
           f"&mailto={EMAIL}")
    try:
        data = fetch_url(url)
        cache_f.write_text(json.dumps(data))
        return data
    except Exception as e:
        print(f"    OpenAlex error: {e}")
        return {'results': []}

def llm_extract_claim(abstract, species_name):
    """Use Anthropic API to extract structured claim from abstract."""
    if not USE_LLM or not abstract: return None

    prompt = f"""Read this scientific abstract about {species_name} and extract a single key finding (1-2 sentences) about animal communication, signal function, vocal behaviour, or acoustic ecology. Be specific and factual.

Abstract:
{abstract[:3000]}

Output ONLY the finding sentence(s), nothing else. No introduction, no quotes."""

    try:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        return msg.content[0].text.strip()
    except Exception as e:
        print(f"    LLM error: {e}")
        return None

# ── LOAD EXISTING DATA ─────────────────────────────────────────────────────
print(f"Loading existing data...")
html_path = OUT / 'species_explorer.html'
html = html_path.read_text(encoding='utf-8')
m = re.search(r'const EMBEDDED_DB = (\[.*?\]);', html, re.DOTALL)
SPECIES = json.loads(m.group(1))
print(f"  Loaded {len(SPECIES)} species, {sum(len(s.get('papers',[])) for s in SPECIES)} papers")

# Filter species to process
to_process = list(SPECIES)
if args.only_missing:
    to_process = [s for s in to_process if not s.get('papers')]
    print(f"  Processing {len(to_process)} species without papers")
if args.limit:
    to_process = to_process[:args.limit]
    print(f"  Limited to first {len(to_process)} species")

# ── PROCESS ────────────────────────────────────────────────────────────────
added_papers = 0
errors = 0

for i, sp in enumerate(to_process, 1):
    sci = sp['sci']
    en = sp.get('en','')
    print(f"\n[{i}/{len(to_process)}] {sci} ({en})")

    existing_dois = {p.get('doi','').lower() for p in sp.get('papers',[]) if p.get('doi')}

    # Search OpenAlex for papers about this species and communication
    queries = [
        f'"{sci}" vocal communication',
        f'"{sci}" acoustic',
        f'"{sci}" call alarm',
    ]

    found_papers = []
    seen_dois = set(existing_dois)

    for q in queries:
        if len(found_papers) >= args.papers_per_species: break
        print(f"  → search: {q}")
        try:
            data = search_openalex(q, per_page=10)
            for w in data.get('results', []):
                doi = (w.get('doi') or '').replace('https://doi.org/','').lower()
                if not doi or doi in seen_dois: continue
                seen_dois.add(doi)
                title = w.get('title') or ''
                year = w.get('publication_year', 0)
                if year < 1950: continue
                venue = ((w.get('primary_location') or {}).get('source') or {}).get('display_name','')[:80]
                abstract = abstract_from_inverted(w.get('abstract_inverted_index'))
                cited = w.get('cited_by_count', 0)

                found_papers.append({
                    'title': title,
                    'year': year,
                    'doi': doi,
                    'journal': venue,
                    'url': f"https://doi.org/{doi}",
                    'abstract': abstract,
                    'cited_by': cited,
                })
                if len(found_papers) >= args.papers_per_species: break
        except Exception as e:
            print(f"    error: {e}")
            errors += 1
            continue
        time.sleep(0.3)  # be polite to OpenAlex

    # Sort by citation count, take top N
    found_papers.sort(key=lambda p: -p.get('cited_by', 0))
    found_papers = found_papers[:args.papers_per_species]

    print(f"  ✓ {len(found_papers)} new papers found")

    # Extract findings via LLM
    for p in found_papers:
        if USE_LLM and p.get('abstract'):
            print(f"  → LLM extracting: {p['title'][:60]}...")
            finding = llm_extract_claim(p['abstract'], sci)
            p['outcome'] = finding or p['abstract'][:200] + '...'
            time.sleep(0.2)
        else:
            p['outcome'] = (p.get('abstract') or '')[:250] + ('...' if p.get('abstract') else '')
        # Remove abstract from final saved data (too large)
        p.pop('abstract', None)
        p.pop('cited_by', None)
        p['open_access'] = 1
        sp.setdefault('papers', []).append(p)
        added_papers += 1

    # Save incrementally every 10 species (in case of interruption)
    if i % 10 == 0:
        print(f"\n💾 Saving checkpoint... ({added_papers} papers added so far)")
        new_db_json = json.dumps(SPECIES, ensure_ascii=False, separators=(',',':'))
        new_html = re.sub(r'const EMBEDDED_DB = \[.*?\];',
                          f'const EMBEDDED_DB = {new_db_json};',
                          html, flags=re.DOTALL)
        html_path.write_text(new_html, encoding='utf-8')

# ── FINAL SAVE ─────────────────────────────────────────────────────────────
print(f"\n💾 Final save...")
new_db_json = json.dumps(SPECIES, ensure_ascii=False, separators=(',',':'))
new_html = re.sub(r'const EMBEDDED_DB = \[.*?\];',
                  f'const EMBEDDED_DB = {new_db_json};',
                  html, flags=re.DOTALL)
html_path.write_text(new_html, encoding='utf-8')

# Update other HTML files
for fname in ['graph_explorer.html', 'compare.html']:
    fpath = OUT / fname
    if fpath.exists():
        content = fpath.read_text(encoding='utf-8')
        new_content = re.sub(r'const (THEME_DB|DB) = \[.*?\];',
                             lambda mat: f"const {mat.group(1)} = {new_db_json};",
                             content, count=1, flags=re.DOTALL)
        fpath.write_text(new_content, encoding='utf-8')

total_papers = sum(len(s.get('papers',[])) for s in SPECIES)
print(f"\n✓ DONE")
print(f"  Species: {len(SPECIES)}")
print(f"  Total papers: {total_papers} (+{added_papers} new)")
print(f"  Errors: {errors}")
print(f"\n  Now re-run literature.html generation via expand_curated.py to refresh themes view.")
print(f"  Or just re-open the site — species_explorer.html is updated.")
