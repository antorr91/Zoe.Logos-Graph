"""LLM-based structured extraction using the Anthropic API.

Batches 3 papers per call to balance cost and field-attribution accuracy.
Uses Claude Sonnet (claude-sonnet-4-5 by default).

Requires ANTHROPIC_API_KEY environment variable.
"""
from __future__ import annotations
import os, json, time, re, urllib.request
from .schema import EXTRACTION_SCHEMA, THEMES, STUDY_TYPES, RELEVANCE_LEVELS

API_URL = 'https://api.anthropic.com/v1/messages'
DEFAULT_MODEL = 'claude-sonnet-4-5-20250929'

SYSTEM_PROMPT = (
    "You are an academic literature analyst specialising in bioacoustics "
    "and animal communication. You extract structured information from "
    "research paper abstracts. You respond ONLY with valid JSON, no "
    "additional text. You strictly follow the requested schema. You are "
    "honest about uncertainty: if the abstract does not contain information "
    "for a field, you leave it as empty string or empty array."
)

EXTRACTION_PROMPT = """You will receive {n} research paper abstracts about animal vocal communication.
For EACH paper, produce a JSON object following this schema EXACTLY:

{schema}

Important rules:
1. Output a JSON array of {n} objects, in the SAME ORDER as the input papers.
2. "species_studied" must contain ONLY species the paper actually investigates, NOT every species mentioned in passing.
3. Pick "themes" only from the controlled vocabulary listed in the schema; an empty array is acceptable if none clearly applies.
4. "confidence" reflects how sure you are given the abstract. Use 0.3 if the abstract is too vague to extract; 0.6 for typical abstracts; 0.9 only when the abstract gives very clear methods+findings.
5. If a paper is NOT about animal vocal communication / bioacoustics of the target species, set "relevance": "low".

Papers to analyse (target species: {target}):

{papers}

Respond with ONLY the JSON array, no markdown fences, no explanation."""


def _api_call(messages: list, model: str = DEFAULT_MODEL,
              api_key: str = '', max_tokens: int = 4096) -> dict:
    """Single API call, returns the parsed response dict."""
    if not api_key:
        raise RuntimeError('ANTHROPIC_API_KEY not set')
    body = {
        'model': model,
        'max_tokens': max_tokens,
        'system': SYSTEM_PROMPT,
        'messages': messages,
    }
    data = json.dumps(body).encode('utf-8')
    req = urllib.request.Request(
        API_URL,
        data=data,
        headers={
            'Content-Type':      'application/json',
            'x-api-key':         api_key,
            'anthropic-version': '2023-06-01',
        },
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode('utf-8'))


def _parse_array(text: str) -> list[dict]:
    """Extract a JSON array from the LLM response, robust to extra text."""
    # Strip code fences if any
    t = re.sub(r'^```(?:json)?\s*', '', text.strip(), flags=re.IGNORECASE)
    t = re.sub(r'\s*```$', '', t)
    # Find the outermost array
    start = t.find('[')
    end = t.rfind(']')
    if start < 0 or end < 0 or end <= start:
        return []
    try:
        return json.loads(t[start:end + 1])
    except json.JSONDecodeError:
        # Try to repair common issues
        try:
            return json.loads(t[start:end + 1].replace(',\n]', '\n]')
                              .replace(',]', ']'))
        except Exception:
            return []


def _validate_one(obj: dict) -> dict:
    """Clamp and sanitize an extracted record to the schema."""
    out = {
        'research_question':       (obj.get('research_question') or '').strip(),
        'species_studied':         [s for s in obj.get('species_studied', [])
                                    if isinstance(s, str) and s.strip()],
        'methods_recording_type':  (obj.get('methods_recording_type') or '').strip(),
        'methods_sample_size':     (obj.get('methods_sample_size') or '').strip(),
        'methods_setting':         (obj.get('methods_setting') or '').strip(),
        'methods_analysis':        (obj.get('methods_analysis') or '').strip(),
        'key_findings':            (obj.get('key_findings') or '').strip(),
        'implications':            (obj.get('implications') or '').strip(),
        'limitations':             (obj.get('limitations') or '').strip(),
        'themes':                  [t for t in obj.get('themes', []) if t in THEMES],
        'study_type':              (obj.get('study_type') or '').strip().lower(),
        'relevance':               (obj.get('relevance') or '').strip().lower(),
        'confidence':              max(0.0, min(1.0,
                                                float(obj.get('confidence') or 0))),
    }
    if out['study_type'] not in STUDY_TYPES:
        out['study_type'] = 'other'
    if out['relevance'] not in RELEVANCE_LEVELS:
        out['relevance'] = 'medium'
    return out


