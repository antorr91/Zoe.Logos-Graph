#!/usr/bin/env python3
"""
assign_species.py - Zoe.Logos-Graph

Decide, for every paper in data/archive/, which species it belongs to, and
write the result into the species page. Everything is recomputed from the text
each time, so a paper filed under the wrong species in the past cannot stay there.

RULES
  1. the paper must be about communication (keywords in title / abstract);
     papers on diet, genetics, disease, plumage ... are left out
  2. species named in the TITLE        -> the paper goes to those species (max 6)
  3. otherwise species named in the ABSTRACT -> those species (max 5); a species
     only mentioned in passing next to the main one is not counted
  4. names = scientific name, "G. species", synonyms and specific English names
     (see atlas.SpeciesNames and data/synonyms.json)
  5. communication papers naming no atlas species (or too many) go to the
     Literature page only; papers whose full abstract is not known yet and do not
     name a species in the title wait ('pending') until fetch_papers.py finds it.
     Papers naming the species in the title stay on its page meanwhile
  6. data/curation.csv always wins (doi, species, decision = keep | remove, note)

Run from the PROJECT ROOT.

  python assign_species.py              dry run -> reports/attribution_changes.csv
  python assign_species.py --apply      write papers.json and species_explorer.html
"""
import csv, argparse, collections
import atlas

ap = argparse.ArgumentParser()
ap.add_argument('--apply', action='store_true')
args = ap.parse_args()

MAX_TITLE, MAX_ABSTRACT = 6, 5
PAGE_FIELDS = ['title', 'authors', 'year', 'journal', 'doi', 'url', 'open_access', 'citations',
               'abstract', 'themes', 'study_type', 'setting', 'recording_type', 'sample_size']


def read_curation():
    out = collections.defaultdict(dict)
    if atlas.CURATION.exists():
        with open(atlas.CURATION, encoding='utf-8-sig', newline='') as f:
            for r in csv.DictReader(f):
                doi = atlas.norm_doi(r.get('doi'))
                d = (r.get('decision') or '').strip().lower()
                if doi and d in ('keep', 'remove'):
                    out[doi][(r.get('species') or '*').strip()] = d
    return out


KEEP_IN_TRASH = ('doi', 'title', 'year', 'journal', 'status', 'why', 'species', 'added')


def trash(p):
    """off-topic papers keep only what is needed to recognise them, so that they are not
    downloaded and judged again at every update, and the archive stays small"""
    for k in list(p):
        if k not in KEEP_IN_TRASH:
            del p[k]
    p.update(abstract='', abstract_full=True, themes=[], trashed=True)


def assign(p, names):
    """-> (species list, status, reason)"""
    if p.get('trashed'):                    # judged off topic before: only the title is kept
        return [], 'offtopic', p.get('why') or 'not about communication'
    title, abstract = p['title'], p['abstract']
    full = p.get('abstract_full') or p.get('no_abstract')     # nothing more to wait for
    if atlas.NOT_RESEARCH.search(title):
        return [], 'offtopic', 'not a study (note, review of a book, anniversary)'
    if atlas.BIOCHEM.search(title):
        return [], 'offtopic', 'chemistry of the signal (molecules, genes), not communication'
    comm = atlas.about_communication(names.strip(title), names.strip(abstract), full)
    if comm is False:
        return [], 'offtopic', 'not about communication'
    in_title = names.find(title)
    if not in_title and names.other_species(title):
        return [], 'general', 'title names a species not in the atlas'
    if in_title:
        if len(in_title) > MAX_TITLE:
            return [], 'general', '%d species in the title' % len(in_title)
        if comm is None:
            core, _ = atlas.comm_terms(names.strip(title))
            core2, weak2 = atlas.comm_terms(names.strip(title + ' ' + abstract))
            if not core and len(core2 | weak2) < 2:     # nothing yet says it is about communication
                return [], 'pending', 'topic unclear until the full abstract'
            return sorted(in_title), 'species', 'title (topic to check with the full abstract)'
        return sorted(in_title), 'species', 'title'
    in_abs = names.find(abstract, plain=False)
    t_core, t_weak = atlas.comm_terms(names.strip(title))
    if in_abs and not t_core and not (t_weak and comm):
        # a species named only in the abstract of a paper whose title is not about
        # communication is usually a passing mention (a list of birds, a comparison)
        return [], 'general', 'species only in the abstract, title not about communication'
    if in_abs:
        top = max(in_abs.values())
        main = {s for s, n in in_abs.items() if n * 3 >= top}      # drop passing mentions
        if len(main) > MAX_ABSTRACT:
            return [], 'general', '%d species in the abstract' % len(main)
        if comm is None:
            return [], 'pending', 'topic unclear until the full abstract'
        return sorted(main), 'species', 'abstract' if full else 'abstract (partial)'
    if not full:
        return [], 'pending', 'no species in title, full abstract not known yet'
    return [], 'general', 'no atlas species named'


