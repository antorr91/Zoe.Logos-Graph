"""
scripts/04_build_species_pages.py
----------------------------------
Step 4 of the Zoe.Logos-Graph build pipeline.

Merges metadata + audio + paper data into:
  - data/built/species/<species_id>.json   (one file per species)
  - data/built/species_index.json          (lightweight index for search grid)

The front-end (web/species.html) reads ONLY these files.
No species data is hardcoded in HTML.

Usage:
    python scripts/04_build_species_pages.py

Requires:
    data/cache/gbif/taxa_matched.json
    data/cache/wikidata/metadata_all.json
    data/cache/xeno_canto/audio_registry.json
    data/annotations/pilot.json            (optional — paper detail)
"""

from __future__ import annotations

import json
import re
from pathlib import Path

METADATA_PATH = Path("data/cache/wikidata/metadata_all.json")
AUDIO_PATH    = Path("data/cache/xeno_canto/audio_registry.json")
PILOT_PATH    = Path("data/annotations/pilot.json")
OUT_DIR       = Path("data/built/species")
INDEX_PATH    = Path("data/built/species_index.json")

# Paper details from pilot — keyed by paper_id
def load_papers() -> dict:
    if not PILOT_PATH.exists():
        return {}
    records = json.loads(PILOT_PATH.read_text(encoding="utf-8"))
    return {r["paper_id"]: r for r in records}


def make_species_id(sp: dict) -> str:
    """Generate a clean filesystem-safe species ID."""
    gbif = sp.get("gbif_usage_key")
    if gbif:
        return f"gbif_{gbif}"
    canon = sp.get("canonical_name", "unknown").lower()
    return re.sub(r"[^a-z0-9]+", "_", canon).strip("_")


def build_species_record(sp: dict, audio: dict, papers: dict) -> dict:
    """Build the full species JSON record."""
    paper_ids  = sp.get("paper_ids", [])
    paper_list = []
    for pid in paper_ids:
        if pid in papers:
            p = papers[pid]
            paper_list.append({
                "id":      pid,
                "title":   p.get("title", ""),
                "year":    p.get("year"),
                "stage":   p.get("developmental_stage", ""),
                "methods": p.get("analysis_method", []),
                "outcome": p.get("main_outcome", ""),
                "dataset_available": p.get("dataset_or_recording_available", "unknown"),
                "dataset_name": p.get("dataset_name"),
            })
        else:
            paper_list.append({"id": pid, "title": f"Paper {pid}", "year": None})

    return {
        # ── Identity ──────────────────────────────────────────────────────
        "species_id":       make_species_id(sp),
        "gbif_usage_key":   sp.get("gbif_usage_key"),
        "scientific_name":  sp.get("canonical_name") or sp.get("scientific_name"),
        "common_name_en":   sp.get("common_name_en", ""),
        "common_names": {
            "en": sp.get("common_name_en", ""),
            "it": sp.get("common_name_it", ""),
            "es": sp.get("common_name_es", ""),
            "fr": sp.get("common_name_fr", ""),
            "de": sp.get("common_name_de", ""),
        },

        # ── Taxonomy ──────────────────────────────────────────────────────
        "taxonomy": {
            "class_":       sp.get("class_") or sp.get("inat_iconic_taxon", ""),
            "order_":       sp.get("order_") or sp.get("inat_order", ""),
            "family":       sp.get("family") or sp.get("inat_family", ""),
            "genus":        sp.get("genus", ""),
            "gbif_match_confidence": sp.get("gbif_match_confidence", 0),
            "gbif_match_status": sp.get("gbif_match_status", ""),
        },

        # ── Conservation ─────────────────────────────────────────────────
        "conservation_status": sp.get("conservation", ""),
        "inat_id": sp.get("inat_id"),

        # ── Media ─────────────────────────────────────────────────────────
        "image": {
            "url":          sp.get("image_url", ""),
            "url_full":     sp.get("image_url_full", ""),
            "source":       sp.get("image_source", "Wikimedia Commons"),
            "license":      sp.get("image_license", ""),
            "attribution":  sp.get("image_attribution", ""),
        },

        # ── Description ───────────────────────────────────────────────────
        "summary":      sp.get("summary", ""),
        "wiki_url":     sp.get("wiki_url", ""),
        "wiki_title":   sp.get("wiki_title", ""),

        # ── Communication (from seed) ─────────────────────────────────────
        "vocalisations":    sp.get("vocalisations", []),
        "contexts":         sp.get("contexts", []),
        "functions":        sp.get("functions", []),

        # ── Audio ─────────────────────────────────────────────────────────
        "audio": {
            "provider":        audio.get("provider", "external_links"),
            "xc_query":        sp.get("xeno_canto_query", ""),
            "recordings":      audio.get("recordings", []),
            "external_links":  audio.get("external_links", []),
        },

        # ── Open-access literature (DOIs from seed) ──────────────────────
        "open_papers": [
            {"doi": doi, "url": f"https://doi.org/{doi}"}
            for doi in sp.get("open_papers", "").split("|") if doi
        ],

        # ── Papers ────────────────────────────────────────────────────────
        "papers":           paper_list,
        "paper_count":      len(paper_list),
    }


def build_index_entry(record: dict) -> dict:
    """Lightweight entry for the search index grid."""
    return {
        "species_id":     record["species_id"],
        "scientific_name": record["scientific_name"],
        "common_name_en": record["common_name_en"],
        "common_names":   record["common_names"],
        "class_":         record["taxonomy"]["class_"],
        "order_":         record["taxonomy"]["order_"],
        "family":         record["taxonomy"]["family"],
        "image_url":      record["image"]["url"],
        "paper_count":    record["paper_count"],
        "conservation":   record["conservation_status"],
        "vocalisations":  record["vocalisations"],
    }


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    audio_reg = {
        a["scientific_name"]: a
        for a in json.loads(AUDIO_PATH.read_text(encoding="utf-8"))
    }
    papers = load_papers()

    index = []
    print(f"\nBuilding {len(metadata)} species pages...\n")

    for i, sp in enumerate(metadata, 1):
        sci    = sp.get("canonical_name") or sp["scientific_name"]
        audio  = audio_reg.get(sci, {"provider": "external_links", "recordings": [], "external_links": []})
        record = build_species_record(sp, audio, papers)
        sid    = record["species_id"]

        out_file = OUT_DIR / f"{sid}.json"
        out_file.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
        index.append(build_index_entry(record))

        print(f"[{i}/{len(metadata)}] {sid}  papers={record['paper_count']}  img={'✓' if record['image']['url'] else '✗'}")

    INDEX_PATH.write_text(
        json.dumps(index, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print(f"\nDone.")
    print(f"  Species pages:  {OUT_DIR}/")
    print(f"  Search index:   {INDEX_PATH}\n")


if __name__ == "__main__":
    main()
