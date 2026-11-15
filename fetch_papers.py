#!/usr/bin/env python3
"""
fetch_papers.py - Zoe.Logos-Graph

Keep data/papers.json up to date (stdlib only, no API key needed):

  1. NEW papers: for every atlas species, OpenAlex journal articles published since
     the last run that name the species (scientific name, synonyms or English name)
     in the title or abstract and are about communication. Preprints, editorials,
     book reviews... are skipped. A species new to the atlas gets its 500 most cited
     papers of any year. Whether a paper is really about that species is decided by
     assign_species.py, exactly as for the old papers.
  2. FULL ABSTRACTS for papers that only have a short one: OpenAlex first, then
     Europe PMC, then Crossref. Papers with no abstract anywhere are marked
     no_abstract, so they are judged on the title alone.
  3. CITATIONS refreshed for every paper (OpenAlex counts).
  4. GBIF synonyms for species not looked up yet (data/synonyms.json, 'gbif').

Set OPENALEX_API_KEY (free, openalex.org/settings/api-key): without it OpenAlex allows
only 100 searches a day. OPENALEX_EMAIL is used for Crossref.

  python fetch_papers.py                       all four steps
  python fetch_papers.py --since 2026-06-01    new papers since this date
  python fetch_papers.py --no-new              only abstracts, citations, synonyms
  python fetch_papers.py --limit 20            first 20 species only (test)
"""
import re, time, argparse
from urllib.parse import urlencode, quote
import atlas

ap = argparse.ArgumentParser()
ap.add_argument('--since', default='', help='YYYY-MM-DD (default: date of the last run)')
ap.add_argument('--no-new', action='store_true')
ap.add_argument('--limit', type=int, default=0)
args = ap.parse_args()

SELECT = ('doi,title,display_name,authorships,publication_year,primary_location,open_access,'
          'cited_by_count,abstract_inverted_index,type,is_retracted,is_paratext')
BAD_TITLE = re.compile(r'^(?:erratum|corrigendum|correction|retraction|editorial|book review|'
                       r'review of|in memoriam|obituary|reply to|response to|comment on)\b', re.I)


def record(w):
    """OpenAlex work -> paper record (same fields as data/papers.json)"""
    doi = atlas.norm_doi(w.get('doi'))
    src = ((w.get('primary_location') or {}).get('source') or {})
    ab = atlas.clean(atlas.from_inverted(w.get('abstract_inverted_index')))
    return {
        'doi': doi, 'title': atlas.clean(w.get('title') or w.get('display_name')),
        'authors': [((a.get('author') or {}).get('display_name') or '') for a in (w.get('authorships') or [])[:20]],
        'year': w.get('publication_year') or 0, 'journal': atlas.clean(src.get('display_name')),
        'url': 'https://doi.org/' + doi, 'open_access': 1 if (w.get('open_access') or {}).get('is_oa') else 0,
        'citations': w.get('cited_by_count') or 0, 'abstract': ab, 'abstract_full': len(ab) >= 200,
        'themes': [], 'study_type': '', 'setting': '', 'recording_type': '', 'sample_size': '',
        'added': atlas.today(), 'species': [], 'status': '',
    }


def journal_article(w):
    src = ((w.get('primary_location') or {}).get('source') or {})
    return (w.get('doi') and w.get('type') == 'article' and src.get('type') == 'journal'
            and not w.get('is_retracted') and not w.get('is_paratext')
            and not BAD_TITLE.search(w.get('title') or ''))


def search_names(s, syn):
    """scientific name, hand-written synonyms and English name (GBIF synonyms are only
    used to recognise names: many are 19th-century names nobody uses)"""
    names = [s['sci']] + (syn.get('manual') or {}).get(s['sci'], [])
    en = re.split(r'[,/;]', s.get('en') or '')[0].strip()
    if en.count(' ') >= 1 and en.lower() not in atlas.GENERIC:
        names.append(en)                              # "zebra finch", not "lion"
    return list(dict.fromkeys(n.replace('"', '') for n in names if n))[:4]


# only papers that also speak of communication: for chickens, mice or zebrafish the most
# cited papers are about genetics or medicine, and the communication ones would be missed
COMM_QUERY = ('(vocal OR vocalization OR vocalisation OR call OR song OR acoustic OR sound OR '
              'communication OR signal OR signalling OR display OR alarm OR pheromone OR '
              'echolocation OR playback OR courtship OR gesture OR whistle OR chorus)')


