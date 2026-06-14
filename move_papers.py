#!/usr/bin/env python3
"""
move_papers.py - Zoe.Logos-Graph

Apply your review decisions to approved_papers.json: move a paper to the correct
species, park it in a general-literature bucket, hold it for a future species, or
delete it. Always makes a timestamped backup before writing.

WORKFLOW
  1) python move_papers.py --prep
       reads paper_review.csv and writes paper_actions.csv with a prefilled
       'action' column (suggested from maybe_belongs_to). Open it in Excel.

  2) edit the 'action' column. Allowed values:
       move:Genus species   move the paper to that species (created if it does
                            not exist yet, so it waits for a future species)
       general              move to the general-literature bucket
       delete               remove the paper entirely
       keep   (or blank)    leave it where it is

  3) python move_papers.py            dry run: shows what would change
     python move_papers.py --apply    writes it (after backing up)

By default only Tier A rows get a suggested move; Tier B/C are left as 'keep'.
"""
import json, csv, re, argparse, shutil, datetime
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument('--master', default='approved_papers.json')
ap.add_argument('--review', default='paper_review.csv')
ap.add_argument('--actions', default='paper_actions.csv')
ap.add_argument('--general-key', default='General Literature')
ap.add_argument('--prep', action='store_true', help='generate paper_actions.csv from paper_review.csv')
ap.add_argument('--apply', action='store_true', help='write changes (otherwise dry run)')
args = ap.parse_args()


def norm_doi(d):
    return (d or '').strip().lower().replace('https://doi.org/', '').replace('http://dx.doi.org/', '')


# ---------- step 1: prepare the actions file ----------
def prep():
    rows = list(csv.DictReader(open(args.review, encoding='utf-8')))
    out = []
    for r in rows:
        action = 'keep'
        if r.get('tier') == 'A_misfiled':
            sugg = (r.get('maybe_belongs_to') or '').split(' | ')
            sugg = [s for s in sugg if ' ' in s]      # only real binomials, not category tokens
            action = 'move:' + sugg[0] if len(sugg) == 1 else 'review'
        elif r.get('tier') == 'B_review':
            action = 'review'
        out.append({'action': action, 'species': r.get('species', ''),
                    'maybe_belongs_to': r.get('maybe_belongs_to', ''), 'doi': r.get('doi', ''),
                    'year': r.get('year', ''), 'title': r.get('title', '')})
    with open(args.actions, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['action', 'species', 'maybe_belongs_to', 'doi', 'year', 'title'])
        w.writeheader(); w.writerows(out)
    n_move = sum(1 for r in out if r['action'].startswith('move:'))
    print('Wrote %s (%d rows).' % (args.actions, len(out)))
    print('  prefilled move: %d   | to review: %d' % (n_move, sum(1 for r in out if r['action'] == 'review')))
    print('Edit the action column, then run:  python move_papers.py   (dry run)')


# ---------- master access (tolerates a few JSON shapes) ----------
def open_master():
    data = json.loads(Path(args.master).read_text(encoding='utf-8'))
    root = data['species'] if (isinstance(data, dict) and 'species' in data
                               and isinstance(data['species'], (dict, list))) else data
    if isinstance(root, dict):
        sample = next(iter(root.values()), {})
        kind = 'dict_of_list' if isinstance(sample, list) else 'dict_of_dict'
    else:
        kind = 'list'
    return data, root, kind


def papers_of(root, kind, name, create=False):
    """return the live papers list for a species (or None)."""
    if kind == 'list':
        for e in root:
            if (e.get('sci') or e.get('name')) == name:
                return e.setdefault('papers', [])
        if create:
            e = {'sci': name, 'papers': []}; root.append(e); return e['papers']
        return None
    if name not in root:
        if create:
            root[name] = ([] if kind == 'dict_of_list' else {'papers': []})
        else:
            return None
    entry = root[name]
    return entry if kind == 'dict_of_list' else entry.setdefault('papers', [])


def find_paper(papers, doi, title):
    dn = norm_doi(doi)
    for i, p in enumerate(papers):
        if dn and norm_doi(p.get('doi') or p.get('DOI')) == dn:
            return i
    if title:
        for i, p in enumerate(papers):
            if (p.get('title') or '').strip()[:80] == title.strip()[:80]:
                return i
    return None


# ---------- step 3: apply ----------
def apply():
    if not Path(args.actions).exists():
        print('No %s found. Run:  python move_papers.py --prep   first.' % args.actions); return
    data, root, kind = open_master()
    actions = list(csv.DictReader(open(args.actions, encoding='utf-8')))
    stat = {'move': 0, 'general': 0, 'delete': 0, 'keep': 0, 'not_found': 0, 'dup_skip': 0, 'new_species': 0}
    targets_created = set()

    for r in actions:
        act = (r.get('action') or '').strip().lower()
        src = r.get('species', ''); doi = r.get('doi', ''); title = r.get('title', '')
        if act in ('', 'keep', 'review'):
            stat['keep'] += 1; continue

        src_papers = papers_of(root, kind, src)
        if src_papers is None:
            stat['not_found'] += 1; continue
        idx = find_paper(src_papers, doi, title)
        if idx is None:
            stat['not_found'] += 1; continue

        if act == 'delete':
            if args.apply:
                src_papers.pop(idx)
            stat['delete'] += 1; continue

        if act == 'general':
            target = args.general_key
        elif act.startswith('move:'):
            target = r['action'].split(':', 1)[1].strip()
        else:
            stat['keep'] += 1; continue

        existed = (papers_of(root, kind, target) is not None)
        tgt_papers = papers_of(root, kind, target, create=True)
        if not existed and target not in (args.general_key,):
            stat['new_species'] += 1; targets_created.add(target)
        paper = src_papers[idx]
        if find_paper(tgt_papers, paper.get('doi') or paper.get('DOI'), paper.get('title')) is not None:
            stat['dup_skip'] += 1
            if args.apply:
                src_papers.pop(idx)
            continue
        if args.apply:
            tgt_papers.append(src_papers.pop(idx))
        stat['general' if act == 'general' else 'move'] += 1

    print('Planned' if not args.apply else 'Applied', 'actions:')
    print('  move to species : %d' % stat['move'])
    print('  to general      : %d' % stat['general'])
    print('  deleted         : %d' % stat['delete'])
    print('  kept            : %d' % stat['keep'])
    print('  duplicates skipped (removed from source): %d' % stat['dup_skip'])
    print('  paper not found (doi/title mismatch): %d' % stat['not_found'])
    if stat['new_species']:
        print('  NEW species containers created (for future species): %d -> %s'
              % (stat['new_species'], ', '.join(sorted(targets_created)[:8]) + ('...' if len(targets_created) > 8 else '')))

    if not args.apply:
        print('\nDry run only. Re-run with --apply to write the changes.')
        return
    bk = '%s.backup-%s.json' % (args.master.rsplit('.json', 1)[0],
                                datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
    shutil.copyfile(args.master, bk)
    Path(args.master).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
    print('\nBackup saved to %s' % bk)
    print('Wrote %s' % args.master)


if __name__ == '__main__':
    if args.prep:
        prep()
    else:
        apply()
