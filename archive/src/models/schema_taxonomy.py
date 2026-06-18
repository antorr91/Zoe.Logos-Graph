"""
src/models/schema_taxonomy.py
------------------------------
Pydantic model for the taxonomic backbone of Zoe.Logos.

Aligns with Darwin Core (DwC) term conventions:
  https://dwc.tdwg.org/terms/

A Taxon is the canonical identity node for a species or taxon.
It holds GBIF-resolved taxonomy and multilingual common names.
The DB primary key is species_id (e.g. "gbif:2493440").
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class TaxonRank(str, Enum):
    kingdom     = "KINGDOM"
    phylum      = "PHYLUM"
    class_      = "CLASS"
    order       = "ORDER"
    family      = "FAMILY"
    genus       = "GENUS"
    species     = "SPECIES"
    subspecies  = "SUBSPECIES"
    variety     = "VARIETY"
    unknown     = "UNKNOWN"


class TaxonomicStatus(str, Enum):
    accepted    = "ACCEPTED"
    synonym     = "SYNONYM"
    doubtful    = "DOUBTFUL"
    unknown     = "UNKNOWN"


class Taxon(BaseModel):
    """
    Canonical taxonomic record for a species or higher taxon.

    Follows Darwin Core conventions for field names and values.
    species_id is the internal primary key (format: "gbif:<usageKey>").
    """

    # ── Identity ────────────────────────────────────────────────────────────
    species_id: str = Field(
        ...,
        description="Internal PK. Format: 'gbif:<usageKey>' (e.g. 'gbif:2493440').",
        examples=["gbif:2493440"],
    )
    gbif_usage_key: Optional[int] = Field(
        None,
        description="GBIF species usage key from the GBIF Checklist Bank.",
    )

    # ── Scientific nomenclature ──────────────────────────────────────────────
    scientific_name: str = Field(
        ...,
        description="Full scientific name with authorship (DwC: scientificName).",
        examples=["Taeniopygia guttata (Vieillot, 1817)"],
    )
    canonical_name: str = Field(
        ...,
        description="Binomial name without authorship (DwC: canonicalName).",
        examples=["Taeniopygia guttata"],
    )
    taxon_rank: TaxonRank = Field(
        TaxonRank.unknown,
        description="Rank of this taxon (DwC: taxonRank).",
    )
    taxonomic_status: TaxonomicStatus = Field(
        TaxonomicStatus.unknown,
        description="Accepted, synonym, doubtful (DwC: taxonomicStatus).",
    )

    # ── Higher classification ────────────────────────────────────────────────
    kingdom:    Optional[str] = Field(None, description="DwC: kingdom.")
    phylum:     Optional[str] = Field(None, description="DwC: phylum.")
    class_name: Optional[str] = Field(None, description="DwC: class.")
    order:      Optional[str] = Field(None, description="DwC: order.")
    family:     Optional[str] = Field(None, description="DwC: family.")
    genus:      Optional[str] = Field(None, description="DwC: genus.")

    # ── Hierarchy ────────────────────────────────────────────────────────────
    parent_taxon_id: Optional[str] = Field(
        None,
        description="species_id of the parent taxon in the GBIF backbone.",
    )

    # ── Common names (multilingual) ──────────────────────────────────────────
    common_name_en: str = Field("", description="Common name — English.")
    common_name_it: str = Field("", description="Common name — Italian.")
    common_name_es: str = Field("", description="Common name — Spanish.")
    common_name_fr: str = Field("", description="Common name — French.")
    common_name_de: str = Field("", description="Common name — German.")

    # ── External links / match metadata ────────────────────────────────────
    gbif_match_confidence: int = Field(
        0,
        description="GBIF match confidence score (0–100).",
        ge=0, le=100,
    )
    gbif_match_status: str = Field("UNKNOWN", description="GBIF match status string.")
    wiki_title: str = Field("", description="Wikipedia article title.")
    xeno_canto_query: str = Field("", description="Default xeno-canto search query for this taxon.")
    inat_id: Optional[int] = Field(None, description="iNaturalist taxon ID.")
    conservation_status: str = Field("", description="IUCN conservation status (e.g. 'LC', 'VU').")

    # ── Profile completeness ────────────────────────────────────────────────
    profile_level: str = Field(
        "basic",
        description="Completeness tier: 'basic' | 'enriched' | 'evidence_backed'.",
    )

    model_config = ConfigDict(use_enum_values=True)
