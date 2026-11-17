#!/usr/bin/env python3
"""
restore_recordings.py - Zoe.Logos-Graph

Puts back the recordings of archives that were wrongly marked as unreachable
(archive.org, observation.org, tierstimmenarchiv.de, colecciones.humboldt.org.co).
It looks back in the git history for the last commit that still had them, and adds
them again to their species. Papers and the other recordings stay as they are.

  python restore_recordings.py
"""
import subprocess
from urllib.parse import urlparse
import atlas
import embedded_db as edb

HOSTS = {'archive.org', 'observation.org', 'www.tierstimmenarchiv.de', 'colecciones.humboldt.org.co'}


def git(*args):
    return subprocess.run(['git', *args], cwd=atlas.PROJ, capture_output=True, check=True).stdout.decode('utf-8')


def main():
    path = atlas.SPECIES_HTML.relative_to(atlas.PROJ).as_posix()
    html, species, eq, end = atlas.load_species()
    now = {r['audio'] for s in species for r in s.get('recordings') or []}

    for commit in git('log', '--format=%H %cs', '-n', '60', '--', path).split('\n'):
        if not commit.strip():
            continue
        sha, day = commit.split()
        old = {s['sci']: s.get('recordings') or [] for s in edb.load(git('show', '%s:%s' % (sha, path)))[0]}
        lost = {sci: [r for r in recs if urlparse(r['audio']).netloc in HOSTS and r['audio'] not in now]
                for sci, recs in old.items()}
        lost = {sci: recs for sci, recs in lost.items() if recs}
        if lost:
            break
    else:
        print('nothing to put back (they are already there, or no commit has them)')
        return

    for s in species:
        s['recordings'] = (s.get('recordings') or []) + lost.get(s['sci'], [])
    atlas.save_species(html, species, eq, end)
    print('from the commit of %s (%s)' % (day, sha[:7]))
    print('recordings put back: %d, species: %d' % (sum(map(len, lost.values())), len(lost)))
    print('recordings now: %d' % sum(len(s.get('recordings') or []) for s in species))


if __name__ == '__main__':
    main()