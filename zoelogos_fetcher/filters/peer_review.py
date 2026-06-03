"""Hard filter to keep only true peer-reviewed papers.

Excludes:
  - Preprints (arXiv, bioRxiv, SSRN, OSF, Research Square, ChemRxiv...)
  - Editorial / letter / comment / retraction / erratum / book review
  - Conference proceedings (kept if they appear as journal articles, but
    flagged separately)
  - Papers without DOI AND without PMID (impossible to verify)
  - Papers without abstract (impossible to extract methods/findings)
"""
from __future__ import annotations

# Known preprint hosts (DOI prefixes or venue substrings)
PREPRINT_DOI_PREFIXES = (
    '10.1101/',         # bioRxiv, medRxiv
    '10.48550/',        # arXiv
    '10.21203/',        # Research Square
    '10.31219/',        # OSF Preprints
    '10.26434/',        # ChemRxiv
    '10.20944/',        # Preprints.org
    '10.31234/',        # PsyArXiv
    '10.31222/',        # EarthArXiv
    '10.2139/',         # SSRN
    '10.31235/',        # SocArXiv
    '10.32942/',        # EcoEvoRxiv
)

PREPRINT_VENUE_SUBSTRINGS = {
    'arxiv', 'biorxiv', 'medrxiv', 'ssrn', 'research square',
    'preprints.org', 'osf preprints', 'chemrxiv', 'psyarxiv',
    'eartharxiv', 'ecoevorxiv', 'authorea', 'figshare', 'zenodo',
    'researchgate', 'preprint server',
}

# Publication types we exclude (substring match, case insensitive)
EXCLUDE_PUB_TYPES = {
    'editorial', 'letter', 'comment', 'erratum', 'retraction',
    'retracted publication', 'corrected and republished article',
    'published erratum', 'book review', 'news', 'biography', 'obituary',
    'historical article', 'autobiography', 'addresses', 'congresses',
    'preprint', 'review of reported cases',
}


def _is_preprint(rec: dict) -> bool:
    doi = (rec.get('doi') or '').lower()
    for pre in PREPRINT_DOI_PREFIXES:
        if doi.startswith(pre):
            return True
    venue = (rec.get('venue') or '').lower()
    for sub in PREPRINT_VENUE_SUBSTRINGS:
        if sub in venue:
            return True
    # If venue type explicitly says preprint
    if 'preprint' in (rec.get('venue_type') or '').lower():
        return True
    # Semantic Scholar marks preprints in pub_types sometimes
    pts = [p.lower() for p in (rec.get('pub_types') or [])]
    if 'preprint' in pts:
        return True
    return False


def _is_excluded_type(rec: dict) -> bool:
    pts = [(p or '').lower() for p in (rec.get('pub_types') or [])]
    wt = (rec.get('work_type') or '').lower()
    # Build the search pool
    fields = pts + [wt]
    for f in fields:
        for bad in EXCLUDE_PUB_TYPES:
            if bad in f:
                return True
    return False


def _has_minimal_metadata(rec: dict) -> bool:
    """Need at least DOI or PMID, plus a title and abstract."""
    has_id = bool(rec.get('doi')) or bool(rec.get('pmid'))
    has_title = bool((rec.get('title') or '').strip())
    has_abst = len((rec.get('abstract') or '').strip()) >= 80
    return has_id and has_title and has_abst


def filter_peer_review(records: list[dict]) -> tuple[list[dict], dict]:
    """Apply all peer-review filters. Returns (kept, stats)."""
    kept = []
    stats = {'in': len(records), 'no_metadata': 0, 'preprint': 0,
             'excluded_type': 0, 'kept': 0}
    for rec in records:
        if not _has_minimal_metadata(rec):
            stats['no_metadata'] += 1
            continue
        if _is_preprint(rec):
            stats['preprint'] += 1
            continue
        if _is_excluded_type(rec):
            stats['excluded_type'] += 1
            continue
        kept.append(rec)
    stats['kept'] = len(kept)
    return kept, stats
