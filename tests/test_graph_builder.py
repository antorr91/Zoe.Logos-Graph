"""
tests/test_graph_builder.py
---------------------------
Tests for the knowledge graph construction layer.
"""

import json
import pytest
from pathlib import Path

import networkx as nx

from src.schema import PaperRecord
from src.validation import validate_record
from src.graph_builder import build_graph_from_records, graph_summary


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

RAW_RECORDS = [
    {
        "paper_id": "paper_g01",
        "title": "Song learning in zebra finches",
        "year": 2021,
        "species_common_name": "zebra finch",
        "species_scientific_name": "Taeniopygia guttata",
        "taxonomic_family": "Estrildidae",
        "developmental_stage": "juvenile",
        "communication_domain": "vocal",
        "vocalisation_type": ["song", "subsong"],
        "behavioural_context": ["vocal learning", "courtship"],
        "putative_function": ["mate attraction"],
        "analysis_method": ["ANOVA", "spectrogram analysis"],
        "main_outcome": "Social feedback accelerates song crystallisation.",
        "dataset_or_recording_available": "yes",
        "dataset_name": "OSF_Test_001",
        "notes_uncertainty": None,
    },
    {
        "paper_id": "paper_g02",
        "title": "Alarm calls in vervet monkeys",
        "year": 2019,
        "species_common_name": "vervet monkey",
        "species_scientific_name": "Chlorocebus pygerythrus",
        "taxonomic_family": "Cercopithecidae",
        "developmental_stage": "adult",
        "communication_domain": "vocal",
        "vocalisation_type": ["alarm call"],
        "behavioural_context": ["predator response"],
        "putative_function": ["predator warning"],
        "analysis_method": ["spectrogram analysis", "playback experiment"],
        "main_outcome": "Calls differ acoustically by predator class.",
        "dataset_or_recording_available": "no",
        "dataset_name": None,
        "notes_uncertainty": None,
    },
]


@pytest.fixture
def records():
    result = []
    for raw in RAW_RECORDS:
        record, errors = validate_record(raw)
        assert record is not None, f"Fixture validation failed: {errors}"
        result.append(record)
    return result


@pytest.fixture
def graph(records):
    return build_graph_from_records(records)


# ---------------------------------------------------------------------------
# Graph structure tests
# ---------------------------------------------------------------------------

def test_graph_is_directed(graph):
    assert isinstance(graph, nx.DiGraph)


def test_paper_nodes_present(graph):
    paper_nodes = [n for n, d in graph.nodes(data=True) if d.get("label") == "Paper"]
    assert len(paper_nodes) == 2


def test_species_nodes_present(graph):
    species_nodes = [n for n, d in graph.nodes(data=True) if d.get("label") == "Species"]
    assert len(species_nodes) == 2


def test_vocalisation_nodes_present(graph):
    voc_nodes = [n for n, d in graph.nodes(data=True) if d.get("label") == "VocalisationType"]
    # song, subsong, alarm call
    assert len(voc_nodes) == 3


def test_dataset_node_only_for_available(graph):
    dataset_nodes = [n for n, d in graph.nodes(data=True) if d.get("label") == "DatasetResource"]
    # Only paper_g01 has a dataset
    assert len(dataset_nodes) == 1


def test_paper_studies_species_edges(graph):
    edges = [(u, v) for u, v, d in graph.edges(data=True)
             if d.get("relation") == "PAPER_STUDIES_SPECIES"]
    assert len(edges) == 2


def test_paper_links_dataset_edges(graph):
    edges = [(u, v) for u, v, d in graph.edges(data=True)
             if d.get("relation") == "PAPER_LINKS_DATASET"]
    assert len(edges) == 1


def test_vocalisation_has_function_edges(graph):
    edges = [(u, v) for u, v, d in graph.edges(data=True)
             if d.get("relation") == "VOCALISATION_HAS_FUNCTION"]
    assert len(edges) >= 2


def test_no_duplicate_nodes(graph):
    """Shared method nodes (spectrogram analysis) should appear once."""
    method_nodes = [n for n, d in graph.nodes(data=True)
                    if d.get("label") == "AnalysisMethod" and d.get("name") == "spectrogram analysis"]
    assert len(method_nodes) == 1


# ---------------------------------------------------------------------------
# Graph summary
# ---------------------------------------------------------------------------

def test_summary_structure(graph):
    s = graph_summary(graph)
    assert "total_nodes" in s
    assert "total_edges" in s
    assert "node_types" in s
    assert "edge_types" in s
    assert s["total_nodes"] > 0
    assert s["total_edges"] > 0


# ---------------------------------------------------------------------------
# Pilot dataset regression test
# ---------------------------------------------------------------------------

def test_pilot_graph_builds():
    """Build graph from all 10 gold pilot records without error."""
    pilot_path = Path("data/annotations/pilot.json")
    if not pilot_path.exists():
        pytest.skip("Pilot dataset not found.")

    raw_records = json.loads(pilot_path.read_text())
    records = []
    for raw in raw_records:
        record, errors = validate_record(raw)
        assert record is not None, f"{raw.get('paper_id')} failed validation: {errors}"
        records.append(record)

    G = build_graph_from_records(records)
    s = graph_summary(G)
    assert s["total_nodes"] > 10
    assert s["total_edges"] > 10
    assert "Paper" in s["node_types"]
    assert s["node_types"]["Paper"] == 10
