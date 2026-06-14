#!/usr/bin/env python3
"""
seed_species.py - Zoe.Logos-Graph

Insert the new species from species_master.csv into the atlas (species_explorer.html
EMBEDDED_DB). Each new species gets its basic taxonomy (class/order/family), common
name and Wikipedia title, and EMPTY curated fields (themes, learning, functions,
frequency, semiotic, papers, audio) ready to be filled by the fetchers and by you.

Existing species are never touched. Uses the robust embedded_db reader/writer.

USAGE
  python seed_species.py --dry-run        # show how many would be added
  python seed_species.py                   # write into species_explorer.html (backup first)
  python seed_species.py --csv species_master.csv --html outputs/species_explorer.html
"""
import csv, argparse, shutil, datetime
from pathlib import Path
import embedded_db as edb

ap = argparse.ArgumentParser()
ap.add_argument('--csv', default='species_master.csv')
ap.add_argument('--html', default='outputs/species_explorer.html')
ap.add_argument('--dry-run', action='store_true')
args = ap.parse_args()


def blank_species(row):
    sci = (row.get('sci') or '').strip()
    return {
        'en': (row.get('en') or '').strip(),
        'sci': sci,
        'class_': (row.get('class_') or '').strip(),
        'order_': (row.get('order_') or '').strip(),
        'family': (row.get('family') or '').strip(),
        'de': '', 'es': '', 'fr': '', 'it': '',
        'themes': [],
        'learning': 'unknown',
        'fn': [], 'voc': [], 'ctx': [],
        'freq': '',
        'semiotic': 'unknown',
        'wiki': (row.get('wiki') or sci.replace(' ', '_')).strip(),
        'papers': [],
        'xc': [],
        'recordings': [],
    }


def main():
    html_path = Path(args.html)
    html = html_path.read_text(encoding='utf-8')
    species, eq, end = edb.load(html)
    have = {(s.get('sci') or '').lower() for s in species}
    print('Atlas currently has %d species.' % len(species))

    added = 0
    with open(args.csv, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            sci = (row.get('sci') or '').strip()
            if not sci or sci.lower() in have:
                continue
            species.append(blank_species(row))
            have.add(sci.lower())
            added += 1

    print('New species to add: %d  ->  total would be %d' % (added, len(species)))
    if args.dry_run:
        print('DRY RUN: nothing written.'); return
    if added == 0:
        print('Nothing to add.'); return

    bk = '%s.backup-%s' % (args.html, datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
    shutil.copyfile(args.html, bk)
    html_path.write_text(edb.write(html, species, eq, end), encoding='utf-8')
    print('Backup: %s' % bk)
    print('Wrote %s (%d species).' % (args.html, len(species)))


if __name__ == '__main__':
    main()
