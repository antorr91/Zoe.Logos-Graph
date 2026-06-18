"""
tests/test_normalisation.py
---------------------------
Tests for config-driven normalisation behaviour.

Key property under test: normalisation maps can be individually
disabled via ZoeConfig, and disabling them must actually affect
the output — both in normalise_record() and in build_graph_from_records().
"""

import pytest
from src.schema import PaperRecord
from src.config import ZoeConfig, NormalisationConfig
from src.normalisation import (
    normalise_record,
    normalise_vocalisation,
    normalise_context,
    normalise_common_name,
)
from src.graph_builder import build_graph_from_records
from src.validation import validate_record


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_record(**overrides) -> PaperRecord:
    base = {
        "paper_id": "norm_test_001",
        "title": "Test",
        "year": 2023,
        "species_common_name": "european starling",
        "species_scientific_name": "Sturnus vulgaris",
        "taxonomic_family": "Sturnidae",
        "developmental_stage": "adult",
        "communication_domain": "vocal",
        "vocalisation_type": ["songs"],        # plural — should normalise to "song"
        "behavioural_context": ["feeding"],    # alias — should normalise to "foraging"
        "putative_function": ["mate attraction"],
        "analysis_method": ["ANOVA"],
        "main_outcome": "Songs vary with context.",
        "dataset_or_recording_available": "no",
        "dataset_name": None,
        "notes_uncertainty": None,
    }
    base.update(overrides)
    record, errors = validate_record(base)
    assert record is not None, f"Fixture failed: {errors}"
    return record


def cfg_with(**flags) -> ZoeConfig:
    """Build a ZoeConfig with specific normalisation flags."""
    return ZoeConfig(normalisation=NormalisationConfig(**flags))


# ---------------------------------------------------------------------------
# Unit tests — normalise_record with cfg
# ---------------------------------------------------------------------------

def test_vocalisation_map_on():
    record = make_record()
    cfg = cfg_with(apply_vocalisation_map=True, apply_context_map=True, apply_species_map=True)
    result = normalise_record(record, cfg=cfg)
    assert "song" in result.vocalisation_type
    assert "songs" not in result.vocalisation_type


def test_vocalisation_map_off():
    record = make_record()
    cfg = cfg_with(apply_vocalisation_map=False, apply_context_map=True, apply_species_map=True)
    result = normalise_record(record, cfg=cfg)
    # With map off, "songs" must stay as-is
    assert "songs" in result.vocalisation_type
    assert "song" not in result.vocalisation_type


def test_context_map_on():
    record = make_record()
    cfg = cfg_with(apply_vocalisation_map=True, apply_context_map=True, apply_species_map=True)
    result = normalise_record(record, cfg=cfg)
    assert "foraging" in result.behavioural_context
    assert "feeding" not in result.behavioural_context


def test_context_map_off():
    record = make_record()
    cfg = cfg_with(apply_vocalisation_map=True, apply_context_map=False, apply_species_map=True)
    result = normalise_record(record, cfg=cfg)
    assert "feeding" in result.behavioural_context
    assert "foraging" not in result.behavioural_context


def test_species_map_on():
    record = make_record(species_common_name="starling")
    cfg = cfg_with(apply_species_map=True, apply_vocalisation_map=True, apply_context_map=True)
    result = normalise_record(record, cfg=cfg)
    assert result.species_common_name == "european starling"


def test_species_map_off():
    record = make_record(species_common_name="starling")
    cfg = cfg_with(apply_species_map=False, apply_vocalisation_map=True, apply_context_map=True)
    result = normalise_record(record, cfg=cfg)
    assert result.species_common_name == "starling"


def test_all_maps_off_leaves_input_unchanged():
    record = make_record()
    cfg = cfg_with(apply_species_map=False, apply_vocalisation_map=False, apply_context_map=False)
    result = normalise_record(record, cfg=cfg)
    assert "songs" in result.vocalisation_type
    assert "feeding" in result.behavioural_context


def test_none_cfg_applies_all_maps():
    """cfg=None is the safe default — all maps must be applied."""
    record = make_record()
    result = normalise_record(record, cfg=None)
    assert "song" in result.vocalisation_type
    assert "foraging" in result.behavioural_context


# ---------------------------------------------------------------------------
# Integration test — cfg flows through build_graph_from_records
# ---------------------------------------------------------------------------

def test_graph_respects_vocalisation_map_off():
    """
    With apply_vocalisation_map=False, 'songs' must appear as a node,
    not the normalised 'song'.
    """
    record = make_record()
    cfg = cfg_with(apply_vocalisation_map=False, apply_context_map=True, apply_species_map=True)
    G = build_graph_from_records([record], cfg=cfg)

    voc_nodes = {d["name"] for _, d in G.nodes(data=True) if d.get("label") == "VocalisationType"}
    assert "songs" in voc_nodes, "Expected raw 'songs' in graph when map is off"
    assert "song" not in voc_nodes, "Normalised 'song' should not appear when map is off"


def test_graph_respects_vocalisation_map_on():
    record = make_record()
    cfg = cfg_with(apply_vocalisation_map=True, apply_context_map=True, apply_species_map=True)
    G = build_graph_from_records([record], cfg=cfg)

    voc_nodes = {d["name"] for _, d in G.nodes(data=True) if d.get("label") == "VocalisationType"}
    assert "song" in voc_nodes
    assert "songs" not in voc_nodes