def search(query, since, deep):
    """journal articles matching the query, one OpenAlex search per page of 100:
    deep = the 1000 most cited of any year, otherwise those published since `since`"""
    out, cursor, pages = [], '*', 0
    while cursor and pages < (10 if deep else 20):
        f = 'title_and_abstract.search:%s AND %s,has_doi:true,type:article' % (query, COMM_QUERY)
        if not deep:
            f += ',from_publication_date:' + since
        data = atlas.openalex('works', filter=f, select=SELECT, per_page=100, cursor=cursor,
                              **({'sort': 'cited_by_count:desc'} if deep else {}))
        if data is None:
            return None
        out += data.get('results') or []
        cursor = (data.get('meta') or {}).get('next_cursor') if data.get('results') else None
        pages += 1
        time.sleep(0.2)
    return out


def new_papers(species, papers, syn, since, state):
    """species searched before: papers since the last run; new species (and, once, every
    species after the search started asking for communication terms): their 1000 most
    cited communication papers of any year.
    One search per species and page ("Taeniopygia guttata" OR "zebra finch"), so a normal
    run costs about one search per species of the 1000 a day of a free OpenAlex key; the
    deep searches may need two or three days, each run goes on where the last one stopped."""
    names = atlas.SpeciesNames(species, syn)
    done = set(state.get('comm_searched') or [])
    found = 0
    todo = species[:args.limit] if args.limit else species
    for i, s in enumerate(todo, 1):
        deep = s['sci'] not in done
        ns = search_names(s, syn)
        works = search('(%s)' % ' OR '.join('"%s"' % n for n in ns), since, deep)
        if works is None:                             # OR query refused: one name at a time
            parts = [search('"%s"' % n, since, deep) for n in ns]
            if all(w is None for w in parts):
                print('  search failed for %s, it will be tried again next time' % s['sci'])
                continue
            works = [w for part in parts for w in part or []]
        for w in works:
            doi = atlas.norm_doi(w.get('doi'))
            if not doi or doi in papers or not journal_article(w):
                continue
            p = record(w)
            # keep only papers about communication: the store stays small and clean
            if atlas.about_communication(names.strip(p['title']), names.strip(p['abstract']), True):
                papers[doi] = p
                found += 1
        done.add(s['sci'])
        state['comm_searched'] = sorted(done)
        if i % 50 == 0:
            print('  %d/%d species, %d new papers' % (i, len(todo), found))
    print('new papers: %d' % found)


def europepmc_abstracts(dois):
    """{doi: abstract} for up to 25 DOIs in one request; None if the service could not be reached"""
    q = ' OR '.join('DOI:"%s"' % d for d in dois)
    data = atlas.get_json('https://www.ebi.ac.uk/europepmc/webservices/rest/search?' + urlencode(
        {'query': q, 'resultType': 'core', 'format': 'json', 'pageSize': 100}), missing_ok=True)
    if data is None:
        return None
    out = {}
    for r in (data.get('resultList') or {}).get('result') or []:
        d = atlas.norm_doi(r.get('doi'))
        if d in dois and r.get('abstractText'):
            out[d] = atlas.clean(r['abstractText'])
    return out


def crossref_abstract(doi):
    """abstract or '', None if Crossref could not be reached"""
    data = atlas.get_json('https://api.crossref.org/works/' + quote(doi) +
                          ('?mailto=' + atlas.EMAIL if atlas.EMAIL else ''), missing_ok=True)
    if data is None:
        return None
    ab = atlas.clean((data.get('message') or {}).get('abstract'))
    return re.sub(r'^abstract\s*', '', ab, flags=re.I)


