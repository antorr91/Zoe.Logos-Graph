"""
scripts/11_community_detection.py
-----------------------------------
Builds and analyses communities on the species-function knowledge graph.

Creates two types of graphs:
  1. Bipartite: species ↔ (vocalisation | function | context)
  2. Species-species: weighted projection — two species are linked if they
     share vocalisations/functions (weight = number of shared traits)

Runs community detection (Louvain via greedy modularity or label propagation)
and exports:
  data/built/graph_communities.json  — for the web explorer
  data/built/graph_full.json         — full node-link graph

Usage:
    python scripts/11_community_detection.py
    python scripts/11_community_detection.py --weight-by papers  (use paper counts as edge weights)
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.db import get_connection

try:
    import networkx as nx
except ImportError:
    print("pip install networkx")
    sys.exit(1)

OUT_DIR = Path("data/built")


# ── Build bipartite graph ─────────────────────────────────────────────────────

def build_bipartite(con, claim_types=("vocalisation","function","context"), min_evidence=1) -> nx.Graph:
    """
    Nodes: species (type=species) + claims (type=vocalisation/function/context)
    Edges: species → claim, weight = paper evidence count
    """
    G = nx.Graph()

    # Species nodes
    species_rows = con.execute("""
        SELECT s.species_id, s.scientific_name, s.common_name_en,
               s.class_, s.order_, s.family,
               m.image_url, m.conservation_status,
               COUNT(DISTINCT ps.paper_id) AS paper_count
        FROM species s
        LEFT JOIN species_metadata m ON s.species_id = m.species_id
        LEFT JOIN paper_species ps ON s.species_id = ps.species_id
        GROUP BY s.species_id
    """).fetchall()

    for row in species_rows:
        G.add_node(row["species_id"], **{
            "node_type": "species",
            "label": row["common_name_en"] or row["scientific_name"],
            "scientific_name": row["scientific_name"],
            "common_name": row["common_name_en"],
            "class_": row["class_"],
            "order_": row["order_"],
            "family": row["family"],
            "image_url": row["image_url"] or "",
            "conservation": row["conservation_status"] or "",
            "paper_count": row["paper_count"] or 0,
        })

    # Claim nodes + edges — v2 schema via JOIN on vocab tables
    # claim_types maps to: 'vocalisation' → signal_id/signal_terms,
    #                       'context'      → context_id/context_terms,
    #                       'function'     → function_id/function_terms
    TYPE_COL = {
        "vocalisation": ("signal_id",   "signal_terms",   "signal_id",   "canonical_label"),
        "context":      ("context_id",  "context_terms",  "context_id",  "canonical_label"),
        "function":     ("function_id", "function_terms", "function_id", "canonical_label"),
    }

    for ct in claim_types:
        if ct not in TYPE_COL:
            continue
        fk_col, vocab_table, vocab_pk, vocab_label = TYPE_COL[ct]

        rows = con.execute(f"""
            SELECT
                cc.species_id,
                vt.{vocab_label}              AS value,
                AVG(cc.confidence)            AS avg_conf,
                COUNT(DISTINCT ce.paper_id)   AS paper_count,
                MAX(ce.extraction_method)     AS best_source
            FROM communication_claims cc
            JOIN {vocab_table} vt ON cc.{fk_col} = vt.{vocab_pk}
            LEFT JOIN claim_evidence ce ON cc.claim_id = ce.claim_id
            WHERE cc.{fk_col} IS NOT NULL
            GROUP BY cc.species_id, vt.{vocab_label}
            HAVING COUNT(DISTINCT ce.paper_id) >= ?
               OR COUNT(DISTINCT ce.paper_id) = 0
        """, (min_evidence,)).fetchall()

        for row in rows:
            sid    = row["species_id"]
            val    = row["value"] or ""
            if not val:
                continue
            nid    = f"{ct}::{val}"
            weight = max(1, row["paper_count"] or 1)
            conf   = row["avg_conf"] or 0.5
            src    = row["best_source"] or "seed"

            if nid not in G:
                G.add_node(nid, **{
                    "node_type": ct,
                    "label": val,
                    "value": val,
                })

            if sid in G:
                G.add_edge(sid, nid, weight=weight,
                           confidence=round(conf, 2), source=src)

    return G


# ── Species-species projection ────────────────────────────────────────────────

def build_species_projection(bipartite: nx.Graph) -> nx.Graph:
    """
    Project bipartite graph onto species nodes only.
    Two species are connected if they share at least one claim node.
    Edge weight = number of shared claim nodes.
    """
    species_nodes = {n for n, d in bipartite.nodes(data=True) if d.get("node_type") == "species"}
    P = nx.Graph()

    for n in species_nodes:
        P.add_node(n, **bipartite.nodes[n])

    # For each claim node, connect all species that share it
    for n, d in bipartite.nodes(data=True):
        if d.get("node_type") == "species":
            continue
        neighbors = list(bipartite.neighbors(n))
        sp_neighbors = [nb for nb in neighbors if nb in species_nodes]
        for i, a in enumerate(sp_neighbors):
            for b in sp_neighbors[i+1:]:
                if P.has_edge(a, b):
                    P[a][b]["weight"] += 1
                    P[a][b]["shared"].append(d["label"])
                else:
                    P.add_edge(a, b, weight=1, shared=[d["label"]])

    return P


# ── Community detection ───────────────────────────────────────────────────────

def detect_communities(G: nx.Graph) -> dict[str, int]:
    """
    Returns {node_id: community_id}.
    Uses greedy modularity optimisation (works on weighted graphs).
    """
    try:
        from networkx.algorithms.community import greedy_modularity_communities
        communities = greedy_modularity_communities(G, weight="weight")
        result = {}
        for i, community in enumerate(communities):
            for node in community:
                result[node] = i
        return result
    except Exception:
        # Fallback: label propagation
        from networkx.algorithms.community import label_propagation_communities
        communities = list(label_propagation_communities(G))
        result = {}
        for i, community in enumerate(communities):
            for node in community:
                result[i] = i
        return result


# ── Export ────────────────────────────────────────────────────────────────────

COMMUNITY_COLORS = [
    "#e8a427","#2cb88a","#9b8ef0","#5b9cf6","#e85b5b",
    "#4dd4ac","#f97316","#a78bfa","#22d3ee","#84cc16",
    "#fb7185","#60a5fa","#34d399","#fbbf24","#c084fc",
]

CLASS_COLORS = {
    "Aves":          "#e8a427",
    "Mammalia":      "#2cb88a",
    "Amphibia":      "#5b9cf6",
    "Reptilia":      "#9b8ef0",
    "Insecta":       "#fb7185",
    "Actinopterygii":"#60a5fa",
}

VOC_TYPE_COLORS = {
    "vocalisation": "#e8a427",
    "function":     "#9b8ef0",
    "context":      "#2cb88a",
    "method":       "#7a7e8a",
}


def export_graph_json(bipartite: nx.Graph, species_proj: nx.Graph,
                      communities_bip: dict, communities_sp: dict) -> dict:
    """Build the JSON payload for the web graph explorer."""

    nodes = []
    edges = []

    # Bipartite nodes
    for nid, data in bipartite.nodes(data=True):
        nt = data.get("node_type","")
        comm = communities_bip.get(nid, 0)
        color = (CLASS_COLORS.get(data.get("class_",""), COMMUNITY_COLORS[comm % len(COMMUNITY_COLORS)])
                 if nt == "species"
                 else VOC_TYPE_COLORS.get(nt, "#454854"))
        degree = bipartite.degree(nid, weight="weight")
        nodes.append({
            "id":    nid,
            "label": data.get("label", nid),
            "type":  nt,
            "community": comm,
            "color":  color,
            "size":  max(6, min(28, 8 + degree * 1.2)) if nt == "species" else max(5, min(18, 5 + degree)),
            "data":  {k: v for k, v in data.items() if k not in ("label",)},
        })

    # Bipartite edges
    for a, b, d in bipartite.edges(data=True):
        edges.append({
            "source": a, "target": b,
            "weight": d.get("weight", 1),
            "confidence": d.get("confidence", 0.5),
            "source_type": d.get("source", "seed"),
        })

    # Species-projection edges (separate layer)
    sp_edges = []
    for a, b, d in species_proj.edges(data=True):
        sp_edges.append({
            "source": a, "target": b,
            "weight": d.get("weight", 1),
            "shared": d.get("shared", []),
        })

    # Community summaries
    comm_members: dict[int, list] = defaultdict(list)
    for nid, comm in communities_bip.items():
        if bipartite.nodes[nid].get("node_type") == "species":
            comm_members[comm].append(bipartite.nodes[nid].get("label",""))

    # Top shared traits per community
    comm_traits: dict[int, list] = defaultdict(list)
    for nid, comm in communities_bip.items():
        nt = bipartite.nodes[nid].get("node_type","")
        if nt in ("vocalisation","function","context"):
            comm_traits[comm].append(bipartite.nodes[nid].get("label",""))

    communities_summary = []
    for cid in sorted(comm_members.keys()):
        communities_summary.append({
            "id":      cid,
            "color":   COMMUNITY_COLORS[cid % len(COMMUNITY_COLORS)],
            "species": sorted(comm_members[cid])[:12],
            "traits":  sorted(set(comm_traits[cid]))[:8],
            "size":    len(comm_members[cid]),
        })

    return {
        "nodes":        nodes,
        "edges":        edges,
        "sp_edges":     sp_edges,
        "communities":  communities_summary,
        "stats": {
            "n_species":    sum(1 for _, d in bipartite.nodes(data=True) if d.get("node_type")=="species"),
            "n_claims":     sum(1 for _, d in bipartite.nodes(data=True) if d.get("node_type")!="species"),
            "n_edges":      bipartite.number_of_edges(),
            "n_communities": len(communities_summary),
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Build species-function community graph.")
    parser.add_argument("--weight-by", default="evidence", choices=["evidence","uniform"])
    parser.add_argument("--claim-types", nargs="+", default=["vocalisation","function","context"])
    parser.add_argument("--min-evidence", type=int, default=0)
    args = parser.parse_args()

    con = get_connection()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\nBuilding bipartite graph (claims: {args.claim_types})...")
    G_bip = build_bipartite(con, args.claim_types, args.min_evidence)
    print(f"  Nodes: {G_bip.number_of_nodes()} · Edges: {G_bip.number_of_edges()}")

    print("Building species-species projection...")
    G_sp = build_species_projection(G_bip)
    sp_nodes = sum(1 for _, d in G_sp.nodes(data=True) if d.get("node_type")=="species")
    print(f"  Species nodes: {sp_nodes} · Edges: {G_sp.number_of_edges()}")

    print("Detecting communities (bipartite)...")
    communities_bip = detect_communities(G_bip)
    n_comm = len(set(communities_bip.values()))
    print(f"  {n_comm} communities found")

    print("Detecting communities (species projection)...")
    communities_sp = detect_communities(G_sp) if G_sp.number_of_edges() > 0 else {}

    print("Exporting graph JSON...")
    payload = export_graph_json(G_bip, G_sp, communities_bip, communities_sp)

    out_path = OUT_DIR / "graph_communities.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"✓ {out_path}  ({out_path.stat().st_size // 1024} KB)")

    # Also export GraphML
    nx.write_graphml(G_bip, str(OUT_DIR / "graph_bipartite.graphml"))
    # Convert list attributes to strings for GraphML compatibility
    G_sp_gml = G_sp.copy()
    for u, v, d in G_sp_gml.edges(data=True):
        if "shared" in d and isinstance(d["shared"], list):
            d["shared"] = "|".join(d["shared"])
    nx.write_graphml(G_sp_gml, str(OUT_DIR / "graph_species.graphml"))
    print(f"✓ GraphML: graph_bipartite.graphml, graph_species.graphml")

    print(f"\nCommunity summary:")
    for c in payload["communities"][:8]:
        print(f"  Community {c['id']} ({c['size']} species): {', '.join(c['species'][:4])}{'…' if len(c['species'])>4 else ''}")
        print(f"    traits: {', '.join(c['traits'][:4])}")

    print(f"\n✓ Done. Run python -m http.server 8000 and open web/graph_explorer.html\n")


if __name__ == "__main__":
    main()