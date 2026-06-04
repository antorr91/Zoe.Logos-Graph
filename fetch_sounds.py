#!/usr/bin/env python3
"""
fetch_sounds.py - Zoe.Logos-Graph
Add audio recordings to species from MULTIPLE sources, never publishing a duplicate.

Sources (no API key needed unless noted):
  inat   iNaturalist  (api.inaturalist.org)        - frogs, insects, reptiles, mammals, some fish
  gbif   GBIF         (api.gbif.org)               - aggregates Macaulay, FrogID, iNat, etc.
  csv    a local CSV you export from any dataset   - e.g. FishSounds (Borealis), Watkins (zip/parquet)
         CSV columns (header required, extra columns ignored):
           sci,audio_url,license,source,id,type
         only 'sci' and 'audio_url' are mandatory.

Xeno-Canto stays in fetch_audio.py (it needs the free key). This script MERGES new,
unique recordings into the existing ones, so run it alongside fetch_audio.py.

A shared registry (data/cache/audio_registry.json) remembers every published clip
(by source:id, by audio URL, and by a content signature) so the same recording is
never embedded twice -- not within a source, not across sources, not across runs.

USAGE
  python fetch_sounds.py --sources inat            # default, iNaturalist only
  python fetch_sounds.py --sources inat,gbif       # add GBIF too
  python fetch_sounds.py --sources csv --csv fishsounds.csv
  python fetch_sounds.py --per-species 10 --only-class Amphibia
  python fetch_sounds.py --dry-run                 # report, write nothing
"""
import os, re, json, time, argparse, urllib.parse
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

PROJ = Path(__file__).parent
OUT = PROJ / 'outputs'
CACHE = PROJ / 'data' / 'cache'
CACHE.mkdir(parents=True, exist_ok=True)

ap = argparse.ArgumentParser()
ap.add_argument('--sources', default='inat', help='comma list: inat,gbif,csv')
ap.add_argument('--csv', default='', help='local CSV (sci,audio_url,license,source,id,type) for FishSounds/Watkins/etc.')
ap.add_argument('--per-species', type=int, default=8, help='target TOTAL recordings per species (existing + new)')
ap.add_argument('--limit', type=int, default=None, help='process only first N species (testing)')
ap.add_argument('--only-class', default='', help='restrict to one class, e.g. Amphibia, Mammalia, Actinopterygii')
ap.add_argument('--licenses', default='cc0,cc-by,cc-by-nc,cc-by-sa,cc-by-nc-sa',
                help='allowed licence codes (comma list); others are skipped')
ap.add_argument('--registry', default=str(CACHE / 'audio_registry.json'))
ap.add_argument('--html', default=str(OUT / 'species_explorer.html'))
ap.add_argument('--dry-run', action='store_true')
args = ap.parse_args()

ALLOWED = {x.strip().lower() for x in args.licenses.split(',') if x.strip()}
UA = {'User-Agent': 'Zoe.Logos-Graph/1.0 (academic atlas of animal communication)'}


def http_json(url):
    try:
        req = Request(url, headers=UA)
        with urlopen(req, timeout=40) as r:
            return json.loads(r.read())
    except (HTTPError, URLError, ValueError, TimeoutError) as e:
        print('      [warn] %s' % e)
        return None


def norm_license(s):
    s = (s or '').lower()
    if 'publicdomain' in s or 'cc0' in s or s == 'zero':
        return 'cc0'
    if 'by-nc-sa' in s: return 'cc-by-nc-sa'
    if 'by-nc-nd' in s: return 'cc-by-nc-nd'
    if 'by-nc' in s:    return 'cc-by-nc'
    if 'by-sa' in s:    return 'cc-by-sa'
    if 'by-nd' in s:    return 'cc-by-nd'
    if 'by' in s:       return 'cc-by'
    return s.strip()


def norm_url(u):
    u = (u or '').split('?')[0].strip().lower()
    if u.startswith('//'):
        u = 'https:' + u
    return u


def sig_of(rec):
    """content signature to catch the same clip cross-listed in two archives"""
    return '|'.join([
        (rec.get('rec', '') or '').strip().lower(),
        (rec.get('date', '') or '').strip(),
        (rec.get('duration', '') or '').strip(),
        (rec.get('type', '') or '').strip().lower(),
        norm_url(rec.get('audio', '')),
    ])


