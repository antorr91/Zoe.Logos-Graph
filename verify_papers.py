#!/usr/bin/env python3
"""
verify_papers.py - Zoe.Logos-Graph

Audit the papers you already have and flag the ones that probably do NOT belong
to the species they are filed under.

Two passes:
  1) RELEVANCE (offline, fast): for each paper, check whether the species name
     (full binomial / genus / common name) actually appears in the stored title
     or abstract, and whether any communication keyword is present. Papers where
     the species is never mentioned are the prime suspects.
  2) DOI (optional, online): with --check-doi it resolves each DOI on Crossref,
     confirms it exists, and compares the stored title with the canonical one.

OUTPUT: paper_review.csv  (sorted worst-first), plus a printed summary.
        Columns: species, doi, year, score, flags, title

USAGE
  python verify_papers.py                         # offline relevance audit
  python verify_papers.py --check-doi             # also verify DOIs on Crossref (slower)
  python verify_papers.py --min-score 1           # only list papers below this score
  python verify_papers.py --source approved_papers.json
"""
import json, csv, re, time, argparse, difflib
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ap = argparse.ArgumentParser()
ap.add_argument('--source', default='approved_papers.json')
ap.add_argument('--out', default='paper_review.csv')
ap.add_argument('--check-doi', action='store_true', help='resolve every DOI on Crossref (online, slow)')
ap.add_argument('--min-score', type=int, default=99, help='only report papers with score < this (default: all)')
ap.add_argument('--limit', type=int, default=None, help='for testing: only first N papers')
args = ap.parse_args()

COMM = ['vocal', 'vocalization', 'vocalisation', 'call', 'song', 'acoustic', 'sound',
        'signal', 'communicat', 'alarm', 'echolocat', 'ultrasonic', 'ultrasound',
        'infrasound', 'duet', 'syntax', 'referential', 'bioacoustic', 'chorus',
        'whistle', 'click', 'bark', 'roar', 'hiss', 'drumming', 'stridulat', 'chirp']

UA = {'User-Agent': 'Zoe.Logos-Graph/1.0 (mailto:a.m.c.torrisi@qmul.ac.uk)'}


def lget(d, *names):
    """case-insensitive get of the first matching key"""
    low = {k.lower(): v for k, v in d.items()} if isinstance(d, dict) else {}
    for n in names:
        if n.lower() in low and low[n.lower()]:
            return low[n.lower()]
    return ''


def iter_species(data):
    """yield (species_name, sci, common, [papers]) tolerating a few JSON shapes"""
    if isinstance(data, dict) and 'species' in data and isinstance(data['species'], (list, dict)):
        data = data['species']
    if isinstance(data, list):
        for entry in data:
            sci = lget(entry, 'sci', 'scientific_name', 'scientificName', 'species', 'name')
            common = lget(entry, 'en', 'common', 'common_name')
            papers = lget(entry, 'papers', 'works') or []
            yield sci or common, sci, common, papers
    elif isinstance(data, dict):
        for key, val in data.items():
            if isinstance(val, dict):
                sci = lget(val, 'sci', 'scientific_name', 'scientificName') or key
                common = lget(val, 'en', 'common', 'common_name')
                papers = lget(val, 'papers', 'works') or []
            elif isinstance(val, list):
                sci, common, papers = key, '', val
            else:
                continue
            yield key, sci, common, papers


def relevance(sci, common, text):
    t = (text or '').lower()
    sci = (sci or '').lower().strip()
    parts = sci.split()
    genus = parts[0] if parts else ''
    epithet = parts[1] if len(parts) > 1 else ''
    full = ' '.join(parts[:2])
    cm = (common or '').lower().strip()

    has_full = bool(full) and full in t
    has_genus = bool(genus) and re.search(r'\b' + re.escape(genus) + r'\b', t) is not None
    has_epi = bool(epithet) and re.search(r'\b' + re.escape(epithet) + r'\b', t) is not None
    has_common = bool(cm) and len(cm) >= 4 and cm in t

    if has_full:
        score = 3
    elif has_genus and (has_epi or has_common):
        score = 2
    elif has_genus or has_common:
        score = 1
    else:
        score = 0
    has_comm = any(k in t for k in COMM)
    return score, has_comm


def crossref_check(doi):
    doi = (doi or '').strip().lower().replace('https://doi.org/', '').replace('http://dx.doi.org/', '')
    if not re.match(r'10\.\d{4,9}/\S+', doi):
        return 'bad_doi_format', ''
    try:
        with urlopen(Request('https://api.crossref.org/works/' + doi, headers=UA), timeout=30) as r:
            d = json.loads(r.read())
        msg = d.get('message', {})
        title = (msg.get('title') or [''])[0]
        return 'ok', title
    except HTTPError as e:
        return ('doi_not_found' if e.code == 404 else 'doi_error_%s' % e.code), ''
    except (URLError, ValueError, TimeoutError):
        return 'doi_unreachable', ''


def main():
    data = json.loads(Path(args.source).read_text(encoding='utf-8'))
    rows = []
    n_papers = 0
    stat = {'score0': 0, 'no_comm': 0, 'no_abstract': 0, 'doi_bad': 0}
    seen_doi = {}

    for name, sci, common, papers in iter_species(data):
        for p in (papers if isinstance(papers, list) else []):
            if not isinstance(p, dict):
                continue
            n_papers += 1
            if args.limit and n_papers > args.limit:
                break
            title = lget(p, 'title')
            abstract = lget(p, 'abstract', 'summary')
            doi = lget(p, 'doi', 'DOI')
            year = lget(p, 'year', 'published', 'date') or ''
            text = title + ' ' + abstract
            score, has_comm = relevance(sci, common, text)
            flags = []
            if score == 0:
                flags.append('species_not_mentioned'); stat['score0'] += 1
            if not abstract or len(abstract) < 40:
                flags.append('no_abstract'); stat['no_abstract'] += 1
            if not has_comm:
                flags.append('no_comm_keyword'); stat['no_comm'] += 1
            d_norm = (doi or '').lower().strip()
            if d_norm:
                if d_norm in seen_doi:
                    flags.append('dup_doi:' + seen_doi[d_norm])
                else:
                    seen_doi[d_norm] = name
            else:
                flags.append('no_doi')

            if args.check_doi and d_norm:
                status, cr_title = crossref_check(doi)
                time.sleep(0.05)
                if status != 'ok':
                    flags.append(status); stat['doi_bad'] += 1
                elif title and cr_title:
                    ratio = difflib.SequenceMatcher(None, title.lower(), cr_title.lower()).ratio()
                    if ratio < 0.6:
                        flags.append('title_mismatch')

            if score < args.min_score:
                rows.append({'species': name, 'doi': doi, 'year': year, 'score': score,
                             'flags': ';'.join(flags), 'title': title[:140]})
        if args.limit and n_papers > args.limit:
            break

    rows.sort(key=lambda r: (r['score'], r['species']))
    with open(args.out, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['species', 'doi', 'year', 'score', 'flags', 'title'])
        w.writeheader(); w.writerows(rows)

    print('Papers checked: %d' % n_papers)
    print('  species NOT mentioned in title/abstract (score 0): %d  <-- prime suspects' % stat['score0'])
    print('  no communication keyword: %d' % stat['no_comm'])
    print('  missing/short abstract: %d' % stat['no_abstract'])
    if args.check_doi:
        print('  DOI problems: %d' % stat['doi_bad'])
    print('\nWrote %s (%d rows, worst first). Open it in Excel and review the score-0 ones.'
          % (args.out, len(rows)))


if __name__ == '__main__':
    main()
