#!/usr/bin/env python3
"""
fetch_literature.py - Zoe.Logos-Graph  (v2, higher precision)

Extend the literature with strong guarantees that papers belong to the right species.

ACCEPT RULES (a paper is kept only if ALL hold):
  - it is a journal article with a DOI and a real abstract, not retracted/paratext
  - no off-topic keyword in the title (genomics, phylogeny, microplastics, ...)
  - at least one communication keyword in title/abstract
  - the species is clearly named, and one of:
        * the full binomial appears in the text  (strongest), OR
        * genus + common name appear AND no OTHER atlas species is named in the text
    (this cross-species check is what stops misfiled papers)

The best papers per species are kept, ranked by: binomial-in-title, communication
density, citations, recency. Up to --per-species (default 15, set 20 if you like).

Themes are auto-suggested from text. LLM-only fields are left empty for curation.
Writes into approved_papers.json (timestamped backup first) and a review CSV.

USAGE
  python fetch_literature.py --species "Panthera pardus" --dry-run
  python fetch_literature.py --per-species 20 --only-missing
"""
import json, csv, re, time, argparse, shutil, datetime
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import quote
from urllib.error import HTTPError, URLError

ap = argparse.ArgumentParser()
ap.add_argument('--csv', default='species_master.csv')
ap.add_argument('--master', default='approved_papers.json')
ap.add_argument('--per-species', type=int, default=15)
ap.add_argument('--only-missing', action='store_true')
ap.add_argument('--species', default='')
ap.add_argument('--limit', type=int, default=None)
ap.add_argument('--pages', type=int, default=2, help='OpenAlex pages of 50 to scan per species')
ap.add_argument('--review-csv', default='literature_added.csv')
ap.add_argument('--mailto', default='a.m.c.torrisi@qmul.ac.uk')
ap.add_argument('--dry-run', action='store_true')
args = ap.parse_args()

COMM = ['vocal', 'vocalis', 'vocaliz', 'call', 'song', 'acoustic', 'sound production', 'signal',
        'communicat', 'alarm', 'echolocat', 'ultrason', 'infrasound', 'duet', 'syntax',
        'referential', 'bioacoustic', 'chorus', 'whistle', 'click', 'bark', 'roar', 'hiss',
        'drum', 'stridulat', 'chirp', 'rumble', 'growl', 'hearing', 'auditory', 'phonation',
        'syllable', 'repertoire', 'spectrogram', 'formant', 'contact call', 'advertisement call',
        'mating call', 'courtship', 'begging', 'trill', 'purr', 'meow', 'howl', 'grunt', 'snort',
        'squeak', 'squeal', 'vibration', 'seismic', 'substrate-borne', 'tremulation',
        'warning call', 'distress call', 'acoustic signal', 'acoustic communication']

NEG = ['microplastic', 'heavy metal', 'heavy-metal', 'toxicolog', 'genome', 'genomic',
       'transcriptom', 'mitochondrial', 'phylogen', 'population genetic', 'stable isotope',
       'stomach content', 'diet composition', 'parasit', 'helminth', 'pathogen', 'antibody',
       'vaccine', 'species distribution model', 'land use', 'pesticide', 'pollutant',
       'crystal structure', 'gene expression', 'crispr', 'microbiome', 'fishery stock']

THEME_KW = {
    'vocal_learning': ['vocal learning', 'song learning', 'imitat', 'vocal production learning', 'tutor'],
    'referential': ['referential', 'functionally referential', 'food call', 'denot', 'object-specific'],
    'syntax': ['syntax', 'combinator', 'sequence', 'ordering', 'compositional', 'call combination'],
    'individual_recognition': ['individual recognition', 'individual identity', 'voice recognition', 'vocal signature'],
    'cultural_transmission': ['cultural', 'tradition', 'horizontal transmission', 'social transmission', 'song sharing'],
    'turn_taking': ['turn-taking', 'turn taking', 'duet', 'antiphonal', 'temporal coordination', 'overlap avoidance'],
    'honest_signalling': ['honest', 'reliab', 'condition-dependent', 'quality signal', 'handicap', 'index signal'],
    'echolocation': ['echolocat', 'biosonar', 'sonar', 'click train'],
    'infrasound': ['infrasound', 'infrasonic', 'low-frequency rumble', 'low frequency call'],
    'dialects': ['dialect', 'geographic variation', 'regional variation', 'song variation'],
    'emotion': ['emotion', 'affect', 'arousal', 'valence', 'distress', 'expression of emotion'],
    'multimodal': ['multimodal', 'multi-modal', 'visual and acoustic', 'gestur', 'cross-modal', 'audiovisual'],
    'deception': ['deception', 'deceptive', 'mimic', 'false alarm', 'manipulat', 'tactical'],
    'parent_offspring': ['parent-offspring', 'mother-offspring', 'pup', 'chick', 'begging', 'maternal', 'nestling'],
    'alarm': ['alarm', 'predator', 'warning call', 'antipredator', 'mobbing'],
    'cooperation': ['cooperat', 'coordinat', 'recruit', 'collective', 'group decision', 'consensus'],
}

