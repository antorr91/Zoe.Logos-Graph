"""Multi-factor relevance scoring.

score(paper) = w1·keyword_overlap + w2·influence + w3·journal_quality
             + w4·recency_bonus + w5·species_match_bonus
"""
from __future__ import annotations
import math, re
from datetime import datetime

# Keyword pool that signals bioacoustic relevance
KEYWORDS = {
    'vocal',          'vocalisation',  'vocalization', 'call',     'calls',
    'song',           'singing',       'acoustic',     'sound',    'auditory',
    'communication',  'signal',        'signalling',   'signaling',
    'echolocation',   'bioacoustic',   'bioacoustics', 'duet',     'chorus',
    'alarm',          'mating',        'territorial',  'syntax',   'dialect',
    'learning',       'imitation',     'mimicry',      'repertoire',
    'playback',       'spectrogram',   'frequency',    'pitch',
    'social',         'recognition',   'individual',
}

# Heuristic journal quality buckets (Scimago Q1 vibe by venue substring)
# Not a perfect SCImago mapping, but a sensible practical proxy for our domain.
TOP_VENUE_SUBSTRINGS = {
    'nature',                          'science',
    'pnas',                            'proc. natl. acad. sci.',
    'proceedings of the national',     'current biology',
    'proceedings of the royal society','proc. r. soc. b',
    'nature communications',           'plos biology',
    'elife',                           'science advances',
    'annual review',                   'cell ',
    'trends in ecology',               'trends in cognitive',
    'journal of neuroscience',         'neuron',
    'philosophical transactions',
}
GOOD_VENUE_SUBSTRINGS = {
    'animal behaviour',                'behavioral ecology',
    'behavioural ecology',             'behavioral ecology and sociobiology',
    'animal cognition',                'journal of experimental biology',
    'biology letters',                 'bioacoustics',
    'frontiers in',                    'plos one',
    'scientific reports',              'communications biology',
    'journal of the acoustical society','journal of comparative physiology',
    'journal of zoology',              'ecology letters',
    'molecular ecology',               'evolution',
    'ethology',                        'auk',
    'ibis',                            'condor',
    'biological journal of the linnean',
    'royal society open',              'methods in ecology',
}


def _keyword_overlap(rec: dict) -> int:
    text = (rec.get('title', '') + ' ' + rec.get('abstract', '')).lower()
    return sum(1 for kw in KEYWORDS if kw in text)


def _journal_quality_score(venue: str) -> float:
    v = (venue or '').lower()
    if not v:
        return 0.0
    for s in TOP_VENUE_SUBSTRINGS:
        if s in v:
            return 3.0
    for s in GOOD_VENUE_SUBSTRINGS:
        if s in v:
            return 2.0
    return 1.0   # other journals still get a baseline


def _species_match_bonus(rec: dict) -> float:
    """Bonus if the target species is explicitly named in title or abstract."""
    target = (rec.get('target_species') or '').lower()
    if not target:
        return 0.0
    text = (rec.get('title', '') + ' ' + rec.get('abstract', '')).lower()
    if target in text:
        return 3.0       # explicit binomial: strong signal
    # Also accept genus-only mention
    genus = target.split()[0] if ' ' in target else target
    if genus and (' ' + genus + ' ' in ' ' + text + ' '):
        return 1.0
    return 0.0


def _recency_bonus(year: int | None) -> float:
    if not year:
        return 0.0
    now = datetime.now().year
    age = max(0, now - year)
    # Bell curve: peak at 0-5 years; classics (high cited) get bonus
    if age <= 5:   return 1.5
    if age <= 10:  return 1.0
    if age <= 20:  return 0.5
    return 0.2


def _influence(rec: dict) -> float:
    # Log-scaled citation count, capped — log keeps very-old super-cited papers
    # from dominating without giving them nothing
    cited = rec.get('cited_by') or 0
    infl = rec.get('influential') or 0
    return math.log10(max(1, cited)) + 0.5 * math.log10(max(1, infl) + 1)


def score_paper(rec: dict) -> float:
    s_kw   = _keyword_overlap(rec)              # 0..N
    s_inf  = _influence(rec)                    # 0..~5
    s_jq   = _journal_quality_score(rec.get('venue', ''))
    s_rec  = _recency_bonus(rec.get('year'))
    s_sp   = _species_match_bonus(rec)
    # Weights chosen so the four signals balance for typical papers
    score = (1.0 * s_kw + 2.5 * s_inf + 2.0 * s_jq +
             1.5 * s_rec + 3.0 * s_sp)
    return round(score, 3)


def rank_papers(records: list[dict]) -> list[dict]:
    for r in records:
        r['score'] = score_paper(r)
    records.sort(key=lambda r: -r.get('score', 0))
    return records


def quota_for_species(n_available: int) -> int:
    """Variable quota: more papers for well-studied species."""
    if n_available >= 50: return 15      # 'famous'
    if n_available >= 15: return 8       # 'well-studied'
    if n_available >= 5:  return 5       # 'moderate'
    return n_available                   # 'niche': take all