def abstracts_and_citations(papers):
    got = 0

    def update(w):
        nonlocal got
        p = papers.get(atlas.norm_doi((w or {}).get('doi')))
        if not p:
            return
        p['citations'] = max(p.get('citations') or 0, w.get('cited_by_count') or 0)
        if (w.get('open_access') or {}).get('is_oa'):
            p['open_access'] = 1
        ab = atlas.clean(atlas.from_inverted(w.get('abstract_inverted_index')))
        if not p.get('abstract_full') and len(ab) >= 200:
            p['abstract'], p['abstract_full'] = ab, True
            got += 1

    fields = 'doi,cited_by_count,abstract_inverted_index,open_access'
    dois = sorted(d for d in papers if not re.search(r'[,|]', d))
    openalex_done = True
    try:
        for i in range(0, len(dois), 50):            # 50 DOIs per OpenAlex request
            data = atlas.openalex('works', filter='doi:' + '|'.join(dois[i:i + 50]), per_page=50, select=fields)
            for w in (data or {}).get('results') or []:
                update(w)
            time.sleep(0.15)
            if i and i % 2000 == 0:
                print('  OpenAlex: %d/%d papers checked' % (i, len(dois)))
        for d in sorted(d for d in papers if re.search(r'[,|]', d)):     # old DOIs with commas: one by one
            update(atlas.openalex('works/https://doi.org/' + quote(d), select=fields))
    except atlas.OpenAlexLimit:
        openalex_done = False                         # Europe PMC and Crossref still run below
        print('OpenAlex daily budget used up: abstracts from Europe PMC and Crossref only this time')
    print('full abstracts from OpenAlex: %d' % got)

    missing = [p for p in papers.values() if not p.get('abstract_full') and not p.get('no_abstract')]
    got = 0
    for i in range(0, len(missing), 25):
        chunk = missing[i:i + 25]
        epmc = europepmc_abstracts([p['doi'] for p in chunk])
        for p in chunk:
            ab = (epmc or {}).get(p['doi'], '')
            cr = crossref_abstract(p['doi']) if len(ab) < 200 else ''
            ab = max(ab, cr or '', key=len)
            if len(ab) >= 200:
                p['abstract'], p['abstract_full'] = ab, True
                got += 1
            elif openalex_done and epmc is not None and cr is not None:
                p['no_abstract'] = True                # judged on the title (and short abstract) only
            time.sleep(0.05)
        if i and i % 1000 == 0:
            print('  Europe PMC / Crossref: %d/%d' % (i, len(missing)))
    print('full abstracts from Europe PMC / Crossref: %d of %d' % (got, len(missing)))


def gbif_synonyms(species, syn):
    gb = syn.setdefault('gbif', {})
    todo = [s['sci'] for s in species if s['sci'] not in gb]
    for sci in todo:
        m = atlas.get_json('https://api.gbif.org/v1/species/match?' + urlencode({'name': sci, 'strict': 'true'}))
        key = (m or {}).get('acceptedUsageKey') or (m or {}).get('usageKey')
        names = []
        if key and (m or {}).get('rank') in ('SPECIES', 'SUBSPECIES'):
            data = atlas.get_json('https://api.gbif.org/v1/species/%s/synonyms?limit=50' % key)
            for r in (data or {}).get('results') or []:
                n = r.get('canonicalName') or ''
                if n and n != sci and atlas.good_synonym(n) and n.split()[-1] == n.split()[-1].lower():
                    names.append(n)
        gb[sci] = sorted(set(names))[:15]
        time.sleep(0.1)
    if todo:
        print('GBIF synonyms looked up for %d species' % len(todo))


def main():
    html, species, eq, end = atlas.load_species()
    papers = atlas.load_papers()
    syn = atlas.read_json(atlas.SYNONYMS, {})
    state = atlas.read_json(atlas.STATE, {})
    n0 = len(papers)

    if not atlas.OPENALEX_KEY:
        print('No OPENALEX_API_KEY: OpenAlex allows only 100 searches a day without a key.')
    gbif_synonyms(species, syn)
    atlas.write_json(atlas.SYNONYMS, syn)
    complete = True
    try:
        if not args.no_new:
            since = args.since or state.get('papers_since') or '2026-06-01'
            # OpenAlex adds papers weeks after publication: look back 60 days, duplicates are skipped
            since = time.strftime('%Y-%m-%d', time.localtime(time.mktime(time.strptime(since, '%Y-%m-%d')) - 60 * 86400))
            new_papers(species, papers, syn, since, state)
        abstracts_and_citations(papers)
    except atlas.OpenAlexLimit:
        complete = False
        print('\nOpenAlex daily budget used up (it resets at 01:00 Italian time). What was found is saved;'
              '\nrun again tomorrow to finish.')
        abstracts_and_citations(papers)

    atlas.save_papers(papers)
    if complete and not args.no_new and not args.limit:
        state['papers_since'] = atlas.today()
    state['papers_checked'] = atlas.today()
    atlas.write_json(atlas.STATE, state)
    print('papers.json: %d papers (%+d)' % (len(papers), len(papers) - n0))


if __name__ == '__main__':
    main()