UA = {'User-Agent': 'Zoe.Logos-Graph/1.0 (mailto:%s)' % args.mailto}


def http_json(url):
    try:
        with urlopen(Request(url, headers=UA), timeout=45) as r:
            return json.loads(r.read())
    except (HTTPError, URLError, ValueError, TimeoutError) as e:
        print('      [warn]', e); return None


def recon_abstract(inv):
    if not inv:
        return ''
    pos = {}
    for word, idxs in inv.items():
        for i in idxs:
            pos[i] = word
    return ' '.join(pos[i] for i in sorted(pos))


def species_in(text, sci, common):
    """3 full binomial, 2 genus+common, 1 genus or common, 0 none ; plus has_full flag"""
    t = text.lower()
    p = (sci or '').lower().split()
    genus = p[0] if p else ''
    epithet = p[1] if len(p) > 1 else ''
    full = ' '.join(p[:2])
    cm = (common or '').lower().strip()
    has_full = bool(full) and full in t
    has_genus = bool(genus) and re.search(r'\b' + re.escape(genus) + r'\b', t) is not None
    has_epi = bool(epithet) and re.search(r'\b' + re.escape(epithet) + r'\b', t) is not None
    has_common = bool(cm) and any(re.search(r'\b' + re.escape(w) + r'\b', t)
                                  for w in cm.split() if len(w) >= 4)
    if has_full:
        return 3, True
    if has_genus and (has_epi or has_common):
        return 2, False
    if has_genus or has_common:
        return 1, False
    return 0, False


def auto_themes(text):
    t = text.lower()
    return [th for th, kws in THEME_KW.items() if any(k in t for k in kws)]


def fetch_openalex(sci):
    works = []
    for page in range(1, args.pages + 1):
        flt = quote('title_and_abstract.search:%s,type:article,has_abstract:true,is_paratext:false' % sci)
        url = ('https://api.openalex.org/works?filter=%s&sort=cited_by_count:desc&per-page=50&page=%d&mailto=%s'
               % (flt, page, quote(args.mailto)))
        d = http_json(url)
        res = (d or {}).get('results', []) or []
        works += res
        time.sleep(0.2)
        if len(res) < 50:
            break
    return works


def to_record(w, sci, score, themes):
    src = (w.get('primary_location') or {}).get('source') or {}
    doi = (w.get('doi') or '').replace('https://doi.org/', '')
    pmid = ((w.get('ids') or {}).get('pmid') or '').split('/')[-1]
    return {
        'source': 'openalex', 'openalex_id': (w.get('id') or '').split('/')[-1],
        'doi': doi, 'pmid': pmid,
        'title': w.get('display_name') or '', 'abstract': recon_abstract(w.get('abstract_inverted_index')),
        'authors': [a.get('author', {}).get('display_name', '') for a in (w.get('authorships') or [])][:25],
        'year': w.get('publication_year') or '',
        'venue': src.get('display_name', ''), 'venue_issn': src.get('issn_l', ''),
        'venue_type': src.get('type', ''), 'work_type': w.get('type', ''),
        'is_oa': bool((w.get('open_access') or {}).get('is_oa')), 'cited_by': w.get('cited_by_count', 0),
        'concepts': [c.get('display_name', '') for c in (w.get('concepts') or [])[:6]],
        'themes': themes, 'target_species': sci, 'species_studied': [sci],
        'relevance': score, 'confidence': 'auto',
        'research_question': '', 'key_findings': [], 'study_type': '',
        'methods_setting': '', 'methods_recording_type': '', 'methods_sample_size': '',
        'methods_analysis': '', 'implications': '', 'limitations': '',
    }


