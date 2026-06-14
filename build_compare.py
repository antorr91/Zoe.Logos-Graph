#!/usr/bin/env python3
"""
build_compare.py - Zoe.Logos-Graph

Regenerate the `const DB = [...]` block inside compare.html from the current
species_explorer.html, so the compare page shows ALL species (not just the
original set) and stays in sync.

The compare cards only need the traits, not the full papers, so this writes a
SLIM DB: per species it keeps sci/en/it/es/fr/de/class_/order_/family/wiki/
themes/learning/freq/semiotic/voc/ctx/fn plus np = number of papers (the count
shown on the card). Dropping the papers arrays makes compare.html much lighter.

Run from the PROJECT ROOT (needs embedded_db.py there), NOT from outputs/.

  python build_compare.py
  python build_compare.py --species outputs/species_explorer.html --compare outputs/compare.html
"""
import json, shutil, datetime, argparse
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument('--species', default='outputs/species_explorer.html')
ap.add_argument('--compare', default='outputs/compare.html')
args = ap.parse_args()

LIST_FIELDS = {'themes', 'voc', 'ctx', 'fn'}
FIELDS = ['sci', 'en', 'it', 'es', 'fr', 'de', 'class_', 'order_', 'family',
          'wiki', 'themes', 'learning', 'freq', 'semiotic', 'voc', 'ctx', 'fn']


def main():
    import embedded_db as edb

    sp_html = Path(args.species).read_text(encoding='utf-8')
    species, _eq, _end = edb.load(sp_html)
    print('species_explorer: %d species' % len(species))

    slim = []
    for s in species:
        rec = {}
        for k in FIELDS:
            v = s.get(k)
            if v is None:
                v = [] if k in LIST_FIELDS else ''
            rec[k] = v
        papers = s.get('papers')
        rec['np'] = len(papers) if isinstance(papers, list) else 0
        slim.append(rec)

    arr = json.dumps(slim, ensure_ascii=True, separators=(',', ':')).replace('</', '<\\/')

    # read compare.html preserving CRLF
    with open(args.compare, encoding='utf-8', newline='') as _f:
        comp = _f.read()
    i = comp.find('const DB = [')
    j = comp.find('const THEME')
    if i < 0 or j < 0 or j < i:
        raise SystemExit('Could not locate "const DB = [" and "const THEME" in %s' % args.compare)

    new = comp[:i] + 'const DB = ' + arr + ';\r\n' + comp[j:]

    bk = args.compare + '.backup-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    shutil.copyfile(args.compare, bk)
    with open(args.compare, 'w', encoding='utf-8', newline='') as f:
        f.write(new)

    total_np = sum(r['np'] for r in slim)
    print('wrote %s' % args.compare)
    print('  %d species, %d papers counted (np)' % (len(slim), total_np))
    print('  size: %.2f MB  (was %.2f MB)' % (len(new) / 1e6, len(comp) / 1e6))
    print('  backup: %s' % bk)


if __name__ == '__main__':
    main()
