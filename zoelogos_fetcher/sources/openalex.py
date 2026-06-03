"""OpenAlex paper source.

Free, no API key required. Set OPENALEX_EMAIL for the polite pool
(higher rate limits, ~10 req/s vs default 1 req/s).
"""
from __future__ import annotations
import os, time, urllib.parse
from ..http_util import http_get_json

BASE = 'https://api.openalex.org/works'


class OpenAlexSource:
    name = 'openalex'

    def __init__(self, email: str | None = None, polite_delay: float = 0.15):
        self.email = email or os.environ.get('OPENALEX_EMAIL', '')
        self.delay = polite_delay

    def _reconstruct_abstract(self, inverted: dict | None) -> str:
        if not inverted:
            return ''
        pos = sorted((idx, word) for word, idxs in inverted.items()
                     for idx in idxs)
        return ' '.join(w for _, w in pos)

    def search_species(self, scientific_name: str, common_name: str = '',
                       max_results: int = 50) -> list[dict]:
        """Return papers about this species' vocal communication."""
        # OpenAlex search is sensitive to query syntax. Use a simple
        # quoted phrase + topical keyword; ranking handles the rest.
        query_terms = f'"{scientific_name}" vocal communication'
        params = {
            'search': query_terms,
            'filter': ','.join([
                'has_abstract:true',
                'type:article',
                'cited_by_count:>2',     # exclude near-uncited noise
            ]),
            'sort':     'relevance_score:desc',
            'per-page': str(min(max_results, 200)),
        }
        if self.email:
            params['mailto'] = self.email
        url = BASE + '?' + urllib.parse.urlencode(params)
        d = http_get_json(url)
        time.sleep(self.delay)
        results = d.get('results', [])
        # If too few results, try a broader query (without "vocal communication")
        if len(results) < 5:
            params['search'] = f'"{scientific_name}" vocalization'
            url = BASE + '?' + urllib.parse.urlencode(params)
            d2 = http_get_json(url)
            time.sleep(self.delay)
            # Merge unique by id
            seen = {(w.get('id') or '') for w in results}
            for w in d2.get('results', []):
                if (w.get('id') or '') not in seen:
                    results.append(w)
        return [self._normalise(w, scientific_name) for w in results]

    def _normalise(self, w: dict, target_species: str) -> dict:
        """Normalise an OpenAlex Work into our common schema."""
        loc = w.get('primary_location') or {}
        src = loc.get('source') or {}
        doi = (w.get('doi') or '').replace('https://doi.org/', '').lower()
        return {
            'source':       'openalex',
            'openalex_id':  (w.get('id') or '').replace('https://openalex.org/', ''),
            'doi':          doi,
            'pmid':         (w.get('ids') or {}).get('pmid', '').replace(
                                'https://pubmed.ncbi.nlm.nih.gov/', '') or '',
            'title':        (w.get('title') or '').strip(),
            'abstract':     self._reconstruct_abstract(
                                w.get('abstract_inverted_index')),
            'authors':      [a.get('author', {}).get('display_name', '')
                             for a in (w.get('authorships') or [])][:10],
            'year':         w.get('publication_year'),
            'venue':        src.get('display_name', '') or '',
            'venue_issn':   src.get('issn_l', '') or '',
            'venue_type':   src.get('type', '') or '',
            'cited_by':     w.get('cited_by_count', 0) or 0,
            'is_oa':        bool((w.get('open_access') or {}).get('is_oa')),
            'work_type':    w.get('type', '') or '',
            'target_species': target_species,
            'concepts':     [c.get('display_name', '')
                             for c in (w.get('concepts') or [])
                             if (c.get('level') or 99) <= 2][:6],
        }
