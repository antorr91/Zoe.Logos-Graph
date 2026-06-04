#!/usr/bin/env python3
"""
fetch_audio.py - Pre-fetches Xeno-Canto recordings (API v3) and embeds them
into species_explorer.html. Audio then loads instantly, no browser API/CORS.

SETUP (one time):
  1. Register free at https://xeno-canto.org/  + verify email
  2. Account page -> copy your API key
  3. Set it:
     Windows:   set XC_API_KEY=your-key-here
     Mac/Linux: export XC_API_KEY=your-key-here

USAGE:
  python fetch_audio.py                  # all species, 6 recordings each
  python fetch_audio.py --per-species 10
  python fetch_audio.py --limit 20       # test first 20
  python fetch_audio.py --only-birds     # only Aves (best XC coverage)
  python fetch_audio.py --debug --limit 3   # troubleshoot query format
"""
from __future__ import annotations
import os, re, json, time, argparse
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import quote
from urllib.error import HTTPError, URLError

PROJ = Path(__file__).parent
OUT = PROJ / 'outputs'
CACHE = PROJ / 'data' / 'cache' / 'xenocanto'
CACHE.mkdir(parents=True, exist_ok=True)

parser = argparse.ArgumentParser()
parser.add_argument('--per-species', type=int, default=6)
parser.add_argument('--limit', type=int, default=None)
parser.add_argument('--only-birds', action='store_true')
parser.add_argument('--debug', action='store_true')
parser.add_argument('--refresh', action='store_true',
                    help='ignore cache and re-fetch (use after raising --per-species or to clean duplicates)')
parser.add_argument('--min-quality', default='E',
                    help='lowest Xeno-Canto quality to keep: A (best) .. E (default E = keep all)')
args = parser.parse_args()

QRANK = {'A': 0, 'B': 1, 'C': 2, 'D': 3, 'E': 4}
def qk(rec):
    q = (rec.get('q', '') or '').strip().upper()[:1]
    return QRANK.get(q, 5)   # unscored -> 5 (kept, but ranked last)
SEEN_IDS = set()   # cross-species: never reuse the same recording on two species

API_KEY = os.environ.get('XC_API_KEY')
if not API_KEY:
    print("=" * 60)
    print("XC_API_KEY not set. Running LINK-ONLY (no audio embedded).")
    print("=" * 60)

def fetch_url(url, timeout=30, retries=3):
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0 Zoe.Logos-Graph/1.0'})
    last_err = None
    for attempt in range(retries):
        try:
            with urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except HTTPError as e:
            try:
                body = e.read().decode('utf-8', 'ignore')[:300]
            except Exception:
                body = ''
            last_err = "HTTP %s: %s" % (e.code, body)
            if e.code == 400:
                if args.debug:
                    print("      [debug] " + last_err)
                return None
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
        except URLError as e:
            last_err = str(e)
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    if args.debug and last_err:
        print("      [debug] " + last_err)
    return None

