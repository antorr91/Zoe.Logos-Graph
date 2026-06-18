"""
scripts/05_build_graph.py
--------------------------
Step 5 of the Zoe.Logos-Graph build pipeline.

Reads built species pages + pilot annotations and rebuilds the knowledge graph,
then exports to data/built/graph.graphml and data/built/graph.json.

The web/graph.html reads data/built/graph.json directly.

Usage:
    python scripts/05_build_graph.py

Requires:
    data/built/species_index.json
    data/built/species/<id>.json files
    data/annotations/pilot.json         (optional)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.schema import PaperRecord
from src.validation import validate_record
from src.normalisation import normalise_record
from src.graph_builder import build_graph_from_records, graph_summary, export_graphml, export_json
from src.config import load_config

PILOT_PATH  = Path("data/annotations/pilot.json")
BUILT_DIR   = Path("data/built")
OUTPUT_GML  = Path("data/built/graph.graphml")
OUTPUT_JSON = Path("data/built/graph.json")


def main():
    cfg = load_config()
    BUILT_DIR.mkdir(parents=True, exist_ok=True)

    if not PILOT_PATH.exists():
        print("No pilot.json found — nothing to build graph from.")
        sys.exit(0)

    raw_records = json.loads(PILOT_PATH.read_text(encoding="utf-8"))
    records = []
    errors  = []

    print(f"\nLoading {len(raw_records)} pilot records...")
    for raw in raw_records:
        record, errs = validate_record(raw)
        if record:
            records.append(normalise_record(record, cfg=cfg))
        else:
            errors.append({"id": raw.get("paper_id"), "errors": errs})
            print(f"  ✗  {raw.get('paper_id')}: {errs}")

    print(f"  Valid: {len(records)}  Errors: {len(errors)}\n")

    G = build_graph_from_records(records, cfg=cfg)
    s = graph_summary(G)

    print(f"Graph summary:")
    print(f"  Nodes: {s['total_nodes']}")
    for label, count in sorted(s['node_types'].items()):
        print(f"    {label:30s} {count}")
    print(f"  Edges: {s['total_edges']}")
    for rel, count in sorted(s['edge_types'].items()):
        print(f"    {rel:40s} {count}")

    export_graphml(G, OUTPUT_GML)
    export_json(G, OUTPUT_JSON)
    print(f"\nGraph written to {BUILT_DIR}/\n")


if __name__ == "__main__":
    main()