def main():
    html, species, eq, end = atlas.load_species()
    papers = atlas.load_papers()
    names = atlas.SpeciesNames(species)
    cur = read_curation()
    before = collections.defaultdict(set)
    for s in species:
        for p in s.get('papers') or []:
            before[s['sci']].add(atlas.norm_doi(p.get('doi')))

    stats = collections.Counter()
    for doi, p in papers.items():
        sp, status, why = assign(p, names)
        c = cur.get(doi, {})
        if c.get('*') == 'remove':
            sp, status, why = [], 'removed', 'curation.csv'
        else:
            sp = [s for s in sp if c.get(s) != 'remove']
            for s, d in c.items():
                if d == 'keep' and s in names.sci and s not in sp:
                    sp.append(s)
            if c:
                why += ' + curation.csv'
            if sp:
                status = 'species'
            elif status == 'species':
                status = 'general'
        p['species'], p['status'], p['why'] = sorted(sp), status, why
        text = p['title'] + ' ' + p['abstract']
        p['themes'] = atlas.themes_of(text) if p.get('abstract_full') else \
            sorted(set(p.get('themes') or []) | set(atlas.themes_of(text)))
        if status in ('offtopic', 'removed') and not p.get('trashed'):
            trash(p)
        stats[status] += 1

    after = collections.defaultdict(set)
    for doi, p in papers.items():
        for s in p['species']:
            after[s].add(doi)

    rows = []
    for s in sorted(set(before) | set(after)):
        for doi in sorted(before[s] - after[s]):
            p = papers.get(doi, {})
            where = ', '.join(p.get('species') or []) or p.get('status', 'dropped')
            rows.append(['removed', s, where, p.get('why', ''), doi, p.get('title', '')])
        for doi in sorted(after[s] - before[s]):
            p = papers[doi]
            rows.append(['added', s, '', p['why'], doi, p['title']])
    atlas.REPORTS.mkdir(exist_ok=True)
    with open(atlas.REPORTS / 'attribution_changes.csv', 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['change', 'species', 'now_under', 'reason', 'doi', 'title'])
        w.writerows(rows)

    n_links = sum(len(v) for v in after.values())
    print('papers: %d   ' % len(papers) + '   '.join('%s %d' % kv for kv in stats.most_common()))
    print('species-paper links: %d (before %d)   removed %d, added %d  -> reports/attribution_changes.csv'
          % (n_links, sum(len(v) for v in before.values()),
             sum(r[0] == 'removed' for r in rows), sum(r[0] == 'added' for r in rows)))
    print('species without papers: %d' % sum(1 for s in species if not after[s['sci']]))
    with open(atlas.REPORTS / 'few_papers.csv', 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)                              # to decide: search them better, or leave them out
        w.writerow(['species', 'english', 'class', 'order', 'papers'])
        for s in sorted(species, key=lambda s: (len(after[s['sci']]), s['sci'])):
            if len(after[s['sci']]) < 5:
                w.writerow([s['sci'], s.get('en', ''), s.get('class_', ''), s.get('order_', ''), len(after[s['sci']])])
    print('species with fewer than 5 papers: %d -> reports/few_papers.csv'
          % sum(1 for s in species if len(after[s['sci']]) < 5))
    if not args.apply:
        print('dry run: nothing written (use --apply)')
        return

    for s in species:
        rows = sorted((papers[d] for d in after[s['sci']]), key=lambda p: (-(p['year'] or 0), -(p['citations'] or 0), p['doi']))
        s['papers'] = [dict({k: p.get(k, '') for k in PAGE_FIELDS}, abstract=atlas.shorten(p['abstract']))
                       for p in rows]
    atlas.save_papers(papers)
    atlas.save_species(html, species, eq, end)
    print('written: data/archive/, outputs/species_explorer.html')


if __name__ == '__main__':
    main()
