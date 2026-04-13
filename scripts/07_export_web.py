"""
scripts/07_export_web.py
-------------------------
Export the SQLite database to JSON files for the web frontend.

Writes:
  data/built/species_index.json        — lightweight grid index
  data/built/species/<id>.json         — full species detail pages

The frontend (web/species.html) reads only these files.
The DB is the source of truth; these are rendered outputs.

Usage:
    python scripts/07_export_web.py
    python scripts/07_export_web.py --only gbif_2493440
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.db import get_connection

OUT_DIR    = Path("data/built/species")
INDEX_PATH = Path("data/built/species_index.json")

PROFILE_BADGE = {
    "basic":          {"label":"basic","color":"muted"},
    "enriched":       {"label":"enriched","color":"teal"},
    "evidence_backed":{"label":"evidence backed","color":"amber"},
}


def export_species(con, sid: str) -> dict:
    """Build a full species JSON record from the DB."""
    sp = con.execute("SELECT * FROM species WHERE species_id=?", (sid,)).fetchone()
    if not sp:
        return {}
    sp = dict(sp)

    meta = con.execute("SELECT * FROM species_metadata WHERE species_id=?", (sid,)).fetchone()
    meta = dict(meta) if meta else {}

    # Papers (pilot + literature)
    papers_rows = con.execute("""
        SELECT p.paper_id, p.title, p.year, p.doi, p.abstract, p.journal, p.open_access, p.source,
               ps.developmental_stage, ps.main_outcome, ps.dataset_available, ps.dataset_name
        FROM papers p
        JOIN paper_species ps ON p.paper_id = ps.paper_id
        WHERE ps.species_id = ?
        ORDER BY p.year DESC NULLS LAST
    """, (sid,)).fetchall()

    papers = [dict(r) for r in papers_rows]

    # Communication claims — grouped with paper evidence and counts
    claims_rows = con.execute("""
        SELECT claim_type, value, confidence, source, paper_id,
               COUNT(*) OVER (PARTITION BY claim_type, value) AS evidence_count
        FROM communication_claims
        WHERE species_id = ?
        ORDER BY claim_type, confidence DESC
    """, (sid,)).fetchall()

    claims_by_type: dict[str, list] = {}
    seen = set()
    for r in claims_rows:
        ct = r["claim_type"]
        key = (ct, r["value"])
        if key in seen:
            continue
        seen.add(key)
        claims_by_type.setdefault(ct, []).append({
            "value":          r["value"],
            "confidence":     round(r["confidence"], 2),
            "source":         r["source"],
            "evidence_count": r["evidence_count"],
        })

    # Media assets
    media_rows = con.execute("""
        SELECT * FROM media_assets WHERE species_id=? ORDER BY media_type, provider
    """, (sid,)).fetchall()
    media = [dict(r) for r in media_rows]

    # Open literature DOIs
    dois_rows = con.execute("""
        SELECT doi, url, title, year, source FROM open_literature
        WHERE species_id=? ORDER BY year DESC NULLS LAST
    """, (sid,)).fetchall()
    open_dois = [dict(r) for r in dois_rows]

    # Audio (structured for frontend)
    xc_audio  = [m for m in media if m["provider"] == "xeno_canto"]
    fs_audio  = [m for m in media if m["provider"] == "freesound"]
    audio_recs = []
    for m in (xc_audio + fs_audio):
        audio_recs.append({
            "id":    m.get("xc_id",""),
            "type":  m.get("recording_type","vocalisation"),
            "rec":   m.get("recorded_by",""),
            "loc":   m.get("location",""),
            "date":  m.get("recorded_date",""),
            "url":   m.get("url",""),
            "audio": m.get("audio_url",""),
            "sono":  m.get("spectrogram_url",""),
            "license": m.get("license",""),
        })

    profile_level = sp.get("profile_level","basic")
    paper_count   = len(papers)
    claim_count   = sum(len(v) for v in claims_by_type.values())
    doi_count     = len(open_dois)

    return {
        # ── Identity ──────────────────────────────────────────────────────────
        "species_id":       sid,
        "gbif_usage_key":   sp.get("gbif_usage_key"),
        "scientific_name":  sp["scientific_name"],
        "common_name_en":   sp.get("common_name_en",""),
        "common_names": {
            "en": sp.get("common_name_en",""),
            "it": sp.get("common_name_it",""),
            "es": sp.get("common_name_es",""),
            "fr": sp.get("common_name_fr",""),
            "de": sp.get("common_name_de",""),
        },

        # ── Taxonomy ──────────────────────────────────────────────────────────
        "taxonomy": {
            "class_":               sp.get("class_",""),
            "order_":               sp.get("order_",""),
            "family":               sp.get("family",""),
            "genus":                sp.get("genus",""),
            "gbif_match_confidence": sp.get("gbif_match_confidence",0),
            "gbif_match_status":    sp.get("gbif_match_status",""),
        },

        # ── Quality tier ──────────────────────────────────────────────────────
        "profile_level":  profile_level,
        "profile_badge":  PROFILE_BADGE.get(profile_level, PROFILE_BADGE["basic"]),
        "stats": {
            "paper_count": paper_count,
            "claim_count": claim_count,
            "doi_count":   doi_count,
            "media_count": len(media),
        },

        # ── Media ─────────────────────────────────────────────────────────────
        "image": {
            "url":          meta.get("image_url",""),
            "url_full":     meta.get("image_url_full",""),
            "source":       meta.get("image_source","Wikimedia Commons"),
            "license":      meta.get("image_license",""),
            "attribution":  meta.get("image_attribution",""),
        },

        # ── Description ───────────────────────────────────────────────────────
        "summary":          meta.get("summary",""),
        "wiki_url":         meta.get("wiki_url",""),
        "wiki_title":       sp.get("wiki_title",""),
        "conservation_status": meta.get("conservation_status",""),
        "inat_id":          meta.get("inat_id"),

        # ── Communication profile ─────────────────────────────────────────────
        # For backward compat with frontend, keep flat lists too
        "vocalisations": [c["value"] for c in claims_by_type.get("vocalisation",[])],
        "contexts":      [c["value"] for c in claims_by_type.get("context",[])],
        "functions":     [c["value"] for c in claims_by_type.get("function",[])],

        # Provenance-aware version
        "communication_profile": {
            "vocalisations": claims_by_type.get("vocalisation",[]),
            "contexts":      claims_by_type.get("context",[]),
            "functions":     claims_by_type.get("function",[]),
            "methods":       claims_by_type.get("method",[]),
        },

        # ── Audio ─────────────────────────────────────────────────────────────
        "audio": {
            "provider":       sp.get("audio_provider","external_links"),
            "xc_query":       sp.get("xeno_canto_query",""),
            "recordings":     audio_recs,
            "external_links": [],
        },

        # ── Literature ────────────────────────────────────────────────────────
        "open_papers": open_dois,
        "papers":      papers,
        "paper_count": paper_count,

        # ── Provenance ────────────────────────────────────────────────────────
        "provenance": {
            "taxonomy_source":  "GBIF backbone",
            "media_source":     "Wikimedia Commons",
            "literature_source": "Crossref + OpenAlex + pilot annotations",
            "db_version":       "0.3",
        },
    }


def build_index_entry(record: dict) -> dict:
    return {
        "species_id":      record["species_id"],
        "scientific_name": record["scientific_name"],
        "common_name_en":  record["common_name_en"],
        "common_names":    record["common_names"],
        "class_":          record["taxonomy"]["class_"],
        "order_":          record["taxonomy"]["order_"],
        "family":          record["taxonomy"]["family"],
        "image_url":       record["image"]["url"],
        "paper_count":     record["paper_count"],
        "doi_count":       record["stats"]["doi_count"],
        "claim_count":     record["stats"]["claim_count"],
        "conservation":    record.get("conservation_status",""),
        "profile_level":   record["profile_level"],
        "vocalisations":   record["vocalisations"],
        "has_audio":       len(record["audio"]["recordings"]) > 0,
    }


def main():
    parser = argparse.ArgumentParser(description="Export DB to JSON for web frontend.")
    parser.add_argument("--only", default=None, help="Export only this species_id.")
    args = parser.parse_args()

    con  = get_connection()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.only:
        ids = [args.only]
    else:
        ids = [r[0] for r in con.execute("SELECT species_id FROM species ORDER BY common_name_en")]

    print(f"\nExporting {len(ids)} species to JSON...\n")
    index = []

    for i, sid in enumerate(ids, 1):
        record = export_species(con, sid)
        if not record:
            print(f"  [{i}/{len(ids)}] {sid} — not found, skipping")
            continue

        out_file = OUT_DIR / f"{sid}.json"
        out_file.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
        index.append(build_index_entry(record))

        level = record["profile_level"]
        pc    = record["paper_count"]
        dc    = record["stats"]["doi_count"]
        print(f"  [{i}/{len(ids)}] {record['common_name_en']:30s} level={level:15s} papers={pc} dois={dc}")

    if not args.only:
        INDEX_PATH.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")

    levels = {}
    for r in index:
        lv = r["profile_level"]
        levels[lv] = levels.get(lv, 0) + 1

    print(f"\n✓ Exported {len(index)} species")
    for lv, n in sorted(levels.items()):
        badge = {"basic":"○","enriched":"◎","evidence_backed":"●"}.get(lv,"?")
        print(f"  {badge} {lv:20s} {n}")
    print(f"✓ Index: {INDEX_PATH}\n")


if __name__ == "__main__":
    main()