class LLMExtractor:
    def __init__(self, api_key: str | None = None, model: str = DEFAULT_MODEL,
                 batch_size: int = 3, max_retries: int = 2):
        self.api_key = api_key or os.environ.get('ANTHROPIC_API_KEY', '')
        self.model = model
        self.batch_size = batch_size
        self.max_retries = max_retries
        # Stats
        self.total_calls = 0
        self.total_in_tokens = 0
        self.total_out_tokens = 0

    def _format_papers(self, papers: list[dict]) -> str:
        blocks = []
        for i, p in enumerate(papers, 1):
            title = p.get('title', '').strip()
            abstract = p.get('abstract', '').strip()
            blocks.append(
                f'--- Paper {i} ---\nTitle: {title}\nAbstract: {abstract}\n'
            )
        return '\n'.join(blocks)

    def extract_batch(self, papers: list[dict], target_species: str) -> list[dict]:
        """Process up to batch_size papers in one LLM call."""
        if not papers:
            return []
        prompt = EXTRACTION_PROMPT.format(
            n=len(papers),
            schema=EXTRACTION_SCHEMA,
            target=target_species,
            papers=self._format_papers(papers),
        )
        for attempt in range(self.max_retries + 1):
            try:
                resp = _api_call(
                    [{'role': 'user', 'content': prompt}],
                    model=self.model, api_key=self.api_key)
                self.total_calls += 1
                u = resp.get('usage', {})
                self.total_in_tokens  += u.get('input_tokens',  0)
                self.total_out_tokens += u.get('output_tokens', 0)
                # Extract text content
                content = resp.get('content', [])
                text = ''.join(blk.get('text', '') for blk in content
                               if blk.get('type') == 'text')
                arr = _parse_array(text)
                if len(arr) == len(papers):
                    return [_validate_one(o) for o in arr]
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)
                    continue
                # Give up: return as much as we got, pad with low-confidence empties
                out = [_validate_one(o) for o in arr]
                while len(out) < len(papers):
                    out.append(_validate_one({'confidence': 0.0,
                                              'relevance': 'low'}))
                return out
            except Exception as e:
                if attempt < self.max_retries:
                    time.sleep(2 ** (attempt + 1))
                    continue
                # Total failure: return low-confidence placeholders
                return [_validate_one({'confidence': 0.0,
                                       'relevance': 'low'})
                        for _ in papers]
        return [_validate_one({}) for _ in papers]

    def extract_all(self, papers: list[dict], target_species: str,
                    progress_cb=None) -> list[dict]:
        """Process all papers in batches, returning enriched records.
        Combines original metadata with LLM-extracted fields."""
        out = []
        for i in range(0, len(papers), self.batch_size):
            chunk = papers[i:i + self.batch_size]
            enriched = self.extract_batch(chunk, target_species)
            for orig, llm in zip(chunk, enriched):
                merged = dict(orig)
                merged.update(llm)        # LLM fields override placeholders
                out.append(merged)
            if progress_cb:
                progress_cb(min(i + self.batch_size, len(papers)), len(papers))
        return out

    def stats(self) -> dict:
        # Sonnet 4.5 pricing (USD per million tokens, indicative)
        cost_in = self.total_in_tokens  * 3.00 / 1_000_000
        cost_out = self.total_out_tokens * 15.00 / 1_000_000
        return {
            'calls':       self.total_calls,
            'in_tokens':   self.total_in_tokens,
            'out_tokens':  self.total_out_tokens,
            'cost_usd':    round(cost_in + cost_out, 4),
        }