def main():
    data = json.loads(Path(args.master).read_text(encoding='utf-8'))
    is_wrapped = isinstance(data, dict) and 'species' in data
    root = data['species'] if is_wrapped else data
    if not isinstance(root, list):
        raise SystemExit('expected approved_papers.json with a species list')
    by_sci = {(e.get('sci') or '').lower(): e for e in root}

    if args.species:
        wanted = [{'sci': args.species, 'en': ''}]
    else:
        with open(args.csv, encoding='utf-8') as f:
            wanted = [{'sci': r.get('sci', '').strip(), 'en': r.get('en', '').strip()}
                      for r in csv.DictReader(f) if r.get('sci')]
    if args.limit:
        wanted = wanted[:args.limit]

    # cross-species index: every binomial known to the atlas
    all_binos = {}
    for lst in (root, wanted):
        for e in lst:
            p = (e.get('sci') or '').lower().split()
            if len(p) >= 2:
                all_binos[' '.join(p[:2])] = e.get('sci')

    added_rows, total_added, touched = [], 0, 0
    for i, sp in enumerate(wanted, 1):
        sci, en = sp['sci'], sp['en']
        target_bino = ' '.join(sci.lower().split()[:2])
        entry = by_sci.get(sci.lower())
        if entry is None:
            entry = {'sci': sci, 'en': en, 'papers': []}
            root.append(entry); by_sci[sci.lower()] = entry
        papers = entry.setdefault('papers', [])
        have_doi = {(p.get('doi') or '').lower() for p in papers}
        print('[%d/%d] %s (have %d)' % (i, len(wanted), sci, len(papers)), end=' ')
        if args.only_missing and len(papers) >= args.per_species:
            print('-> full'); continue

        candidates = []
        for w in fetch_openalex(sci):
            if w.get('type') != 'article' or w.get('is_retracted') or w.get('is_paratext'):
                continue
            doi = (w.get('doi') or '').replace('https://doi.org/', '')
            if not doi or doi.lower() in have_doi:
                continue
            src = (w.get('primary_location') or {}).get('source') or {}
            if (src.get('type') or '') != 'journal':
                continue
            title = w.get('display_name') or ''
            abstract = recon_abstract(w.get('abstract_inverted_index'))
            if len(abstract) < 60:
                continue
            tl = title.lower()
            if any(neg in tl for neg in NEG):
                continue
            text = title + ' ' + abstract
            tlow = text.lower()
            if not any(k in tlow for k in COMM):
                continue
            score, has_full = species_in(text, sci, en)
            if score < 2:
                continue
            if not has_full:
                if any(b != target_bino and b in tlow for b in all_binos):
                    continue   # another atlas species named, binomial not explicit -> skip
            themes = auto_themes(text)
            comm_count = sum(1 for k in COMM if k in tlow)
            cit = w.get('cited_by_count', 0) or 0
            yr = w.get('publication_year') or 0
            q = (6 if has_full else 3) + (4 if target_bino in tl else 0) \
                + min(comm_count, 6) + min(cit, 200) / 25.0 + (1 if (yr and yr >= 2010) else 0)
            candidates.append((q, doi, to_record(w, sci, score, themes)))

        candidates.sort(key=lambda c: c[0], reverse=True)
        kept = 0
        for q, doi, rec in candidates:
            if len(papers) >= args.per_species:
                break
            if doi.lower() in have_doi:
                continue
            papers.append(rec); have_doi.add(doi.lower())
            added_rows.append({'species': sci, 'year': rec['year'], 'doi': doi, 'q': round(q, 1),
                               'relevance': rec['relevance'], 'themes': ';'.join(rec['themes']),
                               'title': rec['title'][:140]})
            kept += 1; total_added += 1
        if kept:
            touched += 1
        print('-> +%d' % kept)

    print('\nAdded %d papers across %d species.' % (total_added, touched))
    if added_rows:
        with open(args.review_csv, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=['species', 'year', 'doi', 'q', 'relevance', 'themes', 'title'])
            w.writeheader(); w.writerows(added_rows)
        print('Review list: %s' % args.review_csv)

    if args.dry_run:
        print('DRY RUN: master not written.'); return
    if total_added == 0:
        print('Nothing to write.'); return
    bk = '%s.backup-%s.json' % (args.master.rsplit('.json', 1)[0],
                                datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
    shutil.copyfile(args.master, bk)
    Path(args.master).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
    print('Backup: %s\nWrote %s' % (bk, args.master))


if __name__ == '__main__':
    main()
