#!/usr/bin/env python3
"""
fetch_papers.py - Zoe.Logos-Graph

Keep data/archive/ up to date (stdlib only, no API key needed):

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

Species still without papers are also searched, once, on Europe PMC (no key, no daily
limit) and on OpenAlex with the species in the title alone.

Set OPENALEX_API_KEY (free, openalex.org/settings/api-key): without it OpenAlex allows
only 100 searches a day. OPENALEX_EMAIL is used for Crossref.

  python fetch_papers.py                       all four steps
  python fetch_papers.py --since 2026-06-01    new papers since this date
  python fetch_papers.py --no-new              only abstracts, citations, synonyms
  python fetch_papers.py --limit 20            first 20 species only (test)
  python fetch_papers.py --only-empty          only the species without papers (quick)
"""
import re, time, argparse
from urllib.parse import urlencode, quote
import atlas

ap = argparse.ArgumentParser()
ap.add_argument('--since', default='', help='YYYY-MM-DD (default: date of the last run)')
ap.add_argument('--no-new', action='store_true')
ap.add_argument('--limit', type=int, default=0)
ap.add_argument('--only-empty', action='store_true', help='only the species without papers')
args = ap.parse_args()

SELECT = ('doi,title,display_name,authorships,publication_year,primary_location,open_access,'
          'cited_by_count,abstract_inverted_index,type,is_retracted,is_paratext')
BAD_TITLE = re.compile(r'^(?:erratum|corrigendum|correction|retraction|editorial|book review|'
                       r'review of|in memoriam|obituary|reply to|response to|comment on)\b', re.I)


def record(w):
    """OpenAlex work -> paper record (same fields as data/archive/)"""
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


def search(query, since, deep):
    """journal articles matching the query, one OpenAlex search per page of 100:
    deep = the 1000 most cited of any year, otherwise those published since `since`"""
    out, cursor, pages = [], '*', 0
    while cursor and pages < (10 if deep else 20):
        f = 'title_and_abstract.search:%s AND %s,has_doi:true,type:article' % (query, atlas.COMM_QUERY)
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


def search_titles(query):
    """species still without papers: every article with the species in the TITLE, whatever
    the abstract says (old papers and taxonomic descriptions often have no abstract on
    OpenAlex, so the search with communication terms cannot find them); the titles that
    are about communication are kept below. At most 200, one or two searches."""
    out, cursor = [], '*'
    for _ in range(2):
        data = atlas.openalex('works', filter='title.search:%s,has_doi:true,type:article' % query,
                              select=SELECT, per_page=100, cursor=cursor)
        if data is None:
            return out
        out += data.get('results') or []
        cursor = (data.get('meta') or {}).get('next_cursor') if data.get('results') else None
        if not cursor:
            break
        time.sleep(0.2)
    return out


EPMC = 'https://www.ebi.ac.uk/europepmc/webservices/rest/search?'
EPMC_COMM = ('vocal* OR call OR calls OR song* OR acoustic* OR sound* OR communicat* OR display* OR '
             'alarm OR pheromone* OR echolocat* OR playback OR courtship OR gesture* OR whistle* OR '
             'chorus OR signal*')
EPMC_SKIP = {'preprint', 'published erratum', 'comment', 'editorial', 'letter', 'retraction of publication',
             'retracted publication', 'news'}


def epmc_record(r):
    """Europe PMC result -> paper record (same fields as data/archive/), None if not a journal article"""
    doi = atlas.norm_doi(r.get('doi'))
    journal = (((r.get('journalInfo') or {}).get('journal') or {}).get('title') or r.get('journalTitle') or '')
    kinds = {k.lower() for k in ((r.get('pubTypeList') or {}).get('pubType') or [])}
    title = atlas.clean(r.get('title')).rstrip('.')
    if not doi or not journal or kinds & EPMC_SKIP or BAD_TITLE.search(title):
        return None
    authors = [a.get('fullName') or '' for a in ((r.get('authorList') or {}).get('author') or [])[:20]]
    ab = atlas.clean(r.get('abstractText'))
    return {
        'doi': doi, 'title': title, 'authors': authors or (r.get('authorString') or '').split(', ')[:20],
        'year': int(r.get('pubYear') or 0), 'journal': atlas.clean(journal), 'url': 'https://doi.org/' + doi,
        'open_access': 1 if r.get('isOpenAccess') == 'Y' else 0, 'citations': r.get('citedByCount') or 0,
        'abstract': ab, 'abstract_full': len(ab) >= 200,
        'themes': [], 'study_type': '', 'setting': '', 'recording_type': '', 'sample_size': '',
        'added': atlas.today(), 'species': [], 'status': '',
    }


