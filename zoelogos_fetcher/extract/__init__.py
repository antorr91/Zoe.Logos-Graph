"""LLM-based structured extraction (Elicit-style)."""
from .schema      import ExtractedPaper, EXTRACTION_SCHEMA
from .llm         import LLMExtractor

__all__ = ['ExtractedPaper', 'EXTRACTION_SCHEMA', 'LLMExtractor']
