"""
src/models/schema_signals.py
-----------------------------
Pydantic models for the communication vocabulary layer of Zoe.Logos.

This layer defines a small ontology of signal types, modalities,
behavioural contexts, communicative functions, and analysis methods.
Each term is a controlled vocabulary entry, not a free-text string.

Hierarchy:
  Modality → SignalFamily → SignalType → SignalSubtype

Relationships:
  Taxon ── has_signal ──► SignalTerm
  SignalTerm ── occurs_in ──► Context
  SignalTerm ── has_function ──► Function

Term IDs use the format: "<namespace>:<slug>"
  e.g. "signal:alarm_call", "context:predator_response", "fn:mate_attraction"
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class SignalModality(str, Enum):
    acoustic    = "acoustic"
    visual      = "visual"
    chemical    = "chemical"
    tactile     = "tactile"
    multimodal  = "multimodal"
    unknown     = "unknown"


class AcousticDescriptor(str, Enum):
    tonal       = "tonal"
    broadband   = "broadband"
    pulsed      = "pulsed"
    ultrasonic  = "ultrasonic"
    infrasonic  = "infrasonic"
    harmonic    = "harmonic"
    noisy       = "noisy"
    mixed       = "mixed"
    unknown     = "unknown"


# ---------------------------------------------------------------------------
# Core vocabulary models
# ---------------------------------------------------------------------------

class SignalTerm(BaseModel):
    """
    A controlled vocabulary entry for a signal type (call, song, click, etc.).

    Organised as a hierarchy: signal families contain signal types,
    which may contain subtypes. Aliases ensure that variant spellings
    from literature map to a single canonical term.

    Loaded from data/vocab/signal_terms.yaml.
    """

    signal_id: str = Field(
        ...,
        description="Unique term ID. Format: 'signal:<slug>' (e.g. 'signal:alarm_call').",
        examples=["signal:alarm_call"],
    )
    canonical_label: str = Field(
        ...,
        description="Canonical English label used in the DB and UI.",
        examples=["alarm call"],
    )
    modality: SignalModality = Field(
        SignalModality.unknown,
        description="Primary sensory modality of this signal.",
    )
    parent_signal_id: Optional[str] = Field(
        None,
        description="ID of the parent SignalTerm (for hierarchical browsing).",
        examples=["signal:call"],
    )
    aliases: list[str] = Field(
        default_factory=list,
        description="Variant spellings and synonyms that normalise to this term.",
        examples=[["alarm vocalisation", "alarm vocalization", "anti-predator call"]],
    )
    definition: Optional[str] = Field(
        None,
        description="Short definition (1–2 sentences). Sourced from the literature.",
    )
    scope_note: Optional[str] = Field(
        None,
        description="Annotation guidance for curators and the extraction prompt.",
        examples=["Use only when the source explicitly describes alarm, predator, or threat context."],
    )
    acoustic_descriptor: Optional[AcousticDescriptor] = Field(
        None,
        description="Primary acoustic descriptor (for acoustic signals only).",
    )

    model_config = ConfigDict(use_enum_values=True)


class ContextTerm(BaseModel):
    """
    A controlled vocabulary entry for a behavioural / ethological context.

    Examples: 'courtship', 'predator_response', 'parent_offspring_interaction'.

    Loaded from data/vocab/context_terms.yaml.
    """

    context_id: str = Field(
        ...,
        description="Unique term ID. Format: 'context:<slug>'.",
        examples=["context:predator_response"],
    )
    canonical_label: str = Field(
        ...,
        description="Canonical English label.",
        examples=["predator response"],
    )
    aliases: list[str] = Field(
        default_factory=list,
        description="Variant labels that normalise to this term.",
    )
    definition: Optional[str] = Field(None)
    scope_note: Optional[str] = Field(None)
    parent_context_id: Optional[str] = Field(None)


class FunctionTerm(BaseModel):
    """
    A controlled vocabulary entry for a communicative function.

    Examples: 'mate_attraction', 'group_cohesion', 'predator_warning'.

    Loaded from data/vocab/function_terms.yaml.
    """

    function_id: str = Field(
        ...,
        description="Unique term ID. Format: 'fn:<slug>'.",
        examples=["fn:mate_attraction"],
    )
    canonical_label: str = Field(
        ...,
        description="Canonical English label.",
        examples=["mate attraction"],
    )
    aliases: list[str] = Field(
        default_factory=list,
    )
    definition: Optional[str] = Field(None)
    scope_note: Optional[str] = Field(None)
    parent_function_id: Optional[str] = Field(None)


class MethodTerm(BaseModel):
    """
    A controlled vocabulary entry for an analysis or experimental method.

    Examples: 'spectrogram_analysis', 'hidden_markov_model', 'playback_experiment'.

    Loaded from data/vocab/method_terms.yaml.
    """

    method_id: str = Field(
        ...,
        description="Unique term ID. Format: 'method:<slug>'.",
        examples=["method:spectrogram_analysis"],
    )
    canonical_label: str = Field(
        ...,
        description="Canonical English label.",
        examples=["spectrogram analysis"],
    )
    aliases: list[str] = Field(default_factory=list)
    definition: Optional[str] = Field(None)
    method_category: Optional[str] = Field(
        None,
        description="Broad category: 'acoustic', 'statistical', 'behavioural', 'computational', 'neural'.",
    )
