#!/usr/bin/env python3
"""
update_atlas.py - Zoe.Logos-Graph

The whole update, in order. The GitHub Action runs it every two weeks; it also
runs by hand from the project root.

  1. fetch_papers.py      new papers, full abstracts, citations, GBIF synonyms
  2. assign_species.py    which species each paper belongs to
  3. fetch_recordings.py  check and top up the recordings   (skip with --no-recordings)
  4. build_site.py        home, compare, literature, graph

Writes reports/summary.md (used as the text of the Pull Request).

  python update_atlas.py
  python update_atlas.py --offline        steps 2 and 4 only, no internet needed
"""
import sys, csv, time, argparse, subprocess
from collections import Counter
import atlas

ap = argparse.ArgumentParser()
ap.add_argument('--offline', action='store_true')
ap.add_argument('--no-recordings', action='store_true')
args = ap.parse_args()


def step(*cmd):
    print('\n=== %s ===' % ' '.join(cmd), flush=True)
    t = time.time()
    if subprocess.run([sys.executable] + list(cmd), cwd=atlas.PROJ).returncode:
        raise SystemExit('%s failed' % cmd[0])
    print('    (%.0f s)' % (time.time() - t), flush=True)


def snapshot():
    _, species, _, _ = atlas.load_species()
    return {'species': len(species),
            'papers': len({p['doi'] for s in species for p in s.get('papers') or []}),
            'links': sum(len(s.get('papers') or []) for s in species),
            'recordings': sum(len(s.get('recordings') or []) for s in species),
            'with_recordings': sum(1 for s in species if s.get('recordings'))}


def summary(before, after, n_before):
    papers = atlas.load_papers()
    status = Counter(p.get('status') for p in papers.values())
    new = [p for p in papers.values() if p.get('added') == atlas.today() and p.get('status') == 'species']
    changes = Counter()
    path = atlas.REPORTS / 'attribution_changes.csv'
    if path.exists():
        with open(path, encoding='utf-8') as f:
            changes = Counter(r['change'] for r in csv.DictReader(f))
    L = ['## Zoe.Logos-Graph update, %s' % atlas.today(), '',
         '| | before | after |', '|---|---:|---:|']
    for k, label in [('species', 'species'), ('papers', 'papers on species pages'),
                     ('links', 'species-paper links'), ('recordings', 'recordings'),
                     ('with_recordings', 'species with recordings')]:
        L.append('| %s | %d | %d |' % (label, before[k], after[k]))
    L += ['', '**New papers found:** %d (on a species page: %d)' % (len(papers) - n_before, len(new))]
    for p in sorted(new, key=lambda p: p['title'])[:40]:
        L.append('- %s (%s) *%s*' % (p['title'], p['year'], ', '.join(p['species'])))
    L += ['', '**Species-paper links:** %d added, %d removed (`reports/attribution_changes.csv`)'
          % (changes['added'], changes['removed']), '',
          '**All papers:** ' + ', '.join('%s %d' % kv for kv in status.most_common()), '',
          'pending = waiting for the full abstract; general = about communication but naming no atlas '
          'species (Literature page only); offtopic = not about communication.', '',
          'To keep or remove a paper for a species on every future run, add a line to '
          '`data/curation.csv` (doi, species, keep or remove, note).']
    atlas.REPORTS.mkdir(exist_ok=True)
    (atlas.REPORTS / 'summary.md').write_text('\n'.join(L) + '\n', encoding='utf-8')
    print('\n'.join(L[:12]))


def main():
    before, n_before = snapshot(), len(atlas.load_papers())
    if before['papers'] == 0:
        raise SystemExit('species page has no papers: stop')
    if not args.offline:
        step('fetch_papers.py')
    step('assign_species.py', '--apply')
    if not args.no_recordings:
        step('fetch_recordings.py', *(['--offline'] if args.offline else []))
    step('build_site.py')
    after = snapshot()
    summary(before, after, n_before)
    # safety net for the automatic run: if a service was down and much was lost, do not publish
    if after['species'] != before['species'] or after['papers'] < 0.8 * before['papers'] \
            or after['recordings'] < 0.8 * before['recordings']:
        raise SystemExit('\nUnexpected drop (see table above): nothing will be published.')


if __name__ == '__main__':
    main()