def europepmc_empty(species, papers, syn, state, shown, key):
    """species without papers: Europe PMC, once for each species (and again if synonyms are
    added). It has many zoology and veterinary journals and needs no key; it is searched
    before OpenAlex, so it works also when the OpenAlex budget of the day is used up."""
    names = atlas.SpeciesNames(species, syn)
    done = set(state.get('epmc_searched') or [])
    todo = [s for s in species if shown.get(s['sci'], 0) == 0 and key(s) not in done]
    if not todo:
        return set()
    print('Europe PMC: %d species without papers' % len(todo))
    new, failed = set(), 0
    for s in todo:
        ns = atlas.search_names(s, syn, True)
        q = '(%s) AND (TITLE:(%s) OR ABSTRACT:(%s)) AND NOT SRC:PPR' % (
            ' OR '.join('TITLE:"%s" OR ABSTRACT:"%s"' % (n, n) for n in ns), EPMC_COMM, EPMC_COMM)
        cursor, ok = '*', True
        for _ in range(3):                            # at most 300 results
            data = atlas.get_json(EPMC + urlencode({'query': q, 'resultType': 'core', 'format': 'json',
                                                    'pageSize': 100, 'cursorMark': cursor}))
            if data is None:
                ok = False
                break
            for r in (data.get('resultList') or {}).get('result') or []:
                p = epmc_record(r)
                if p and p['doi'] not in papers and \
                        atlas.about_communication(names.strip(p['title']), names.strip(p['abstract']), True):
                    papers[p['doi']] = p
                    new.add(p['doi'])
            nxt = data.get('nextCursorMark')
            if not nxt or nxt == cursor or not (data.get('resultList') or {}).get('result'):
                break
            cursor = nxt
            time.sleep(0.2)
        if ok:
            done.add(key(s))
            state['epmc_searched'] = sorted(done)
        else:
            failed += 1
    if failed:
        print('Europe PMC did not answer for %d species: they will be tried again next time' % failed)
    print('Europe PMC: %d new papers' % len(new))
    return new


def new_papers(species, papers, syn, since, state, new):
    """species searched before: papers since the last run; new species (and, once, every
    species after the search started asking for communication terms): their 1000 most
    cited communication papers of any year.
    One search per species and page ("Taeniopygia guttata" OR "zebra finch"), so a normal
    run costs about one search per species of the 1000 a day of a free OpenAlex key; the
    deep searches may need two or three days, each run goes on where the last one stopped."""
    names = atlas.SpeciesNames(species, syn)
    done = set(state.get('comm_searched') or [])
    rescued = set(state.get('rescue_searched') or [])     # few papers: searched once with every name
    titled = set(state.get('title_searched') or [])       # no papers: searched once by title alone
    key = lambda s: '|'.join([s['sci']] + sorted((syn.get('manual') or {}).get(s['sci'], [])))
    shown = {}
    for p in papers.values():
        if p.get('status') == 'species':
            for x in p.get('species') or []:
                shown[x] = shown.get(x, 0) + 1
    todo = species[:args.limit] if args.limit else species
    if args.only_empty:
        todo = [s for s in todo if shown.get(s['sci'], 0) == 0]
    new |= europepmc_empty(todo, papers, syn, state, shown, key)
    found = len(new)
    for i, s in enumerate(todo, 1):
        wide = shown.get(s['sci'], 0) < 5 and key(s) not in rescued   # again if synonyms were added
        deep = wide or s['sci'] not in done
        ns = atlas.search_names(s, syn, wide)
        works = search('(%s)' % ' OR '.join('"%s"' % n for n in ns), since, deep)
        if works is None:                             # OR query refused: one name at a time
            parts = [search('"%s"' % n, since, deep) for n in ns]
            if all(w is None for w in parts):
                print('  search failed for %s, it will be tried again next time' % s['sci'])
                continue
            works = [w for part in parts for w in part or []]
        bare = shown.get(s['sci'], 0) == 0 and key(s) not in titled
        if bare:
            works += search_titles('(%s)' % ' OR '.join('"%s"' % n for n in atlas.search_names(s, syn, True)))
        for w in works:
            doi = atlas.norm_doi(w.get('doi'))
            if not doi or doi in papers or not journal_article(w):
                continue
            p = record(w)
            # keep only papers about communication: the store stays small and clean
            if atlas.about_communication(names.strip(p['title']), names.strip(p['abstract']), True):
                papers[doi] = p
                new.add(doi)
                found += 1
        done.add(s['sci'])
        state['comm_searched'] = sorted(done)
        if wide:
            rescued.add(key(s))
            state['rescue_searched'] = sorted(rescued)
        if bare:
            titled.add(key(s))
            state['title_searched'] = sorted(titled)
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


def abstracts_and_citations(papers, only=None):
    """only: a set of DOIs (the papers just found), otherwise every paper"""
    if only is not None:
        papers = {d: papers[d] for d in only if d in papers}
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
    dois = sorted(d for d, p in papers.items() if not re.search(r'[,|]', d) and not p.get('trashed'))
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
    complete, new = True, set()
    only = new if args.only_empty else None              # --only-empty: abstracts of the new papers only
    try:
        if not args.no_new:
            since = args.since or state.get('papers_since') or '2026-06-01'
            # OpenAlex adds papers weeks after publication: look back 60 days, duplicates are skipped
            since = time.strftime('%Y-%m-%d', time.localtime(time.mktime(time.strptime(since, '%Y-%m-%d')) - 60 * 86400))
            new_papers(species, papers, syn, since, state, new)    # fills `new` as it goes
        abstracts_and_citations(papers, only)
    except atlas.OpenAlexLimit:
        complete = False
        print('\nOpenAlex daily budget used up (it resets at 01:00 Italian time). What was found is saved;'
              '\nrun again tomorrow to finish.')
        abstracts_and_citations(papers, only)

    atlas.save_papers(papers)
    if complete and not args.no_new and not args.limit and not args.only_empty:
        state['papers_since'] = atlas.today()
    state['papers_checked'] = atlas.today()
    atlas.write_json(atlas.STATE, state)
    print('papers: %d papers (%+d)' % (len(papers), len(papers) - n0))


if __name__ == '__main__':
    main()
