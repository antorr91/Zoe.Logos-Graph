#!/usr/bin/env python3
"""
build_site.py - Zoe.Logos-Graph

Bring every page in line with species_explorer.html after an update:
  - home page numbers (species, papers, classes) and the "last updated" date
  - compare.html        (build_compare.py)
  - literature.html     (build_literature.py, from data/archive/)
  - graph data          (build_graph_data.py, needs networkx)
  - taxonomy.html       (class > order > family > species tree)
  - data.html           (research gaps, downloads) and the files in outputs/data/export/
  - root index.html     -> redirect to outputs/index.html (GitHub Pages serves the root)

  python build_site.py
"""
import re, sys, csv, json, subprocess
from collections import defaultdict
import atlas

OUT = atlas.PROJ / 'outputs'
HOME = OUT / 'index.html'
EXPORT = OUT / 'data' / 'export'
THEME_LABELS = {
    'vocal_learning': 'Vocal learning', 'referential': 'Referential communication', 'syntax': 'Syntax',
    'individual_recognition': 'Individual recognition', 'cultural_transmission': 'Cultural transmission',
    'turn_taking': 'Turn-taking and duetting', 'honest_signalling': 'Honest signalling',
    'echolocation': 'Echolocation', 'infrasound': 'Infrasound', 'dialects': 'Dialects',
    'emotion': 'Emotion', 'multimodal': 'Multimodal', 'deception': 'Deception',
    'parent_offspring': 'Parent-offspring', 'alarm': 'Alarm', 'cooperation': 'Cooperation'}