def search_xc(sci_name):
    cache_f = CACHE / (re.sub(r'[^a-z0-9]+', '_', sci_name.lower()) + '.json')
    if cache_f.exists() and not args.refresh:
        return json.loads(cache_f.read_text())
    if not API_KEY:
        return []

    parts = sci_name.split()
    genus = parts[0]
    species = parts[1] if len(parts) > 1 else ''

    # v3 syntax: space-separated tags, whole query URL-encoded
    query = "gen:" + genus
    if species:
        query += " sp:" + species

    url = "https://xeno-canto.org/api/3/recordings?query=%s&key=%s" % (quote(query), API_KEY)
    if args.debug:
        print("      [debug] " + url.replace(API_KEY, "KEY"))

    data = fetch_url(url)
    if not data:
        cache_f.write_text('[]')
        return []

    recordings = data.get('recordings', []) or []
    result = []
    seen_id = set()
    seen_sig = set()
    for r in recordings:                      # process the WHOLE pool, not just the first N
        f = r.get('file', '')
        if not f:
            continue
        rid = r.get('id', '')
        if rid and rid in seen_id:            # exact duplicate id
            continue
        # content signature: same recordist + date + type + length + country => re-upload / same take
        sig = ((r.get('rec', '') or '').strip().lower(), (r.get('date', '') or '').strip(),
               (r.get('type', '') or '').strip().lower(), (r.get('length', '') or '').strip(),
               (r.get('cnt', '') or '').strip())
        if any(sig) and sig in seen_sig:
            continue
        seen_id.add(rid)
        seen_sig.add(sig)

        if f.startswith('//'):
            f = 'https:' + f
        sono = r.get('sono', {})
        sono_url = ''
        if isinstance(sono, dict):
            sono_url = sono.get('med') or sono.get('small') or ''
            if sono_url.startswith('//'):
                sono_url = 'https:' + sono_url
        rurl = r.get('url', '')
        if rurl.startswith('//'):
            rurl = 'https:' + rurl
        elif not rurl.startswith('http'):
            rurl = "https://xeno-canto.org/%s" % rid
        result.append({
            'id': rid,
            'type': (r.get('type', 'call') or 'call').lower(),
            'q': (r.get('q', '') or '').strip(),
            'loc': r.get('loc', ''),
            'cnt': r.get('cnt', ''),
            'rec': r.get('rec', ''),
            'date': r.get('date', ''),
            'duration': r.get('length', ''),
            'audio': f,
            'sono': sono_url,
            'url': rurl,
            'license': 'CC licensed',
        })

    # best quality first (A..E, unscored last)
    result.sort(key=qk)
    # optional quality floor
    floor = QRANK.get((args.min_quality or 'E').strip().upper()[:1], 4)
    result = [x for x in result if qk(x) <= floor or qk(x) == 5]

    cache_f.write_text(json.dumps(result))   # cache the FULL deduped pool
    return result

print("Loading species data...")
html_path = OUT / 'species_explorer.html'
html = html_path.read_text(encoding='utf-8')
m = re.search(r'const EMBEDDED_DB = (\[.*?\]);', html, re.DOTALL)
SPECIES = json.loads(m.group(1))
print("  %d species loaded" % len(SPECIES))

to_process = SPECIES
if args.only_birds:
    to_process = [s for s in SPECIES if s.get('class_') == 'Aves']
if args.limit:
    to_process = to_process[:args.limit]
print("  Processing %d species\n" % len(to_process))

total_recordings = 0
hits = 0
for i, sp in enumerate(to_process, 1):
    sci = sp['sci']
    cls = sp.get('class_', '')
    print("[%d/%d] %s (%s)" % (i, len(to_process), sci, cls), end=' ')
    recs = search_xc(sci)
    # drop any recording already used by another species, then keep the best N
    recs = [r for r in recs if not (r.get('id') and r['id'] in SEEN_IDS)][:args.per_species]
    for r in recs:
        if r.get('id'):
            SEEN_IDS.add(r['id'])
    if recs:
        sp['recordings'] = recs
        total_recordings += len(recs)
        hits += 1
        print("-> %d recordings" % len(recs))
    else:
        print("-> none (external links will show)")
    if API_KEY:
        time.sleep(0.4)
    if i % 20 == 0:
        nj = json.dumps(SPECIES, ensure_ascii=False, separators=(',', ':'))
        html = re.sub(r'const EMBEDDED_DB = \[.*?\];', 'const EMBEDDED_DB = %s;' % nj, html, flags=re.DOTALL)
        html_path.write_text(html, encoding='utf-8')
        print("  [checkpoint: %d recordings from %d species]" % (total_recordings, hits))

print("\nSaving...")
nj = json.dumps(SPECIES, ensure_ascii=False, separators=(',', ':'))
html = re.sub(r'const EMBEDDED_DB = \[.*?\];', 'const EMBEDDED_DB = %s;' % nj, html, flags=re.DOTALL)
html_path.write_text(html, encoding='utf-8')

# Re-embed only where the media tab needs it. compare.html now uses a custom
# DB (with 'wiki' for images), so we must NOT overwrite it here.
for fname in ['graph_explorer.html']:
    fp = OUT / fname
    if fp.exists():
        c = fp.read_text(encoding='utf-8')
        c = re.sub(r'const (THEME_DB|DB) = \[.*?\];', lambda mt: "const %s = %s;" % (mt.group(1), nj), c, count=1, flags=re.DOTALL)
        fp.write_text(c, encoding='utf-8')

print("DONE: %d recordings embedded from %d/%d species." % (total_recordings, hits, len(to_process)))
if hits == 0 and API_KEY:
    print("\n0 hits with a key set. Re-run with: python fetch_audio.py --debug --limit 3")
    print("and paste the [debug] lines so we can fix the query format.")