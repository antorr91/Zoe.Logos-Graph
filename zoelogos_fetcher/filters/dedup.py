"""Deduplicate papers retrieved from multiple sources.

Strategy:
  1. Group by normalised DOI (lowercase, strip prefix/suffix whitespace)
  2. For records without DOI, fall back to (title-normalised, year)
  3. Merge records by taking the union of non-empty fields, preferring:
       - cited_by:        max across sources
       - influential:     max across sources
       - abstract:        longest non-empty one
       - venue_issn:      first non-empty
       - is_oa:           True if any source says True
       - sources:         set of all source names that contributed
"""
from __future__ import annotations
import re


def _norm_title(t: str) -> str:
    if not t: return ''
    s = re.sub(r'<[^>]+>', '', t)           # strip HTML tags
    s = re.sub(r'\s+', ' ', s).strip().lower()
    s = re.sub(r'[^\w\s]', '', s)           # strip punctuation
    return s


def _merge(a: dict, b: dict) -> dict:
    """Merge b into a (a takes priority on ties)."""
    out = dict(a)
    # Numeric: prefer max
    for k in ('cited_by', 'influential'):
        va = a.get(k) or 0
        vb = b.get(k) or 0
        if vb and vb > (va or 0):
            out[k] = vb
        elif va:
            out[k] = va
    # Abstract: prefer longer
    if len(b.get('abstract') or '') > len(a.get('abstract') or ''):
        out['abstract'] = b['abstract']
    # OR booleans
    out['is_oa'] = bool(a.get('is_oa')) or bool(b.get('is_oa'))
    # First non-empty for several fields
    for k in ('doi', 'pmid', 'openalex_id', 'ss_id', 'venue_issn',
              'venue_type', 'venue', 'work_type'):
        if not a.get(k) and b.get(k):
            out[k] = b[k]
    # Union of pub_types and authors
    if b.get('pub_types'):
        out['pub_types'] = list(set((a.get('pub_types') or []) +
                                    (b.get('pub_types') or [])))
    if not a.get('authors') and b.get('authors'):
        out['authors'] = b['authors']
    # Track which sources contributed
    srcs = set(a.get('sources') or [a.get('source')] if a.get('source') else [])
    if b.get('source'): srcs.add(b['source'])
    out['sources'] = sorted(s for s in srcs if s)
    return out


def deduplicate(records: list[dict]) -> tuple[list[dict], dict]:
    """Returns (deduplicated, stats)."""
    by_doi: dict = {}
    by_title: dict = {}
    no_key = []

    for rec in records:
        doi = (rec.get('doi') or '').strip().lower()
        if doi:
            if doi in by_doi:
                by_doi[doi] = _merge(by_doi[doi], rec)
            else:
                by_doi[doi] = rec
            continue
        # No DOI — use (title, year)
        key = (_norm_title(rec.get('title', '')), rec.get('year'))
        if key[0]:
            if key in by_title:
                by_title[key] = _merge(by_title[key], rec)
            else:
                by_title[key] = rec
        else:
            no_key.append(rec)

    merged = list(by_doi.values()) + list(by_title.values()) + no_key
    stats = {
        'in':          len(records),
        'unique_by_doi':   len(by_doi),
        'unique_by_title': len(by_title),
        'no_key':      len(no_key),
        'out':         len(merged),
        'duplicates_removed': len(records) - len(merged),
    }
    return merged, stats
