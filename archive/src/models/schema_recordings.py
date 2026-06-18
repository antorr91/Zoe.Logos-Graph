"""
src/models/schema_recordings.py
---------------------------------
Pydantic model for the bioacoustic recording layer of Zoe.Logos.

Aligned with TDWG Audiovisual Core (AC):
  https://www.tdwg.org/standards/ac/

A RecordingAsset represents a single audio recording (or spectrogram)
from an external provider such as xeno-canto, Macaulay Library,
BioAcoustica, or a custom dataset.

Key design decisions:
  - provider + provider_recording_id uniquely identify the upstream asset.
  - license is stored verbatim (CC-BY-4.0, ML proprietary, etc.).
  - taxon_id links to the Taxon layer (mandatory).
  - claim_id optionally links to a CommunicationClaim (when the recording
    directly supports or illustrates a specific claim).
  - quality_grade uses xeno-canto conventions as defaults (A–E).
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class RecordingProvider(str, Enum):
    xeno_canto      = "xeno-canto"
    macaulay        = "macaulay"
    bioacoustica    = "bioacoustica"
    freesound       = "freesound"
    gbif_media      = "gbif_media"
    open_ecoacoustics = "open_ecoacoustics"
    custom          = "custom"
    unknown         = "unknown"


class QualityGrade(str, Enum):
    """xeno-canto quality grades, extended for other providers."""
    A = "A"  # highest
    B = "B"
    C = "C"
    D = "D"
    E = "E"  # lowest
    unknown = "unknown"


# ---------------------------------------------------------------------------
# RecordingAsset
# ---------------------------------------------------------------------------

class RecordingAsset(BaseModel):
    """
    A bioacoustic recording or multimedia asset.

    Follows TDWG Audiovisual Core conventions for metadata fields.
    External providers are identified by RecordingProvider enum values.

    Licensing note:
      - xeno-canto: most recordings are CC-licensed; check individual records.
      - Macaulay Library: high-resolution assets require a licensing agreement
        for commercial use; standard playback is open.
      - BioAcoustica: recordings are licensed individually by contributors.
      - Always store the license string and attribution; never assume free reuse.
    """

    # ── Identity ─────────────────────────────────────────────────────────────
    recording_id:           Optional[str] = Field(
        None,
        description="Internal ID. Format: '<provider>:<provider_recording_id>'. "
                    "Auto-generated if not provided.",
    )
    provider:               RecordingProvider = Field(
        ...,
        description="Audio provider (AC: dcterms:source / provider).",
    )
    provider_recording_id:  Optional[str] = Field(
        None,
        description="ID within the provider's system (e.g. xeno-canto XC number).",
        examples=["XC12345"],
    )

    # ── Taxon link ───────────────────────────────────────────────────────────
    taxon_id:               str = Field(
        ...,
        description="FK to species.species_id. Format: 'gbif:<usageKey>'.",
    )
    scientific_name_raw:    Optional[str] = Field(
        None,
        description="Scientific name as stated by the provider (may differ from canonical).",
    )

    # ── Claim link (optional) ────────────────────────────────────────────────
    claim_id:               Optional[int] = Field(
        None,
        description="FK to communication_claims.claim_id. "
                    "Set when this recording directly supports or illustrates a claim.",
    )

    # ── URLs ──────────────────────────────────────────────────────────────────
    url:                    str = Field(
        ...,
        description="Canonical page URL for this recording (AC: dc:identifier / landingPage).",
    )
    audio_url:              Optional[str] = Field(
        None,
        description="Direct URL to the audio file (AC: ac:accessURI).",
    )
    spectrogram_url:        Optional[str] = Field(
        None,
        description="URL to a spectrogram image (AC: ac:thumbnailAccessURI).",
    )

    # ── Rights & attribution ─────────────────────────────────────────────────
    license:                Optional[str] = Field(
        None,
        description="License identifier (AC: dcterms:license). E.g. 'CC-BY-4.0'.",
    )
    rights_holder:          Optional[str] = Field(
        None,
        description="Rights holder name (AC: dcterms:rightsHolder).",
    )
    attribution:            Optional[str] = Field(
        None,
        description="Full attribution string for display (AC: ac:attributionLinkURL / credit).",
    )

    # ── Recording classification ──────────────────────────────────────────────
    recording_type:         Optional[str] = Field(
        None,
        description="Type of recording as stated by the provider "
                    "(e.g. 'song', 'call', 'alarm call'). NOT normalised to SignalTerm here.",
    )
    quality_grade:          QualityGrade = Field(
        QualityGrade.unknown,
        description="Quality grade (AC: ac:dataQuality). Uses xeno-canto A–E by default.",
    )

    # ── Provenance / field metadata ───────────────────────────────────────────
    location:               Optional[str] = Field(
        None,
        description="Recording location as string (AC: dcterms:Location / verbatimLocality).",
    )
    latitude:               Optional[float] = Field(None, ge=-90.0, le=90.0)
    longitude:              Optional[float] = Field(None, ge=-180.0, le=180.0)
    recorded_date:          Optional[str] = Field(
        None,
        description="Recording date as ISO 8601 string (AC: dcterms:date).",
    )
    recorded_by:            Optional[str] = Field(
        None,
        description="Name of the recordist (AC: dcterms:creator).",
    )

    # ── Technical metadata ────────────────────────────────────────────────────
    duration_s:             Optional[float] = Field(None, description="Duration in seconds.")
    sample_rate_hz:         Optional[int]   = Field(None, description="Sample rate in Hz.")
    bit_depth:              Optional[int]   = Field(None, description="Bit depth (8, 16, 24).")
    file_format:            Optional[str]   = Field(None, description="File format (e.g. 'mp3', 'wav', 'flac').")

    fetched_at:             Optional[str]   = Field(None, description="ISO 8601 fetch timestamp.")

    model_config = ConfigDict(use_enum_values=True)
