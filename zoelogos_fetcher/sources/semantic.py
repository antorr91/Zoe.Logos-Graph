"""Semantic Scholar source.

Free API, no key required for moderate use. Set SEMANTIC_SCHOLAR_KEY for
higher rate limits (request key at semanticscholar.org/product/api).
"""
from __future__ import annotations
import os, time, urllib.parse
from ..http_util import http_get_json

BASE = 'https://api.semanticscholar.org/graph/v1/paper/search'

FIELDS = ('paperId,externalIds,title,abstract,authors,year,venue,'
          'publicationVenue,publicationTypes,publicationDate,'
          'citationCount,influentialCitationCount,isOpenAccess,openAccessPdf')


class SemanticScholarSource:
    name = 'semantic_scholar'

    def __init__(self, api_key: str | None = None, polite_delay: float = 1.1):
        self.api_key = api_key or os.environ.get('SEMANTIC_SCHOLAR_KEY', '')
        # without key: 1 req/s rough; with key 10 req/s
        self.delay = 0.15 if self.api_key else polite_delay

    def _headers(self) -> dict:
        h = {'User-Agent': 'Zoe.Logos-Graph/3.0'}
        if self.api_key:
            h['x-api-key'] = self.api_key
        return h

    def search_species(self, scientific_name: str, common_name: str = '',
                       max_results: int = 50) -> list[dict]:
        query = f'{scientific_name} vocal communication'
        params = {
            'query':  query,
            'limit':  str(min(max_results, 100)),
            'fields': FIELDS,
        }
        url = BASE + '?' + urllib.parse.urlencode(params)
        d = http_get_json(url, headers=self._headers())
        time.sleep(self.delay)
        return [self._normalise(p, scientific_name) for p in d.get('data', [])]

    def _normalise(self, p: dict, target: str) -> dict:
        ex = p.get('externalIds') or {}
        pv = p.get('publicationVenue') or {}
        return {
            'source':         'semantic_scholar',
            'ss_id':          p.get('paperId', ''),
            'doi':            (ex.get('DOI') or '').lower(),
            'pmid':           ex.get('PubMed') or '',
            'openalex_id':    '',
            'title':          (p.get('title') or '').strip(),
            'abstract':       (p.get('abstract') or '').strip(),
            'authors':        [a.get('name', '')
                               for a in (p.get('authors') or [])][:10],
            'year':           p.get('year'),
            'venue':          p.get('venue', '') or pv.get('name', ''),
            'venue_issn':     (pv.get('issn') or ''),
            'venue_type':     (pv.get('type') or '').lower(),
            'cited_by':       p.get('citationCount', 0) or 0,
            'influential':    p.get('influentialCitationCount', 0) or 0,
            'is_oa':          bool(p.get('isOpenAccess')),
            'work_type':      ','.join(p.get('publicationTypes') or [])
                              if p.get('publicationTypes') else '',
            'pub_types':      p.get('publicationTypes') or [],
            'target_species': target,
            'concepts':       [],
        }
