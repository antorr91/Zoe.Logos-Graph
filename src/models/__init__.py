"""
src/models/__init__.py
-----------------------
Public API for the Zoe.Logos model layer (v2).

Exposes all Pydantic models from the four schema modules.
Import from here, not from individual modules:

    from src.models import Taxon, CommunicationClaim, SignalTerm, RecordingAsset
"""

from .schema_taxonomy import Taxon, TaxonRank, TaxonomicStatus
from .schema_signals import (
    SignalTerm,
    ContextTerm,
    FunctionTerm,
    MethodTerm,
    SignalModality,
    AcousticDescriptor,
)
from .schema_evidence import (
    CommunicationClaim,
    ClaimEvidence,
    ExtractedClaimItem,
    PaperExtractionResult,
    CurationStatus,
    SupportLevel,
    ExtractionMethod,
)
from .schema_recordings import RecordingAsset, RecordingProvider, QualityGrade
from .schema_annotations import SignalAnnotation
from .schema_topics import ResearchTopicTerm

__all__ = [
    # Taxonomy
    "Taxon", "TaxonRank", "TaxonomicStatus",
    # Signals
    "SignalTerm", "ContextTerm", "FunctionTerm", "MethodTerm",
    "SignalModality", "AcousticDescriptor",
    # Evidence
    "CommunicationClaim", "ClaimEvidence",
    "ExtractedClaimItem", "PaperExtractionResult",
    "CurationStatus", "SupportLevel", "ExtractionMethod",
    # Recordings
    "RecordingAsset", "RecordingProvider", "QualityGrade",
    # Annotations
    "SignalAnnotation",
    # Research topics
    "ResearchTopicTerm",
]
