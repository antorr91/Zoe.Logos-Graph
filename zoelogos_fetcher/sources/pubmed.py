"""PubMed source via NCBI E-utilities.

Free, no key required. With NCBI_API_KEY env var you get 10 req/s
instead of 3 req/s.
"""
from __future__ import annotations
import os, time, re, urllib.parse, xml.etree.ElementTree as ET
from ..http_util import http_get_text

BASE_SEARCH = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi'
BASE_FETCH  = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi'


class PubMedSource:
    name = 'pubmed'

    def __init__(self, api_key: str | None = None, polite_delay: float = 0.35):
        self.api_key = api_key or os.environ.get('NCBI_API_KEY', '')
        # 3 req/s without key, 10 with key
        self.delay = 0.11 if self.api_key else polite_delay

    def _esearch(self, query: str, max_results: int = 50) -> list[str]:
        """Return list of PMIDs matching the query."""
        params = {
            'db': 'pubmed', 'term': query, 'retmax': str(max_results),
            'retmode': 'json', 'sort': 'relevance',
        }
        if self.api_key:
            params['api_key'] = self.api_key
        url = BASE_SEARCH + '?' + urllib.parse.urlencode(params)
        import json
        txt = http_get_text(url)
        time.sleep(self.delay)
        try:
            d = json.loads(txt)
            return d.get('esearchresult', {}).get('idlist', [])
        except Exception:
            return []

    def _efetch(self, pmids: list[str]) -> str:
        """Fetch the XML for a list of PMIDs."""
        if not pmids:
            return ''
        params = {
            'db': 'pubmed', 'id': ','.join(pmids), 'rettype': 'abstract',
            'retmode': 'xml',
        }
        if self.api_key:
            params['api_key'] = self.api_key
        url = BASE_FETCH + '?' + urllib.parse.urlencode(params)
        return http_get_text(url)

    def search_species(self, scientific_name: str, common_name: str = '',
                       max_results: int = 50) -> list[dict]:
        """Search PubMed for papers about this species' vocal communication."""
        # Build a query that uses MeSH terms when possible
        query = (f'("{scientific_name}"[Title/Abstract] OR '
                 f'"{scientific_name}"[Organism]) AND '
                 f'(vocalization[MeSH] OR "vocal communication"[Title/Abstract] '
                 f'OR "acoustic communication"[Title/Abstract] OR '
                 f'bioacoustics[Title/Abstract] OR "animal calls"[Title/Abstract] '
                 f'OR "vocal learning"[Title/Abstract]) NOT preprint[Filter]')
        pmids = self._esearch(query, max_results=max_results)
        if not pmids:
            return []
        xml_txt = self._efetch(pmids)
        time.sleep(self.delay)
        return self._parse_xml(xml_txt, scientific_name)

    def _parse_xml(self, xml_txt: str, target: str) -> list[dict]:
        if not xml_txt:
            return []
        try:
            root = ET.fromstring(xml_txt)
        except ET.ParseError:
            return []
        out = []
        for art in root.findall('.//PubmedArticle'):
            try:
                rec = self._parse_one(art, target)
                if rec:
                    out.append(rec)
            except Exception:
                continue
        return out

    def _parse_one(self, art: ET.Element, target: str) -> dict | None:
        pmid = (art.findtext('.//PMID') or '').strip()
        title = (art.findtext('.//ArticleTitle') or '').strip()
        if not title:
            return None
        # Abstract: concatenate AbstractText sections
        ab_parts = []
        for ab in art.findall('.//Abstract/AbstractText'):
            label = ab.get('Label')
            txt = ''.join(ab.itertext()).strip()
            if txt:
                ab_parts.append(f'{label}: {txt}' if label else txt)
        abstract = '\n'.join(ab_parts).strip()
        # DOI
        doi = ''
        for el in art.findall('.//ArticleId'):
            if (el.get('IdType') or '').lower() == 'doi':
                doi = (el.text or '').lower().strip()
                break
        # Authors
        authors = []
        for au in art.findall('.//Author')[:10]:
            ln = (au.findtext('LastName') or '').strip()
            in_ = (au.findtext('Initials') or '').strip()
            full = (au.findtext('CollectiveName') or '').strip()
            if ln:
                authors.append(f'{ln} {in_}'.strip())
            elif full:
                authors.append(full)
        # Year
        year = None
        y_el = art.find('.//PubDate/Year')
        if y_el is not None:
            try: year = int(y_el.text)
            except: pass
        if year is None:
            md = art.findtext('.//PubDate/MedlineDate') or ''
            m = re.search(r'\b(19|20)\d{2}\b', md)
            if m: year = int(m.group(0))
        # Journal
        journal = (art.findtext('.//Journal/Title') or '').strip()
        issn = (art.findtext('.//Journal/ISSN') or '').strip()
        # Publication type (excludes editorial/comment/letter/etc.)
        pubtypes = [pt.text for pt in art.findall('.//PublicationType')
                    if pt.text]
        return {
            'source':         'pubmed',
            'pmid':           pmid,
            'doi':            doi,
            'openalex_id':    '',
            'title':          title,
            'abstract':       abstract,
            'authors':        authors,
            'year':           year,
            'venue':          journal,
            'venue_issn':     issn,
            'venue_type':     'journal',          # PubMed is journals-only
            'cited_by':       None,               # PubMed doesn't have citation count
            'is_oa':          False,              # set later via OpenAlex enrichment
            'work_type':      pubtypes[0] if pubtypes else 'Journal Article',
            'pub_types':      pubtypes,
            'target_species': target,
            'concepts':       [],
        }