# ---------- registry (shared dedup memory) ----------
def load_registry():
    p = Path(args.registry)
    if p.exists():
        try:
            d = json.loads(p.read_text())
            return set(d.get('keys', [])), set(d.get('urls', [])), set(d.get('sigs', []))
        except Exception:
            pass
    return set(), set(), set()


def save_registry(keys, urls, sigs):
    if args.dry_run:
        return
    Path(args.registry).write_text(json.dumps(
        {'keys': sorted(keys), 'urls': sorted(urls), 'sigs': sorted(sigs)}))


KEYS, URLS, SIGS = load_registry()


def is_dup(rec):
    k = '%s:%s' % (rec.get('source', ''), rec.get('id', ''))
    if rec.get('id') and k in KEYS: return True
    if norm_url(rec.get('audio', '')) in URLS: return True
    if sig_of(rec) in SIGS: return True
    return False


def register(rec):
    if rec.get('id'):
        KEYS.add('%s:%s' % (rec.get('source', ''), rec.get('id', '')))
    URLS.add(norm_url(rec.get('audio', '')))
    SIGS.add(sig_of(rec))


# ---------- source: iNaturalist ----------
def fetch_inat(sci, want):
    url = ('https://api.inaturalist.org/v1/observations?'
           + urllib.parse.urlencode({
               'taxon_name': sci, 'sounds': 'true', 'quality_grade': 'research',
               'per_page': 60, 'order_by': 'votes', 'order': 'desc'}))
    data = http_json(url)
    out = []
    if not data:
        return out
    for obs in data.get('results', []):
        for s in (obs.get('sounds') or []):
            fu = s.get('file_url') or ''
            if not fu:
                continue
            out.append({
                'source': 'inat', 'id': str(s.get('id') or obs.get('id') or ''),
                'type': (obs.get('description') and 'call') or 'call',
                'q': '', 'rec': (obs.get('user') or {}).get('login', ''),
                'date': obs.get('observed_on') or '', 'cnt': obs.get('place_guess', '') or '',
                'duration': '', 'audio': fu, 'sono': '',
                'url': obs.get('uri') or ('https://www.inaturalist.org/observations/%s' % obs.get('id')),
                'license': norm_license(s.get('license_code')),
                'attribution': s.get('attribution', '') or '',
            })
    return out


# ---------- source: GBIF ----------
def fetch_gbif(sci, want):
    url = ('https://api.gbif.org/v1/occurrence/search?'
           + urllib.parse.urlencode({'scientificName': sci, 'mediaType': 'Sound', 'limit': 60}))
    data = http_json(url)
    out = []
    if not data:
        return out
    for occ in data.get('results', []):
        for m in (occ.get('media') or []):
            if (m.get('type') or '').lower() != 'sound':
                continue
            ident = m.get('identifier') or ''
            if not ident:
                continue
            out.append({
                'source': 'gbif', 'id': str(occ.get('key') or m.get('identifier') or ''),
                'type': 'call', 'q': '',
                'rec': m.get('rightsHolder') or occ.get('recordedBy') or m.get('creator') or '',
                'date': (occ.get('eventDate') or '')[:10], 'cnt': occ.get('country', '') or '',
                'duration': '', 'audio': ident, 'sono': '',
                'url': 'https://www.gbif.org/occurrence/%s' % occ.get('key', ''),
                'license': norm_license(m.get('license') or occ.get('license')),
                'attribution': m.get('publisher') or occ.get('datasetName') or '',
            })
    return out


# ---------- source: local CSV (FishSounds / Watkins / anything) ----------
def load_csv(path):
    import csv
    by = {}
    with open(path, encoding='utf-8', errors='replace', newline='') as f:
        for row in csv.DictReader(f):
            sci = (row.get('sci') or row.get('scientific_name') or '').strip()
            audio = (row.get('audio_url') or row.get('url') or row.get('audio') or '').strip()
            if not sci or not audio:
                continue
            by.setdefault(sci, []).append({
                'source': (row.get('source') or 'csv').strip(),
                'id': (row.get('id') or '').strip(),
                'type': (row.get('type') or 'call').strip().lower(),
                'q': '', 'rec': (row.get('rec') or row.get('recordist') or '').strip(),
                'date': (row.get('date') or '').strip(), 'cnt': (row.get('country') or '').strip(),
                'duration': (row.get('duration') or '').strip(),
                'audio': audio, 'sono': '',
                'url': (row.get('page') or audio).strip(),
                'license': norm_license(row.get('license')),
                'attribution': (row.get('attribution') or '').strip(),
            })
    return by