REDIRECT = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Zoe.Logos-Graph</title>
<meta http-equiv="refresh" content="0; url=outputs/index.html">
<link rel="canonical" href="outputs/index.html">
</head>
<body><p><a href="outputs/index.html">Zoe.Logos-Graph &rarr;</a></p></body>
</html>
"""


def run(*cmd):
    print('$ ' + ' '.join(cmd))
    r = subprocess.run([sys.executable] + list(cmd), cwd=atlas.PROJ, capture_output=True, text=True)
    for line in (r.stdout + r.stderr).strip().splitlines()[-3:]:
        print('    ' + line)
    if r.returncode:
        raise SystemExit('failed: ' + ' '.join(cmd))


def home(species):
    n = len(species)
    papers = len({p['doi'] for s in species for p in s.get('papers') or []})
    classes = len({s['class_'] for s in species if s.get('class_')})
    day = atlas.read_json(atlas.STATE, {}).get('papers_checked') or atlas.today()
    h = HOME.read_text(encoding='utf-8')
    h = re.sub(r'(<span class="stat-n">)\d+(</span><span class="stat-l">species)', r'\g<1>%d\2' % n, h)
    h = re.sub(r'(<span class="stat-n">)\d+(</span><span class="stat-l">peer-reviewed papers)', r'\g<1>%d\2' % papers, h)
    h = re.sub(r'(<span class="stat-n">)\d+(</span>\s*<span class="stat-l">classes)', r'\g<1>%d\2' % classes, h)
    h = re.sub(r'\d+ species · search in 6 languages', '%d species · search in 6 languages' % n, h)
    if 'id="last-update"' not in h:
        h = h.replace('</body>', '<p style="text-align:center;font-size:11px;color:var(--hint);margin:0 0 2rem">'
                      'Papers last updated <span id="last-update"></span></p>\n</body>', 1)
    h = re.sub(r'(<span id="last-update">)[^<]*(</span>)', r'\g<1>%s\2' % day, h)
    HOME.write_text(h, encoding='utf-8')
    print('home: %d species, %d papers, %d classes, updated %s' % (n, papers, classes, day))


def set_const(page, name, value):
    """replace the one-line `const NAME = ...;` in a page with fresh data"""
    path = OUT / page
    h = path.read_text(encoding='utf-8')
    start = h.index('const %s = ' % name)
    stop = h.index('\n', start)
    h = h[:start] + 'const %s = %s;' % (name, json.dumps(value, ensure_ascii=False, separators=(',', ':'))) + h[stop:]
    path.write_text(h, encoding='utf-8')


def is_methods(p):
    return bool(atlas.METHODS_RX.search((p.get('title') or '') + ' ' + (p.get('abstract') or '')))


def taxonomy(species):
    rows = [[s['sci'], (s.get('en') or '').split(',')[0].strip(), s.get('class_') or '?', s.get('order_') or '?',
             s.get('family') or '?', len(s.get('papers') or []), sum(map(is_methods, s.get('papers') or [])),
             len(s.get('recordings') or [])] for s in species]
    set_const('taxonomy.html', 'TAX', rows)
    print('taxonomy: %d species, %d families' % (len(rows), len({r[4] for r in rows})))


def exports(species, papers):
    """plain files for people who want the data (linked from data.html)"""
    EXPORT.mkdir(parents=True, exist_ok=True)
    cls = {s['sci']: s for s in species}
    with open(EXPORT / 'papers.csv', 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['doi', 'title', 'year', 'journal', 'species', 'themes', 'methods', 'open_access', 'citations', 'where'])
        for p in sorted(papers.values(), key=lambda p: (-(p.get('year') or 0), p['doi'])):
            if p.get('status') in ('species', 'general'):
                w.writerow([p['doi'], p['title'], p.get('year') or '', p.get('journal') or '', '; '.join(p.get('species') or []),
                            '; '.join(p.get('themes') or []), int(is_methods(p)), p.get('open_access') or 0,
                            p.get('citations') or 0, 'species page' if p['status'] == 'species' else 'literature only'])
    with open(EXPORT / 'species.csv', 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['scientific_name', 'english_name', 'class', 'order', 'family', 'papers', 'recordings',
                    'vocal_learning', 'signal_types', 'wikipedia'])
        for s in species:
            w.writerow([s['sci'], s.get('en') or '', s.get('class_') or '', s.get('order_') or '', s.get('family') or '',
                        len(s.get('papers') or []), len(s.get('recordings') or []), s.get('learning') or '',
                        '; '.join(s.get('voc') or []), s.get('wiki') or ''])
    with open(EXPORT / 'recordings.csv', 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['species', 'source', 'id', 'type', 'date', 'place', 'recordist', 'audio', 'page', 'licence'])
        for s in species:
            for r in s.get('recordings') or []:
                w.writerow([s['sci'], r.get('source') or 'xc', r.get('id') or '', r.get('type') or '', r.get('date') or '',
                            r.get('cnt') or '', r.get('rec') or '', r.get('audio') or '', r.get('url') or '', r.get('license') or ''])
    return [p for p in sorted(EXPORT.iterdir())]


def data_page(species, papers, files):
    n_species = defaultdict(int)
    for s in species:
        n_species[s.get('class_') or '?'] += 1
    by_theme = defaultdict(lambda: defaultdict(int))
    cls = {s['sci']: s.get('class_') or '?' for s in species}
    shown = [p for p in papers.values() if p.get('status') == 'species']
    for p in shown:
        for c in {cls[x] for x in p.get('species') or [] if x in cls}:
            for t in p.get('themes') or []:
                by_theme[t][c] += 1
    desc = {'papers.csv': 'every paper with its species, themes, DOI and whether it is a methods paper',
            'species.csv': 'the species with taxonomy, number of papers and recordings',
            'recordings.csv': 'every recording with source, place, licence and audio link',
            'graph_communities.json': 'the species network used by the graph page',
            'graph_bipartite.graphml': 'the same network for Gephi, NetworkX or igraph'}
    paths = [(f, 'data/export/' + f.name) for f in files] + \
            [(OUT / 'data' / 'built' / n, 'data/built/' + n) for n in ('graph_communities.json', 'graph_bipartite.graphml')]
    set_const('data.html', 'GAPS', {
        'classes': dict(n_species), 'themes': {t: dict(v) for t, v in by_theme.items()},
        'labels': THEME_LABELS, 'updated': atlas.read_json(atlas.STATE, {}).get('papers_checked') or atlas.today(),
        'totals': {'species': len(species), 'papers': len(shown), 'methods': sum(map(is_methods, shown)),
                   'recordings': sum(len(s.get('recordings') or []) for s in species)},
        'files': [[rel, desc.get(f.name, ''), max(1, round(f.stat().st_size / 1024))] for f, rel in paths if f.exists()]})
    print('data page: %d themes x %d classes, %d files' % (len(by_theme), len(n_species), len(paths)))


def main():
    html, species, eq, end = atlas.load_species()
    papers = atlas.load_papers()
    home(species)
    (atlas.PROJ / 'index.html').write_text(REDIRECT, encoding='utf-8')
    run('build_compare.py')
    run('build_literature.py')
    try:
        import networkx  # noqa: F401
        run('build_graph_data.py')
    except ImportError:
        print('networkx not installed: graph data not rebuilt (pip install networkx)')
    taxonomy(species)
    data_page(species, papers, exports(species, papers))


if __name__ == '__main__':
    main()
