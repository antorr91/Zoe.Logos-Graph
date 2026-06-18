"""
scripts/02_fetch_species_metadata.py
-------------------------------------
Step 2 of the Zoe.Logos-Graph build pipeline.

For each species in taxa_matched.json, fetches:
  - Wikipedia summary (extract + thumbnail)
  - iNaturalist conservation status

Caches each response in data/cache/wikidata/<species_id>.json
Writes enriched data to data/cache/wikidata/metadata_all.json

Usage:
    python scripts/02_fetch_species_metadata.py

Requires:
    data/cache/gbif/taxa_matched.json  (from step 01)
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import requests

TAXA_PATH   = Path("data/cache/gbif/taxa_matched.json")
CACHE_DIR   = Path("data/cache/wikidata")
OUTPUT_PATH = Path("data/cache/wikidata/metadata_all.json")
DELAY       = 0.4


def fetch_wikipedia(wiki_title: str) -> dict:
    """Fetch summary from Wikipedia REST API."""
    if not wiki_title:
        return {}
    try:
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{requests.utils.quote(wiki_title)}"
        r = requests.get(url, timeout=10, headers={"User-Agent": "ZoeLogosGraph/0.1 (research)"})
        if r.status_code == 404:
            return {}
        r.raise_for_status()
        d = r.json()
        sentences = (d.get("extract") or "").split(". ")
        summary = ". ".join(sentences[:3]).strip()
        if summary and not summary.endswith("."):
            summary += "."
        return {
            "summary":          summary,
            "image_url":        d.get("thumbnail", {}).get("source"),
            "image_url_full":   d.get("originalimage", {}).get("source"),
            "wiki_url":         d.get("content_urls", {}).get("desktop", {}).get("page"),
            "image_source":     "Wikimedia Commons",
            "image_license":    "see Wikimedia Commons page",
            "image_attribution": "",
        }
    except Exception as e:
        print(f"    Wikipedia error: {e}")
        return {}


def fetch_inaturalist(sci_name: str) -> dict:
    """Fetch conservation status from iNaturalist taxa API."""
    try:
        url = f"https://api.inaturalist.org/v1/taxa?q={requests.utils.quote(sci_name)}&rank=species&per_page=1"
        r = requests.get(url, timeout=10, headers={"User-Agent": "ZoeLogosGraph/0.1 (research)"})
        r.raise_for_status()
        results = r.json().get("results", [])
        if not results:
            return {}
        t = results[0]
        anc = t.get("ancestors") or []
        def get_rank(rank):
            return next((a["name"] for a in anc if a.get("rank") == rank), "")
        return {
            "inat_id":           t.get("id"),
            "inat_iconic_taxon": t.get("iconic_taxon_name", ""),
            "conservation":      t.get("conservation_status", {}).get("status_name") if t.get("conservation_status") else "",
            "inat_order":        get_rank("order"),
            "inat_family":       get_rank("family"),
        }
    except Exception as e:
        print(f"    iNaturalist error: {e}")
        return {}


def main():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    taxa = json.loads(TAXA_PATH.read_text(encoding="utf-8"))
    total = len(taxa)
    results = []

    print(f"\nFetching metadata for {total} species...\n")

    for i, sp in enumerate(taxa, 1):
        sci  = sp["canonical_name"]
        wiki = sp.get("wiki_title", "")
        sid  = sp.get("species_id") or sci.replace(" ", "_").lower()

        print(f"[{i}/{total}] {sci}")

        # Check cache
        cache_file = CACHE_DIR / f"{sid.replace(':', '_').replace('/', '_')}.json"
        if cache_file.exists():
            cached = json.loads(cache_file.read_text())
            print(f"  ✓  cached")
        else:
            wp   = fetch_wikipedia(wiki)
            inat = fetch_inaturalist(sci)
            time.sleep(DELAY)

            cached = {**sp, **wp, **inat}
            cache_file.write_text(json.dumps(cached, indent=2, ensure_ascii=False))
            print(f"  ✓  fetched  img={'yes' if wp.get('image_url') else 'no'}  inat={bool(inat)}")

        results.append({**sp, **cached})

    OUTPUT_PATH.write_text(
        json.dumps(results, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    with_img = sum(1 for r in results if r.get("image_url"))
    print(f"\nDone: {with_img}/{total} have images")
    print(f"Output: {OUTPUT_PATH}\n")


if __name__ == "__main__":
    main()
