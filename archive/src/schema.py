"""
schema.py
---------
Pydantic schema for a single extracted paper record in Zoe.Logos-Graph.

Each record represents the structured knowledge extracted from one scientific abstract.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class DevelopmentalStage(str, Enum):
    embryo = "embryo"
    early_life = "early-life"
    juvenile = "juvenile"
    adult = "adult"
    mixed = "mixed"
    unknown = "unknown"


class CommunicationDomain(str, Enum):
    vocal = "vocal"
    multimodal = "multimodal"
    unknown = "unknown"


class DatasetAvailability(str, Enum):
    yes = "yes"
    no = "no"
    unknown = "unknown"


# ---------------------------------------------------------------------------
# Main record schema
# ---------------------------------------------------------------------------

class PaperRecord(BaseModel):
    """
    Structured knowledge record extracted from a single scientific abstract.

    Annotation principles:
    - Extract only what is supported by the abstract.
    - Prefer explicit statements over inferred interpretations.
    - Preserve uncertainty when the abstract is vague.
    - Normalise species names and behaviour terms where possible.
    - Keep main_outcome short and faithful to the paper.
    """

    paper_id: str = Field(
        ...,
        description="Unique identifier for this paper (e.g. 'paper_001' or a DOI slug).",
        examples=["paper_001", "10.1234_jeb.2024.001"],
    )

    title: str = Field(
        ...,
        description="Full title of the paper as given in the abstract or metadata.",
    )

    year: Optional[int] = Field(
        None,
        description="Publication year. Null if not stated.",
        ge=1900,
        le=2100,
    )

    species_common_name: str = Field(
        ...,
        description="Common name of the focal species (e.g. 'zebra finch'). "
                    "Use 'multiple species' if comparative. Use 'unknown' if not stated.",
    )

    species_scientific_name: str = Field(
        ...,
        description="Binomial scientific name (e.g. 'Taeniopygia guttata'). "
                    "Use 'unknown' if not stated.",
    )

    taxonomic_family: str = Field(
        ...,
        description="Taxonomic family of the focal species (e.g. 'Estrildidae'). "
                    "Use 'unknown' if not stated.",
    )

    developmental_stage: DevelopmentalStage = Field(
        DevelopmentalStage.unknown,
        description="Developmental stage of the subjects studied.",
    )

    communication_domain: CommunicationDomain = Field(
        CommunicationDomain.unknown,
        description="Primary communication modality studied.",
    )

    vocalisation_type: List[str] = Field(
        default_factory=list,
        description="Types of vocalisation described (e.g. ['contact call', 'alarm call', 'song']). "
                    "Normalise to consistent lowercase terms.",
        examples=[["contact call", "alarm call"], ["song"]],
    )

    behavioural_context: List[str] = Field(
        default_factory=list,
        description="Contexts in which vocalisation occurs "
                    "(e.g. ['foraging', 'parent-offspring interaction', 'predator response']).",
    )

    putative_function: List[str] = Field(
        default_factory=list,
        description="Communicative functions attributed to the vocalisation in the abstract "
                    "(e.g. ['mate attraction', 'individual recognition', 'cohesion']).",
    )

    analysis_method: List[str] = Field(
        default_factory=list,
        description="Analytical or computational methods used "
                    "(e.g. ['spectrogram analysis', 'UMAP', 'hidden Markov model']).",
    )

    main_outcome: str = Field(
        ...,
        description="One or two sentences summarising the main finding, "
                    "faithful to the abstract. Do not add interpretation.",
    )

    dataset_or_recording_available: DatasetAvailability = Field(
        DatasetAvailability.unknown,
        description="Whether a dataset or audio recording is stated to be publicly available.",
    )

    dataset_name: Optional[str] = Field(
        None,
        description="Name or identifier of the dataset if mentioned (e.g. 'xeno-canto', 'NIST 2023'). "
                    "Null otherwise.",
    )

    notes_uncertainty: Optional[str] = Field(
        None,
        description="Free-text notes on uncertainty, ambiguity, or caveats in extraction. "
                    "Use when the abstract is vague or fields required inference.",
    )

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------

    @model_validator(mode="after")
    def dataset_name_requires_availability_yes(self) -> "PaperRecord":
        """If dataset_name is set, availability must be 'yes' — not 'no' or 'unknown'."""
        if self.dataset_name and self.dataset_or_recording_available != DatasetAvailability.yes:
            raise ValueError(
                f"dataset_name is '{self.dataset_name}' but dataset_or_recording_available "
                f"is '{self.dataset_or_recording_available.value}'. "
                "Must be 'yes' when a dataset name is provided."
            )
        return self

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def to_graph_nodes(self) -> dict:
        """
        Return a dict of node dictionaries for graph construction.
        Keys: 'paper', 'species', 'vocalisation_types', 'behavioural_contexts',
              'functions', 'methods', 'dataset'.
        """
        return {
            "paper": {
                "id": self.paper_id,
                "label": "Paper",
                "title": self.title,
                "year": self.year,
            },
            "species": {
                "id": f"species::{self.species_scientific_name}",
                "label": "Species",
                "common_name": self.species_common_name,
                "scientific_name": self.species_scientific_name,
                "taxonomic_family": self.taxonomic_family,
            },
            "vocalisation_types": [
                {"id": f"voc::{v}", "label": "VocalisationType", "name": v}
                for v in self.vocalisation_type
            ],
            "behavioural_contexts": [
                {"id": f"ctx::{c}", "label": "BehaviouralContext", "name": c}
                for c in self.behavioural_context
            ],
            "functions": [
                {"id": f"fn::{f}", "label": "CommunicationFunction", "name": f}
                for f in self.putative_function
            ],
            "methods": [
                {"id": f"method::{m}", "label": "AnalysisMethod", "name": m}
                for m in self.analysis_method
            ],
            "dataset": {
                "id": f"dataset::{self.dataset_name}",
                "label": "DatasetResource",
                "name": self.dataset_name,
            } if self.dataset_name else None,
        }


# ---------------------------------------------------------------------------
# Example record (matches the spec)
# ---------------------------------------------------------------------------

EXAMPLE_RECORD = PaperRecord(
    paper_id="paper_001",
    title="Exploratory analysis of early-life chick calls",
    year=2024,
    species_common_name="domestic chick",
    species_scientific_name="Gallus gallus domesticus",
    taxonomic_family="Phasianidae",
    developmental_stage=DevelopmentalStage.early_life,
    communication_domain=CommunicationDomain.vocal,
    vocalisation_type=["calls"],
    behavioural_context=["early social communication"],
    putative_function=["social signalling"],
    analysis_method=["computational acoustic analysis"],
    main_outcome="Early-life calls show structured acoustic variation.",
    dataset_or_recording_available=DatasetAvailability.unknown,
    dataset_name=None,
    notes_uncertainty=None,
)
