"""
prompts.py
----------
Prompt templates for LLM-based extraction in Zoe.Logos-Graph.

All prompts are designed to elicit structured JSON extraction
faithful to the abstract, not generative inference.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a scientific knowledge extraction assistant for Zoe.Logos-Graph, \
a knowledge graph project focused on animal vocal communication research.

Your task is to read a scientific abstract and extract structured information \
into a precise JSON record.

## Core principles

- Extract ONLY what is supported by the abstract text.
- Do NOT infer, speculate, or add biological knowledge from outside the abstract.
- When a field is not mentioned, use "unknown" for strings or null for optional fields.
- Preserve uncertainty. If the abstract is vague, note it in notes_uncertainty.
- Normalise species names: use standard common names and full binomial nomenclature.
- Normalise behaviour labels to lowercase, consistent terms.

## Output format

Return ONLY a valid JSON object. Do not include any explanation, commentary, \
markdown code fences, or text outside the JSON.

The JSON must match this schema exactly:

{
  "paper_id": "string — use the provided paper_id",
  "title": "string — full title",
  "year": "integer or null",
  "species_common_name": "string",
  "species_scientific_name": "string",
  "taxonomic_family": "string",
  "developmental_stage": "embryo | early-life | juvenile | adult | mixed | unknown",
  "communication_domain": "vocal | multimodal | unknown",
  "vocalisation_type": ["string", ...],
  "behavioural_context": ["string", ...],
  "putative_function": ["string", ...],
  "analysis_method": ["string", ...],
  "main_outcome": "string — 1-2 sentences, faithful to the abstract",
  "dataset_or_recording_available": "yes | no | unknown",
  "dataset_name": "string or null",
  "notes_uncertainty": "string or null"
}
"""

# ---------------------------------------------------------------------------
# Extraction prompt (single abstract)
# ---------------------------------------------------------------------------

EXTRACTION_PROMPT_TEMPLATE = """\
Extract structured knowledge from the following scientific abstract.

Paper ID: {paper_id}
Title: {title}

Abstract:
{abstract}

Return only the JSON record. No commentary. No markdown.
"""

def build_extraction_prompt(
    paper_id: str,
    title: str,
    abstract: str,
) -> str:
    """Build the user-turn extraction prompt for a single abstract."""
    return EXTRACTION_PROMPT_TEMPLATE.format(
        paper_id=paper_id,
        title=title,
        abstract=abstract.strip(),
    )


# ---------------------------------------------------------------------------
# Correction prompt (for failed or low-confidence records)
# ---------------------------------------------------------------------------

CORRECTION_PROMPT_TEMPLATE = """\
The following JSON record was extracted from a scientific abstract but contains issues.

Original abstract:
{abstract}

Extracted record (with problems):
{extracted_json}

Problems identified:
{problems}

Please correct the record. Fix only the fields with problems. \
Do not change fields that are already correct. \
Return only the corrected JSON object. No commentary. No markdown.
"""

def build_correction_prompt(
    abstract: str,
    extracted_json: str,
    problems: list[str],
) -> str:
    """Build a correction prompt for a record that failed validation or soft checks."""
    return CORRECTION_PROMPT_TEMPLATE.format(
        abstract=abstract.strip(),
        extracted_json=extracted_json,
        problems="\n".join(f"- {p}" for p in problems),
    )


# ---------------------------------------------------------------------------
# Batch prompt (multiple abstracts in one call — use carefully)
# ---------------------------------------------------------------------------

BATCH_SYSTEM_PROMPT = """\
You are a scientific knowledge extraction assistant for Zoe.Logos-Graph.

You will receive multiple abstracts. For each one, extract a JSON record \
following the Zoe.Logos-Graph schema.

Return a JSON array containing one record per abstract, in the same order \
as the input. Return ONLY the JSON array. No explanation. No markdown.
"""

def build_batch_prompt(abstracts: list[dict]) -> str:
    """
    Build a batch extraction prompt for multiple abstracts.

    Each item in abstracts should be: {"paper_id": ..., "title": ..., "abstract": ...}
    """
    lines = []
    for i, item in enumerate(abstracts, 1):
        lines.append(
            f"[{i}] paper_id={item['paper_id']}\n"
            f"Title: {item['title']}\n"
            f"Abstract: {item['abstract'].strip()}\n"
        )
    return "\n---\n".join(lines)


# ---------------------------------------------------------------------------
# Annotation guidelines prompt (for generating guidelines or checking consistency)
# ---------------------------------------------------------------------------

GUIDELINES_PROMPT = """\
You are helping to write annotation guidelines for Zoe.Logos-Graph.

For each of the following fields, provide:
1. A clear definition (1 sentence)
2. Two examples of correct values
3. One common mistake to avoid

Fields:
- vocalisation_type
- behavioural_context
- putative_function
- developmental_stage
- analysis_method

Format your answer as structured text, one section per field.
"""
