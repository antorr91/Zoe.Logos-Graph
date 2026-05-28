"""
src/models/schema_annotations.py
----------------------------------
Pydantic model for timed signal annotations within audio recordings.

Conceptual distinction (critical for bioacousticians):

  RecordingAsset   = the audio FILE (full recording, any duration)
  SignalAnnotation = a TIMED SEGMENT within that file, labelled as a signal
  CommunicationClaim = a SCIENTIFIC ASSERTION backed by paper or annotation

A single RecordingAsset can contain:
  - multiple signal annotations (different species, call types, time slots)
  - overlapping or adjacent segments
  - annotations at different confidence levels
  - annotations from different annotators or protocols

This model is aligned with:
  - Raven annotation format (start_time, end_time, low_freq, high_freq)
  - TDWG Audiovisual Core (for the linking fields)
  - BioAcoustica annotation conventions
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SignalAnnotation(BaseModel):
    """
    A timed, labelled segment within an audio recording.

    The signal_id references a controlled vocabulary term (signal_terms table).
    If the raw label cannot be normalised, signal_label_raw is populated
    and a vocab_suggestion is queued for curator review.

    Time fields follow Raven conventions (seconds from recording start).
    Frequency fields are in Hz.
    """

    model_config = ConfigDict(use_enum_values=True)

    # ── Identity ─────────────────────────────────────────────────────────────
    annotation_id:      Optional[int] = Field(
        None,
        description="DB autoincrement PK.",
    )
    recording_id:       str = Field(
        ...,
        description="FK to media_assets.recording_id (or xc_id for xeno-canto).",
    )

    # ── Taxon link ────────────────────────────────────────────────────────────
    taxon_id:           Optional[str] = Field(
        None,
        description="FK to species.species_id. Null if taxon is uncertain.",
    )
    taxon_label_raw:    Optional[str] = Field(
        None,
        description="Species name as written by the annotator (before GBIF resolution).",
    )

    # ── Signal classification ─────────────────────────────────────────────────
    signal_id:          Optional[str] = Field(
        None,
        description="FK to signal_terms.signal_id. Null if not yet normalised.",
    )
    signal_label_raw:   Optional[str] = Field(
        None,
        description="Signal label as written by the annotator (before vocab normalisation).",
    )

    # ── Temporal extent (Raven-compatible) ────────────────────────────────────
    start_time_s:       float = Field(
        ...,
        description="Annotation start time in seconds from recording start.",
        ge=0.0,
    )
    end_time_s:         float = Field(
        ...,
        description="Annotation end time in seconds from recording start.",
        ge=0.0,
    )

    # ── Frequency extent (Hz) ─────────────────────────────────────────────────
    low_freq_hz:        Optional[float] = Field(
        None,
        description="Lower frequency bound of the annotated segment in Hz.",
        ge=0.0,
    )
    high_freq_hz:       Optional[float] = Field(
        None,
        description="Upper frequency bound of the annotated segment in Hz.",
        ge=0.0,
    )

    # ── Annotation provenance ─────────────────────────────────────────────────
    annotator:          Optional[str] = Field(
        None,
        description="Name or ID of the human or automated annotator.",
    )
    annotation_protocol: Optional[str] = Field(
        None,
        description="Protocol or tool used for annotation (e.g. 'Raven Pro 1.6', 'BirdNET').",
    )
    is_automated:       bool = Field(
        False,
        description="True if produced by an automated detector rather than a human.",
    )

    # ── Quality ───────────────────────────────────────────────────────────────
    confidence:         float = Field(
        0.5,
        description="Confidence in signal label assignment (0.0–1.0).",
        ge=0.0, le=1.0,
    )
    curation_status:    str = Field(
        "extracted",
        description="'extracted' | 'curated' | 'rejected'. "
                    "Extracted = automated; curated = human-verified.",
    )

    # ── Optional link to a CommunicationClaim ────────────────────────────────
    claim_id:           Optional[int] = Field(
        None,
        description="FK to claims_v2.claim_id. Set when this annotation directly "
                    "supports a scientific claim.",
    )

    # ── Validators ───────────────────────────────────────────────────────────
    @model_validator(mode="after")
    def end_after_start(self) -> "SignalAnnotation":
        if self.end_time_s <= self.start_time_s:
            raise ValueError(
                f"end_time_s ({self.end_time_s}) must be greater than "
                f"start_time_s ({self.start_time_s})."
            )
        return self

    @model_validator(mode="after")
    def freq_range_valid(self) -> "SignalAnnotation":
        if self.low_freq_hz is not None and self.high_freq_hz is not None:
            if self.high_freq_hz <= self.low_freq_hz:
                raise ValueError(
                    f"high_freq_hz ({self.high_freq_hz}) must be greater than "
                    f"low_freq_hz ({self.low_freq_hz})."
                )
        return self

    @property
    def duration_s(self) -> float:
        """Duration of the annotated segment in seconds."""
        return self.end_time_s - self.start_time_s
