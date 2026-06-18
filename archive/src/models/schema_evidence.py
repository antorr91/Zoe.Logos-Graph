"""
src/models/schema_evidence.py
------------------------------
Pydantic models for the evidence layer of Zoe.Logos.

A CommunicationClaim is the central knowledge unit of Zoe.Logos.
It links a taxon to a signal type, context, and function —
backed by a traceable piece of evidence from a paper or recording.

Design principles:
  - Every claim must have evidence_text (the source sentence or passage).
  - Claims are never bare assertions: they are always attributed.
  - Confidence and curation_status distinguish machine-extracted from curated.
  - A single paper may support multiple claims.
  - Multiple evidence items can support a single claim (via ClaimEvidence).

Curation tiers:
  'seed'        — initial manual entry, no paper backing  (confidence: 0.4–0.6)
  'extracted'   — LLM extraction from abstract            (confidence: 0.5–0.85)
  'curated'     — human-reviewed                          (confidence: 0.9–1.0)
  'recording'   — derived from annotated audio recording  (varies)
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class CurationStatus(str, Enum):
    seed        = "seed"
    extracted   = "extracted"
    curated     = "curated"
    recording   = "recording"
    rejected    = "rejected"


class SupportLevel(str, Enum):
    """How explicitly does the source support the claim?"""
    explicit    = "explicit"    # source directly states the claim
    implicit    = "implicit"    # claim is a reasonable inference from context
    uncertain   = "uncertain"   # source is ambiguous


class ExtractionMethod(str, Enum):
    llm_abstract    = "llm_abstract"    # LLM from abstract
    llm_fulltext    = "llm_fulltext"    # LLM from full text
    manual          = "manual"          # manually entered by curator
    recording_annotation = "recording_annotation"  # from audio annotation


# ---------------------------------------------------------------------------
# ClaimEvidence — one piece of evidence supporting a claim
# ---------------------------------------------------------------------------

class ClaimEvidence(BaseModel):
    """
    A single evidence item supporting a CommunicationClaim.

    One claim can have multiple evidence items (e.g. from different papers).
    The evidence_text MUST be present; it is the primary traceability mechanism.
    """

    evidence_id:        Optional[int] = Field(None, description="DB autoincrement ID.")

    claim_id:           Optional[int] = Field(None, description="FK to CommunicationClaim.claim_id.")

    paper_id:           Optional[str] = Field(
        None,
        description="FK to papers.paper_id. Null only for recording-derived evidence.",
    )
    recording_id:       Optional[str] = Field(
        None,
        description="FK to media_assets.recording_id. Null for paper-derived evidence.",
    )

    evidence_text:      str = Field(
        ...,
        description="The source sentence or passage that supports the claim. REQUIRED.",
        min_length=5,
    )
    support_level:      SupportLevel = Field(
        SupportLevel.uncertain,
        description="How explicitly does the source text support the claim?",
    )
    extraction_method:  ExtractionMethod = Field(
        ExtractionMethod.llm_abstract,
    )
    confidence:         float = Field(
        0.5,
        description="Confidence in this evidence item (0.0–1.0).",
        ge=0.0, le=1.0,
    )
    extraction_version: str = Field(
        "0.2",
        description="Version of the extraction pipeline that produced this record.",
    )

    model_config = ConfigDict(use_enum_values=True)


# ---------------------------------------------------------------------------
# CommunicationClaim — the central knowledge unit
# ---------------------------------------------------------------------------

class CommunicationClaim(BaseModel):
    """
    A claim that a taxon produces a signal type in a context for a function.

    This is the core node of the Zoe.Logos knowledge graph.
    Each claim is backed by one or more ClaimEvidence items.

    Key design decisions:
    - signal_id, context_id, function_id reference controlled vocabulary terms.
    - evidence_items must have at least one entry for extracted/curated claims.
    - curation_status governs how the claim is displayed in the UI.
    """

    # ── Identity ────────────────────────────────────────────────────────────
    claim_id:           Optional[int] = Field(None, description="DB autoincrement PK.")

    # ── Core claim ──────────────────────────────────────────────────────────
    taxon_id:           str = Field(
        ...,
        description="FK to species.species_id. Format: 'gbif:<usageKey>'.",
    )
    signal_id:          Optional[str] = Field(
        None,
        description="FK to signal_terms.signal_id. Format: 'signal:<slug>'.",
    )
    context_id:         Optional[str] = Field(
        None,
        description="FK to context_terms.context_id. Format: 'context:<slug>'.",
    )
    function_id:        Optional[str] = Field(
        None,
        description="FK to function_terms.function_id. Format: 'fn:<slug>'.",
    )
    method_id:          Optional[str] = Field(
        None,
        description="FK to method_terms.method_id. Format: 'method:<slug>'.",
    )

    # ── Biological qualifiers ────────────────────────────────────────────────
    life_stage:         Optional[str] = Field(
        None,
        description="Life stage of focal subjects (DwC: lifeStage). E.g. 'juvenile', 'adult'.",
    )

    # ── Summary ─────────────────────────────────────────────────────────────
    main_outcome:       Optional[str] = Field(
        None,
        description="1–2 sentence summary of the paper's main finding for this claim.",
    )

    # ── Provenance ──────────────────────────────────────────────────────────
    curation_status:    CurationStatus = Field(
        CurationStatus.extracted,
    )
    aggregate_confidence: float = Field(
        0.5,
        description="Aggregate confidence across all evidence items (0.0–1.0).",
        ge=0.0, le=1.0,
    )

    # ── Evidence ────────────────────────────────────────────────────────────
    evidence_items:     list[ClaimEvidence] = Field(
        default_factory=list,
        description="Evidence items supporting this claim. Should not be empty for extracted/curated.",
    )

    # ── Free-text fallback (legacy compatibility) ────────────────────────────
    signal_label_raw:   Optional[str] = Field(
        None,
        description="Raw signal label from extraction (before vocabulary normalisation).",
    )
    context_label_raw:  Optional[str] = Field(
        None,
        description="Raw context label from extraction.",
    )
    function_label_raw: Optional[str] = Field(
        None,
        description="Raw function label from extraction.",
    )

    # ── Validators ──────────────────────────────────────────────────────────
    @model_validator(mode="after")
    def extracted_claims_need_evidence(self) -> "CommunicationClaim":
        """Extracted and curated claims must have at least one evidence item."""
        if self.curation_status in (CurationStatus.extracted, CurationStatus.curated):
            if not self.evidence_items:
                raise ValueError(
                    f"CommunicationClaim with curation_status='{self.curation_status}' "
                    "must have at least one evidence item with evidence_text."
                )
        return self

    model_config = ConfigDict(use_enum_values=True)


# ---------------------------------------------------------------------------
# Structured extraction schema (used in LLM prompts)
# ---------------------------------------------------------------------------

class ExtractedClaimItem(BaseModel):
    """
    One structured claim extracted from a single abstract by the LLM.

    Raw labels are normalised to controlled vocabulary IDs post-extraction.
    Species names are extracted as-written; GBIF resolution happens in claim_ingest.
    """
    signal:         Optional[str] = Field(None, description="Signal type as written in source.")
    context:        Optional[str] = Field(None, description="Behavioural context as written in source.")
    function:       Optional[str] = Field(
        None,
        description="Communicative function — ONLY if explicitly stated. Never inferred from context.",
    )
    method:         Optional[str] = Field(None, description="Analysis method as written in source.")
    topic:          Optional[str] = Field(None, description="Research topic or cognitive phenomenon.")
    life_stage:     Optional[str] = Field(None)
    evidence_text:  str           = Field(..., min_length=5,
                                          description="Source sentence supporting this claim. REQUIRED.")
    support_level:  str           = Field("uncertain",
                                          description="'explicit' | 'implicit' | 'uncertain'")
    confidence:     float         = Field(0.5, ge=0.0, le=1.0)


class PaperExtractionResult(BaseModel):
    """
    Full extraction result for one paper: metadata + structured claims.

    This replaces PaperRecord as the primary extraction output in v2.
    PaperRecord is kept for backward compatibility with existing tests.
    """
    paper_id:       str
    title:          str
    year:           Optional[int]   = None
    doi:            Optional[str]   = None

    # ── Taxonomy (possibly multi-species) ───────────────────────────────────
    species: list[dict] = Field(
        default_factory=list,
        description="List of {scientific_name, common_name} dicts for all focal taxa.",
    )

    # ── Claims ──────────────────────────────────────────────────────────────
    claims: list[ExtractedClaimItem] = Field(
        default_factory=list,
        description="Structured claims extracted from the abstract.",
    )

    # ── Paper-level metadata ─────────────────────────────────────────────────
    main_outcome:               Optional[str] = None
    dataset_or_recording_available: str = "unknown"
    dataset_name:               Optional[str] = None
    notes_uncertainty:          Optional[str] = None