# ---------- main ----------
print('Loading species from %s ...' % args.html)
html_path = Path(args.html)
html = html_path.read_text(encoding='utf-8')

def extract_db(h):
    key = 'const EMBEDDED_DB'
    i = h.find(key)
    if i < 0:
        raise SystemExit('EMBEDDED_DB not found in ' + args.html)
    eq = h.find('[', i)
    depth = 0; instr = False; esc = False; end = None
    for j in range(eq, len(h)):
        c = h[j]
        if instr:
            if esc: esc = False
            elif c == '\\': esc = True
            elif c == '"': instr = False
        else:
            if c == '"': instr = True
            elif c == '[': depth += 1
            elif c == ']':
                depth -= 1
                if depth == 0:
                    end = j; break
    return eq, end

def js_to_json(s):
    """Make a JS array literal safe for strict json: fix escapes JSON rejects but JS allows,
    without corrupting legitimate \\\\ pairs or valid \\uXXXX."""
    out = []
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c == '\\' and i + 1 < n:
            nxt = s[i + 1]
            if nxt in '"\\/bfnrt':
                out.append(c); out.append(nxt); i += 2; continue
            if nxt == 'u' and re.match(r'[0-9a-fA-F]{4}', s[i + 2:i + 6]):
                out.append('\\u'); i += 2; continue
            out.append('\\\\'); i += 1; continue   # stray/invalid escape -> escape the backslash
        out.append(c); i += 1
    return ''.join(out)

DB_EQ, DB_END = extract_db(html)
SPECIES = json.loads(js_to_json(html[DB_EQ:DB_END + 1]), strict=False)
print('  %d species' % len(SPECIES))

# 1) seed the registry with everything already embedded (so we never re-add it)
for sp in SPECIES:
    for r in (sp.get('recordings') or []):
        r.setdefault('source', r.get('source', 'xc'))
        register(r)

sources = [s.strip() for s in args.sources.split(',') if s.strip()]
csv_data = load_csv(args.csv) if (('csv' in sources) and args.csv) else {}

to_do = SPECIES
if args.only_class:
    to_do = [s for s in to_do if s.get('class_', '').lower() == args.only_class.lower()]
if args.limit:
    to_do = to_do[:args.limit]
print('  processing %d species from sources: %s\n' % (len(to_do), ', '.join(sources)))

added_total = 0
skipped_dups = 0
species_touched = 0

for i, sp in enumerate(to_do, 1):
    sci = sp.get('sci', '')
    existing = sp.get('recordings') or []
    need = args.per_species - len(existing)
    print('[%d/%d] %s (have %d)' % (i, len(to_do), sci, len(existing)), end=' ')
    if need <= 0:
        print('-> full'); continue

    candidates = []
    for src in sources:
        if src == 'inat':
            candidates += fetch_inat(sci, need); time.sleep(0.7)
        elif src == 'gbif':
            candidates += fetch_gbif(sci, need); time.sleep(0.3)
        elif src == 'csv':
            candidates += csv_data.get(sci, [])

    fresh = []
    for r in candidates:
        if r.get('license') not in ALLOWED:
            continue
        if is_dup(r):
            skipped_dups += 1
            continue
        register(r)              # claim it immediately so later sources/species can't repeat it
        fresh.append(r)
        if len(fresh) >= need:
            break

    if fresh:
        sp['recordings'] = existing + fresh
        added_total += len(fresh)
        species_touched += 1
        print('-> +%d' % len(fresh))
    else:
        print('-> none new')

print('\nAdded %d recordings to %d species (skipped %d duplicates).'
      % (added_total, species_touched, skipped_dups))

if args.dry_run:
    print('DRY RUN: nothing written.')
else:
    nj = json.dumps(SPECIES, ensure_ascii=False, separators=(',', ':'))
    html = html[:DB_EQ] + nj + html[DB_END + 1:]
    html_path.write_text(html, encoding='utf-8')
    save_registry(KEYS, URLS, SIGS)
    print('Wrote %s and updated registry %s' % (args.html, args.registry))