"""
graph_builder.py
----------------
Converts validated and normalised PaperRecord objects into a NetworkX knowledge graph.

Exports to GraphML and JSON-LD formats for downstream exploration.

Usage:
    python -m src.graph_builder --input data/processed/extracted.json --output outputs/graph.graphml
"""

from __future__ import annotations

import json
import sys
import argparse
from pathlib import Path
from typing import List

import networkx as nx

from src.schema import PaperRecord
from src.normalisation import normalise_record


# ---------------------------------------------------------------------------
# Node and edge construction
# ---------------------------------------------------------------------------

def add_node_if_new(G: nx.Graph, node_id: str, **attrs) -> None:
    """Add a node to the graph only if it does not already exist."""
    if node_id not in G:
        G.add_node(node_id, **attrs)


def build_graph_from_records(records: List[PaperRecord], cfg=None) -> nx.DiGraph:
    """
    Build a directed knowledge graph from a list of PaperRecord objects.

    cfg (ZoeConfig | None): controls which normalisation maps are applied.
    If None, all maps are applied (safe default).

    Node types:
        Paper, Species, VocalisationType, BehaviouralContext,
        CommunicationFunction, AnalysisMethod, DatasetResource

    Edge types (stored as 'relation' attribute):
        PAPER_STUDIES_SPECIES
        PAPER_REPORTS_VOCALISATION
        SPECIES_PRODUCES_VOCALISATION
        VOCALISATION_OCCURS_IN_CONTEXT
        VOCALISATION_HAS_FUNCTION
        PAPER_USES_METHOD
        PAPER_LINKS_DATASET
    """
    G = nx.DiGraph()

    for record in records:
        rec = normalise_record(record, cfg=cfg)

        # ── Paper node ──────────────────────────────────────────────
        paper_id = f"paper::{rec.paper_id}"
        add_node_if_new(
            G, paper_id,
            label="Paper",
            title=rec.title,
            year=rec.year or 0,
            paper_id=rec.paper_id,
            communication_domain=rec.communication_domain.value,
            developmental_stage=rec.developmental_stage.value,
            main_outcome=rec.main_outcome,
        )

        # ── Species node ─────────────────────────────────────────────
        species_id = f"species::{rec.species_scientific_name}"
        add_node_if_new(
            G, species_id,
            label="Species",
            common_name=rec.species_common_name,
            scientific_name=rec.species_scientific_name,
            taxonomic_family=rec.taxonomic_family,
        )
        G.add_edge(paper_id, species_id, relation="PAPER_STUDIES_SPECIES")

        # ── Vocalisation type nodes ───────────────────────────────────
        for voc in rec.vocalisation_type:
            voc_id = f"voc::{voc}"
            add_node_if_new(G, voc_id, label="VocalisationType", name=voc)
            G.add_edge(paper_id, voc_id, relation="PAPER_REPORTS_VOCALISATION")
            G.add_edge(species_id, voc_id, relation="SPECIES_PRODUCES_VOCALISATION")

            # ── Behavioural context edges from vocalisation ───────────
            for ctx in rec.behavioural_context:
                ctx_id = f"ctx::{ctx}"
                add_node_if_new(G, ctx_id, label="BehaviouralContext", name=ctx)
                if not G.has_edge(voc_id, ctx_id):
                    G.add_edge(voc_id, ctx_id, relation="VOCALISATION_OCCURS_IN_CONTEXT")

            # ── Function edges from vocalisation ──────────────────────
            for fn in rec.putative_function:
                fn_id = f"fn::{fn}"
                add_node_if_new(G, fn_id, label="CommunicationFunction", name=fn)
                if not G.has_edge(voc_id, fn_id):
                    G.add_edge(voc_id, fn_id, relation="VOCALISATION_HAS_FUNCTION")

        # ── Behavioural context nodes (paper-level, for papers with no voc) ──
        for ctx in rec.behavioural_context:
            ctx_id = f"ctx::{ctx}"
            add_node_if_new(G, ctx_id, label="BehaviouralContext", name=ctx)

        # ── Analysis method nodes ─────────────────────────────────────
        for method in rec.analysis_method:
            method_id = f"method::{method}"
            add_node_if_new(G, method_id, label="AnalysisMethod", name=method)
            G.add_edge(paper_id, method_id, relation="PAPER_USES_METHOD")

        # ── Dataset node ──────────────────────────────────────────────
        if rec.dataset_name:
            dataset_id = f"dataset::{rec.dataset_name}"
            add_node_if_new(
                G, dataset_id,
                label="DatasetResource",
                name=rec.dataset_name,
                availability=rec.dataset_or_recording_available.value,
            )
            G.add_edge(paper_id, dataset_id, relation="PAPER_LINKS_DATASET")

    return G


# ---------------------------------------------------------------------------
# Graph statistics
# ---------------------------------------------------------------------------

def graph_summary(G: nx.DiGraph) -> dict:
    """Return a summary of graph statistics."""
    node_labels = {}
    for _, data in G.nodes(data=True):
        label = data.get("label", "unknown")
        node_labels[label] = node_labels.get(label, 0) + 1

    edge_relations = {}
    for _, _, data in G.edges(data=True):
        rel = data.get("relation", "unknown")
        edge_relations[rel] = edge_relations.get(rel, 0) + 1

    return {
        "total_nodes": G.number_of_nodes(),
        "total_edges": G.number_of_edges(),
        "node_types": node_labels,
        "edge_types": edge_relations,
    }


def print_summary(G: nx.DiGraph) -> None:
    s = graph_summary(G)
    print(f"\n{'='*50}")
    print(f"Zoe.Logos-Graph — Graph Summary")
    print(f"{'='*50}")
    print(f"Nodes: {s['total_nodes']}")
    for label, count in sorted(s["node_types"].items()):
        print(f"  {label:30s} {count}")
    print(f"Edges: {s['total_edges']}")
    for rel, count in sorted(s["edge_types"].items()):
        print(f"  {rel:40s} {count}")
    print(f"{'='*50}\n")


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def export_graphml(G: nx.DiGraph, path: Path) -> None:
    """Export graph to GraphML format (readable by Gephi, Cytoscape, etc.)."""
    nx.write_graphml(G, str(path))
    print(f"GraphML written: {path}")


def export_json(G: nx.DiGraph, path: Path) -> None:
    """Export graph to node-link JSON format."""
    data = nx.node_link_data(G, edges="edges")
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"JSON written: {path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    from src.config import load_config
    parser = argparse.ArgumentParser(description="Build the Zoe.Logos-Graph knowledge graph.")
    parser.add_argument("--input", required=True, help="Path to extracted records JSON file.")
    parser.add_argument("--output", default=None, help="Output GraphML path (overrides config).")
    parser.add_argument("--json", action="store_true", help="Also export JSON node-link file.")
    parser.add_argument("--config", default=None, help="Path to a custom config.yaml.")
    args = parser.parse_args()

    cfg = load_config(args.config)
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = cfg.graph.output_file

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    raw_records = json.loads(input_path.read_text(encoding="utf-8"))
    if isinstance(raw_records, dict):
        raw_records = [raw_records]

    records = [PaperRecord(**r) for r in raw_records]
    print(f"Loaded {len(records)} records.")

    G = build_graph_from_records(records, cfg=cfg)
    print_summary(G)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if cfg.graph.export_graphml:
        export_graphml(G, output_path)

    if args.json or cfg.graph.export_json:
        json_path = output_path.with_suffix(".json")
        export_json(G, json_path)


if __name__ == "__main__":
    main()
