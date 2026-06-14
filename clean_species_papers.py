#!/usr/bin/env python3
"""
clean_species_papers.py - Zoe.Logos-Graph

Reassign papers filed under the WRONG species inside species_explorer.html using
an EXACT 1-to-1 match of each atlas species' scientific binomial AND full English
common name. The species named in a paper's TITLE is treated as the real subject.

Fast: one precompiled regex for all species names.

Run from the PROJECT ROOT (needs embedded_db.py there), NOT from outputs/.

  python clean_species_papers.py            DRY RUN -> species_paper_review.csv
  python clean_species_papers.py --apply     move the 'move' rows (backup first)

CSV columns: action, comm, filed_under, move_to, matched_in, doi, year, title
  action: move | review-multi | review-none | keep
  comm:   yes/no  (is the paper about communication?) -> 'yes' review rows belong
          in General Literature by theme, 'no' ones are off-topic.
"""
import csv, re, argparse, shutil, datetime, collections
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument('--html', default='outputs/species_explorer.html')
ap.add_argument('--out', default='species_paper_review.csv')
ap.add_argument('--apply', action='store_true', help='write the moves (otherwise dry run)')
ap.add_argument('--title-only', action='store_true', help='match species in the title only')
args = ap.parse_args()

COMM = ['vocal', 'call', 'song', 'sing', 'acoustic', 'sound', 'signal', 'communicat',
        'alarm', 'echolocat', 'ultrason', 'infrasound', 'duet', 'syntax', 'referential',
        'bioacoustic', 'chorus', 'whistle', 'click', 'bark', 'roar', 'hiss', 'drumming',
        'stridulat', 'chirp', 'rumble', 'growl', 'hearing', 'auditory', 'repertoire',
        'playback', 'mimic', 'dialect', 'vocaliz', 'vocalis']

GENERIC = {'frog', 'toad', 'owl', 'bat', 'whale', 'finch', 'tit', 'crow', 'dove',
           'duck', 'goose', 'gull', 'tern', 'wren', 'lark', 'pipit', 'thrush',
           'sparrow', 'warbler', 'cricket', 'cicada', 'parrot', 'penguin', 'seal',
           'monkey', 'ape', 'deer', 'bird', 'fish', 'cuckoo', 'magpie', 'raven',
           'robin', 'starling', 'swallow', 'cod', 'goby', 'gecko'}


def lget(d, *names):
    if not isinstance(d, dict):
        return ''
    low = {k.lower(): v for k, v in d.items()}
    for n in names:
        v = low.get(n.lower())
        if v:
            return v
    return ''


def build_index(species):
    bino2sp, common2sp, dup = {}, {}, set()
    for rec in species:
        name = lget(rec, 'sci', 'scientific_name', 'name')
        if not name:
            continue
        p = name.lower().split()
        if len(p) >= 2:
            bino2sp[' '.join(p[:2])] = name
        cm = re.sub(r'\s+', ' ', (lget(rec, 'en', 'common', 'common_name') or '').lower().strip())
        if cm and (' ' in cm or len(cm) >= 7) and cm not in GENERIC:
            if cm in common2sp and common2sp[cm] != name:
                dup.add(cm)
            else:
                common2sp[cm] = name
    for cm in dup:
        common2sp.pop(cm, None)
    term2sp = {}
    for k, v in bino2sp.items():
        term2sp[k] = v
    for k, v in common2sp.items():
        term2sp.setdefault(k, v)
    terms = sorted(term2sp.keys(), key=len, reverse=True)   # longer first
    pat = re.compile(r'\b(?:' + '|'.join(re.escape(t) for t in terms) + r')\b') if terms else None
    return term2sp, pat


def species_in(text, term2sp, pat):
    if not pat or not text:
        return set()
    t = text.lower()
    return {term2sp[m.group(0)] for m in pat.finditer(t) if m.group(0) in term2sp}


def is_comm(text):
    t = text.lower()
    return any(k in t for k in COMM)


