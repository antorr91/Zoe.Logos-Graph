"""
scripts/01_match_taxa.py
------------------------
Step 1 of the Zoe.Logos-Graph build pipeline.

Reads seed_species.csv, queries the GBIF Species API for each scientific name,
and writes a normalised taxa JSON with stable GBIF usageKeys.

Usage:
    python scripts/01_match_taxa.py

Output:
    data/cache/gbif/taxa_matched.json
"""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path

import requests

SEED_PATH   = Path("data/seed/seed_species.csv")
OUTPUT_PATH = Path("data/cache/gbif/taxa_matched.json")
GBIF_API    = "https://api.gbif.org/v1/species/match"
DELAY       = 0.3  # seconds between requests — be polite to GBIF


def match_taxon(sci_name: str) -> dict:
    """Query GBIF species match API for a scientific name."""
    try:
        r = requests.get(GBIF_API, params={"name": sci_name, "verbose": False}, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  ERROR: {sci_name} → {e}")
        return {}


def extract_fields(match: dict, row: dict) -> dict:
    """Extract the fields we care about from a GBIF match response."""
    return {
        "scientific_name":      match.get("scientificName") or row["scientific_name"],
        "canonical_name":       match.get("canonicalName")  or row["scientific_name"],
        "species_id":           f"gbif:{match['usageKey']}" if "usageKey" in match else None,
        "gbif_usage_key":       match.get("usageKey"),
        "common_name_en":       row["common_name_en"],
        "common_name_it":       row.get("common_name_it", ""),
        "common_name_es":       row.get("common_name_es", ""),
        "common_name_fr":       row.get("common_name_fr", ""),
        "common_name_de":       row.get("common_name_de", ""),
        "class_":               match.get("class", ""),
        "order_":               match.get("order", ""),
        "family":               match.get("family", ""),
        "genus":                match.get("genus", ""),
        "wiki_title":           row.get("wiki_title", ""),
        "xeno_canto_query":     row.get("xeno_canto_query", ""),
        "audio_provider":       row.get("audio_provider", "external_links"),
        "paper_ids":            [p for p in row.get("paper_ids", "").split("|") if p],
        "vocalisations":        [v for v in row.get("vocalisations", "").split("|") if v],
        "contexts":             [c for c in row.get("contexts", "").split("|") if c],
        "functions":            [f for f in row.get("functions", "").split("|") if f],
        "gbif_match_confidence": match.get("confidence", 0),
        "gbif_match_status":    match.get("status", "UNKNOWN"),
    }


def main():
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    rows = list(csv.DictReader(SEED_PATH.open(encoding="utf-8")))
    total = len(rows)
    results = []

    print(f"\nMatching {total} species against GBIF backbone taxonomy...\n")

    for i, row in enumerate(rows, 1):
        sci = row["scientific_name"].strip()
        print(f"[{i}/{total}] {sci}...", end=" ")
        match = match_taxon(sci)
        record = extract_fields(match, row)
        results.append(record)

        conf = record["gbif_match_confidence"]
        key  = record["gbif_usage_key"]
        print(f"✓  key={key}  confidence={conf}%  class={record['class_']}")

        if i < total:
            time.sleep(DELAY)

    OUTPUT_PATH.write_text(
        json.dumps(results, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    matched   = sum(1 for r in results if r["gbif_usage_key"])
    unmatched = total - matched
    print(f"\nDone: {matched}/{total} matched, {unmatched} unmatched")
    print(f"Output: {OUTPUT_PATH}\n")


if __name__ == "__main__":
    main()
