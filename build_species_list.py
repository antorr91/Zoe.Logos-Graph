#!/usr/bin/env python3
"""
build_species_list.py - Zoe.Logos-Graph

Propose a balanced list of ~1000 species for the atlas, grounded in real data:
it keeps the species you already have, then fills up from GBIF species that have
SOUND recordings (so every added species has communication-relevant material),
balanced across zoological classes so it is not 90% birds.

No API key needed (GBIF public API).

OUTPUT: species_master.csv  (sci, en, class_, order_, family, wiki, source)
  source = 'existing'  -> already in your atlas (taxonomy kept as-is)
           'gbif'       -> newly proposed

USAGE
  python build_species_list.py --target 1000 --dry-run      # preview counts
  python build_species_list.py --target 1000                # write species_master.csv
  python build_species_list.py --limit 50                   # quick test (50 GBIF lookups)
"""
import json, csv, time, argparse, re
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError

PROJ = Path(__file__).parent
ap = argparse.ArgumentParser()
ap.add_argument('--target', type=int, default=1000, help='total species wanted (existing + new)')
ap.add_argument('--out', default='species_master.csv')
ap.add_argument('--species-html', default=str(PROJ / 'outputs' / 'species_explorer.html'),
                help='used to keep the species you already have, with their taxonomy')
ap.add_argument('--facet-limit', type=int, default=4000, help='how many GBIF sound species to consider')
ap.add_argument('--limit', type=int, default=None, help='cap GBIF species lookups (testing)')
ap.add_argument('--dry-run', action='store_true', help='print the composition, write nothing')
# per-class caps so the list stays balanced; tune freely
ap.add_argument('--caps', default='Aves:340,Mammalia:260,Amphibia:120,Actinopterygii:130,Insecta:90,Reptilia:35,Cephalopoda:15,Other:10')
args = ap.parse_args()

CAPS = {}
for part in args.caps.split(','):
    k, v = part.split(':'); CAPS[k.strip()] = int(v)

UA = {'User-Agent': 'Zoe.Logos-Graph/1.0 (academic atlas of animal communication; mailto:a.m.c.torrisi@qmul.ac.uk)'}


def http_json(url):
    try:
        with urlopen(Request(url, headers=UA), timeout=40) as r:
            return json.loads(r.read())
    except (HTTPError, URLError, ValueError, TimeoutError) as e:
        print('   [warn]', e); return None


def class_bucket(cls):
    return cls if cls in CAPS else 'Other'


# ---- 1) keep the species already in the atlas (with their taxonomy) ----
def load_existing():
    out = []
    p = Path(args.species_html)
    if not p.exists():
        print('note: %s not found, starting from scratch' % args.species_html); return out
    h = p.read_text(encoding='utf-8', errors='replace')
    i = h.find('const EMBEDDED_DB'); eq = h.find('[', i)
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
                if depth == 0: end = j; break

    def js2j(s):
        o = []; k = 0; n = len(s)
        while k < n:
            ch = s[k]
            if ch == '\\' and k + 1 < n:
                nx = s[k + 1]
                if nx in '"\\/bfnrt': o.append(ch); o.append(nx); k += 2; continue
                if nx == 'u' and re.match(r'[0-9a-fA-F]{4}', s[k + 2:k + 6]): o.append('\\u'); k += 2; continue
                o.append('\\\\'); k += 1; continue
            o.append(ch); k += 1
        return ''.join(o)
    for d in json.loads(js2j(h[eq:end + 1]), strict=False):
        out.append({'sci': d.get('sci', ''), 'en': d.get('en', ''), 'class_': d.get('class_', ''),
                    'order_': d.get('order_', ''), 'family': d.get('family', ''),
                    'wiki': d.get('wiki', ''), 'source': 'existing'})
    return out


# ---- 2) GBIF species that have sound recordings, by descending sound count ----
def gbif_sound_species():
    url = 'https://api.gbif.org/v1/occurrence/search?' + urlencode(
        {'mediaType': 'Sound', 'facet': 'speciesKey', 'facetLimit': args.facet_limit, 'limit': 0})
    data = http_json(url)
    if not data or not data.get('facets'):
        return []
    return [c['name'] for c in data['facets'][0]['counts']]   # speciesKeys, most-recorded first


def gbif_species(key):
    d = http_json('https://api.gbif.org/v1/species/%s' % key)
    if not d or d.get('rank') != 'SPECIES' or d.get('kingdom') != 'Animalia':
        return None
    sci = d.get('canonicalName') or d.get('scientificName', '')
    if not sci:
        return None
    return {'sci': sci, 'en': (d.get('vernacularName') or ''), 'class_': d.get('class', ''),
            'order_': d.get('order', ''), 'family': d.get('family', ''),
            'wiki': sci.replace(' ', '_'), 'source': 'gbif'}


def main():
    existing = load_existing()
    have = {e['sci'].lower() for e in existing}
    counts = {}
    for e in existing:
        counts[class_bucket(e['class_'])] = counts.get(class_bucket(e['class_']), 0) + 1
    print('Existing species kept: %d' % len(existing))
    print('  by class:', {k: counts.get(k, 0) for k in CAPS})

    chosen = list(existing)
    keys = gbif_sound_species()
    print('GBIF sound species available: %d' % len(keys))
    if args.limit:
        keys = keys[:args.limit]

    looked = 0
    for key in keys:
        if len(chosen) >= args.target:
            break
        sp = gbif_species(key); looked += 1
        time.sleep(0.05)
        if not sp:
            continue
        if sp['sci'].lower() in have:
            continue
        b = class_bucket(sp['class_'])
        if counts.get(b, 0) >= CAPS.get(b, 0):
            continue          # class already full, keep the balance
        chosen.append(sp); have.add(sp['sci'].lower())
        counts[b] = counts.get(b, 0) + 1
        if looked % 100 == 0:
            print('  ... looked %d, chosen %d' % (looked, len(chosen)))

    print('\nTotal species: %d  (existing %d + new %d)'
          % (len(chosen), len(existing), len(chosen) - len(existing)))
    print('Final composition:', {k: counts.get(k, 0) for k in CAPS})

    if args.dry_run:
        print('DRY RUN: nothing written.'); return
    with open(args.out, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['sci', 'en', 'class_', 'order_', 'family', 'wiki', 'source'])
        w.writeheader()
        for sp in chosen:
            w.writerow(sp)
    print('Wrote %s' % args.out)


if __name__ == '__main__':
    main()