def audit(species):
    term2sp, pat = build_index(species)
    name2rec = {lget(r, 'sci', 'scientific_name', 'name'): r for r in species}
    rows = []
    plan = collections.defaultdict(list)
    for rec in species:
        filed = lget(rec, 'sci', 'scientific_name', 'name')
        papers = rec.get('papers') if isinstance(rec.get('papers'), list) else []
        for idx, paper in enumerate(papers):
            if not isinstance(paper, dict):
                continue
            title = str(lget(paper, 'title', 'ti'))
            abstract = str(lget(paper, 'abstract', 'a', 'ab', 'summary'))
            doi = lget(paper, 'doi', 'd', 'DOI')
            year = lget(paper, 'year', 'y', 'published') or ''
            comm = 'yes' if is_comm(title + ' ' + abstract) else 'no'
            in_title = species_in(title, term2sp, pat)
            in_abs = set() if args.title_only else species_in(abstract, term2sp, pat)
            hits = in_title if in_title else in_abs
            where = 'title' if in_title else ('abstract' if in_abs else '')
            base = {'comm': comm, 'filed_under': filed, 'matched_in': where,
                    'doi': doi, 'year': year, 'title': title[:140]}
            if filed in hits:
                rows.append(dict(action='keep', move_to='', **base))
                continue
            others = sorted(hits)
            if len(others) == 1:
                rows.append(dict(action='move', move_to=others[0], **base))
                plan[id(rec)].append((idx, others[0]))
            elif len(others) >= 2:
                rows.append(dict(action='review-multi', move_to=' | '.join(others[:4]), **base))
            else:
                rows.append(dict(action='review-none', move_to='', **base))
    return rows, plan, name2rec


def norm_doi(d):
    return (d or '').strip().lower().replace('https://doi.org/', '').replace('http://dx.doi.org/', '')


def apply_plan(species, plan, name2rec):
    moved = 0
    for rec in species:
        items = plan.get(id(rec))
        if not items:
            continue
        papers = rec.get('papers')
        if not isinstance(papers, list):
            continue
        for idx, target in sorted(items, key=lambda x: -x[0]):
            paper = papers[idx]
            tgt = name2rec[target].setdefault('papers', [])
            dn = norm_doi(lget(paper, 'doi', 'd', 'DOI'))
            if not (dn and any(norm_doi(lget(q, 'doi', 'd', 'DOI')) == dn for q in tgt)):
                tgt.append(paper)
            papers.pop(idx)
            moved += 1
    return moved


def write_csv(rows, path):
    cols = ['action', 'comm', 'filed_under', 'move_to', 'matched_in', 'doi', 'year', 'title']
    order = {'move': 0, 'review-multi': 1, 'review-none': 2, 'keep': 3}
    rows = sorted(rows, key=lambda r: (order.get(r['action'], 9), r['comm'] != 'yes', r['filed_under']))
    try:
        f = open(path, 'w', newline='', encoding='utf-8')
    except OSError:
        path = path.replace('.csv', '_NEW.csv')
        print('  (could not write %s, maybe open in Excel; writing %s instead)' % (args.out, path))
        f = open(path, 'w', newline='', encoding='utf-8')
    with f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    return path


def main():
    import embedded_db as edb
    html = Path(args.html).read_text(encoding='utf-8')
    species, eq, end = edb.load(html)
    print('Loaded %d species from %s' % (len(species), args.html))
    rows, plan, name2rec = audit(species)
    n_move = sum(1 for r in rows if r['action'] == 'move')
    n_multi = sum(1 for r in rows if r['action'] == 'review-multi')
    n_none = sum(1 for r in rows if r['action'] == 'review-none')
    total = sum(len(r.get('papers') or []) for r in species)
    out = write_csv(rows, args.out)
    print('Papers in atlas: %d' % total)
    print('  MOVE to correct species: %d' % n_move)
    print('  review-multi (several species, none its own): %d  [comm=yes -> General Literature]' % n_multi)
    print('  review-none  (no atlas species named): %d        [comm=yes -> General Literature]' % n_none)
    print('Wrote %s' % out)
    if not args.apply:
        print('\nDRY RUN: nothing changed. Check the "move" rows, then:\n  python clean_species_papers.py --apply')
        return
    if n_move == 0:
        print('\nNothing to move.')
        return
    moved = apply_plan(species, plan, name2rec)
    new_html = edb.write(html, species, eq, end)
    bk = args.html + '.backup-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    shutil.copyfile(args.html, bk)
    Path(args.html).write_text(new_html, encoding='utf-8')
    print('\nMoved %d papers to their correct species.\nBackup: %s\nWrote %s' % (moved, bk, args.html))


if __name__ == '__main__':
    main()