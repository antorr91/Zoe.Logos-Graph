"""
scripts/03_fetch_media.py
--------------------------
Step 3 — fetch audio metadata by provider:

  xeno_canto  → Xeno-canto API (birds, frogs)
  freesound   → Freesound.org API (domestic animals, common species)
  macaulay    → Macaulay Library search link (cetaceans, primates, bats, elephants)
  external    → curated external links only

Freesound requires a free API key. Register at https://freesound.org/apiv2/
Set FREESOUND_API_KEY in your environment before running:

    set FREESOUND_API_KEY=your_key_here      (Windows CMD)
    export FREESOUND_API_KEY=your_key_here   (Mac/Linux)

If the key is not set, Freesound species get external links instead.

Usage:
    python scripts/03_fetch_media.py
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests

METADATA_PATH = Path("data/cache/wikidata/metadata_all.json")
CACHE_DIR     = Path("data/cache/xeno_canto")
OUTPUT_PATH   = Path("data/cache/xeno_canto/audio_registry.json")
DELAY         = 0.5
MAX_XC        = 4
MAX_FS        = 4

FREESOUND_KEY = os.environ.get("FREESOUND_API_KEY", "")
XC_API_KEY    = os.environ.get("XC_API_KEY", "")
HEADERS       = {"User-Agent": "ZoeLogosGraph/0.2 (research)"}


# ── Xeno-canto (v2 public or v3 with key) ────────────────────────────────────
# Xeno-canto v2 API was retired — v3 requires a free personal key.
# Register at https://xeno-canto.org → My account → API keys
# Then: set XC_API_KEY=your_key  (Windows CMD)
#       export XC_API_KEY=your_key  (Mac/Linux)

def fetch_xc(query: str) -> list[dict]:
    cache = CACHE_DIR / f"xc_{query.replace(' ','_').lower()}.json"
    if cache.exists():
        return json.loads(cache.read_text())

    if not XC_API_KEY:
        print(f"    No XC_API_KEY set — skipping (register free at xeno-canto.org)")
        return []

    try:
        r = requests.get(
            "https://xeno-canto.org/api/3/recordings",
            params={"query": query, "key": XC_API_KEY},
            timeout=15, headers=HEADERS,
        )
        r.raise_for_status()
        recs = r.json().get("recordings", [])[:MAX_XC]
        slim = [{"id":rec.get("id"),"type":rec.get("type"),"rec":rec.get("rec"),
                 "cnt":rec.get("cnt"),"loc":rec.get("loc"),"date":rec.get("date"),
                 "url":f"https://xeno-canto.org/{rec.get('id')}",
                 "audio":f"https://xeno-canto.org/{rec.get('id')}/download",
                 "sono":rec.get("sono",{}).get("med"),"license":rec.get("lic")} for rec in recs]
        cache.write_text(json.dumps(slim, indent=2, ensure_ascii=False))
        return slim
    except Exception as e:
        print(f"    XC error: {e}")
        return []


# ── Freesound ───────────────────────────────────────────────────────────────

def fetch_freesound(common_name: str, sci_name: str) -> list[dict]:
    if not FREESOUND_KEY:
        return []
    cache = CACHE_DIR / f"fs_{sci_name.replace(' ','_').lower()}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    try:
        query = f"{common_name} sound"
        r = requests.get(
            "https://freesound.org/apiv2/search/text/",
            params={"query": query, "fields": "id,name,description,url,previews,license,username,duration",
                    "filter": "duration:[0.5 TO 60]", "page_size": MAX_FS,
                    "token": FREESOUND_KEY},
            timeout=15, headers=HEADERS
        )
        r.raise_for_status()
        results = r.json().get("results", [])
        slim = [{"id":s.get("id"),"name":s.get("name"),"description":(s.get("description","")[:120]+"…") if s.get("description","") else "",
                 "url":s.get("url"),"audio":s.get("previews",{}).get("preview-hq-mp3"),
                 "license":s.get("license"),"author":s.get("username"),"duration":round(s.get("duration",0),1)} for s in results]
        cache.write_text(json.dumps(slim, indent=2, ensure_ascii=False))
        return slim
    except Exception as e:
        print(f"    Freesound error: {e}")
        return []


# ── External link registry ───────────────────────────────────────────────────

def external_links_for(sp: dict) -> list[dict]:
    """Return curated external audio links based on provider and taxon."""
    provider = sp.get("audio_provider", "external_links")
    order    = sp.get("order_") or sp.get("inat_order", "")
    common   = sp.get("common_name_en", "")
    sci      = sp.get("canonical_name", "")

    if provider == "macaulay":
        ml_url = f"https://search.macaulaylibrary.org/catalog?taxonCode=&mediaType=audio&searchField=species&q={requests.utils.quote(sci)}"
        links  = [{"name": f"Macaulay Library — {common}", "url": ml_url}]
        if order == "Cetacea":
            links.append({"name": "NOAA Ocean Sounds", "url": "https://www.fisheries.noaa.gov/national/protected-resources/sounds-ocean"})
        elif order == "Chiroptera":
            links.append({"name": "BatDetective", "url": "https://www.batdetective.org/"})
        elif order == "Proboscidea":
            links.append({"name": "ElephantVoices", "url": "https://www.elephantvoices.org/"})
        return links

    if provider == "freesound" and not FREESOUND_KEY:
        fs_url = f"https://freesound.org/search/?q={requests.utils.quote(common+' sound')}"
        return [
            {"name": f"Freesound — search '{common} sound'", "url": fs_url},
            {"name": "Macaulay Library (non-bird)", "url": "https://www.macaulaylibrary.org/"},
        ]

    # Generic fallback
    return [{"name": "Macaulay Library", "url": "https://www.macaulaylibrary.org/"}]


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if not METADATA_PATH.exists():
        print(f"ERROR: {METADATA_PATH} not found — run step 02 first.")
        return

    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    registry = []

    if not FREESOUND_KEY:
        print("⚠  FREESOUND_API_KEY not set — Freesound species will get external links only.")
        print("   Register free at https://freesound.org/apiv2/ and set the env var.\n")

    print(f"Fetching audio for {len(metadata)} species...\n")

    for i, sp in enumerate(metadata, 1):
        sci      = sp.get("canonical_name", sp["scientific_name"])
        common   = sp.get("common_name_en", "")
        provider = sp.get("audio_provider", "external_links")
        xc_q     = sp.get("xeno_canto_query", "")

        print(f"[{i}/{len(metadata)}] {sci}  ({provider})", end="  ")

        recordings    = []
        external_links = []

        if provider == "xeno_canto" and xc_q:
            recordings = fetch_xc(xc_q)
            print(f"XC: {len(recordings)} recordings")
            time.sleep(DELAY)

        elif provider == "freesound":
            recordings = fetch_freesound(common, sci)
            if recordings:
                print(f"Freesound: {len(recordings)} sounds")
            else:
                external_links = external_links_for(sp)
                print(f"Freesound: no key → {len(external_links)} links")
            time.sleep(DELAY)

        elif provider == "macaulay":
            external_links = external_links_for(sp)
            print(f"Macaulay: {len(external_links)} links")

        else:
            external_links = external_links_for(sp)
            print(f"external: {len(external_links)} links")

        registry.append({
            "species_id":     sp.get("species_id"),
            "scientific_name": sci,
            "provider":        provider,
            "recordings":      recordings,
            "external_links":  external_links,
        })

    OUTPUT_PATH.write_text(json.dumps(registry, indent=2, ensure_ascii=False))
    with_audio = sum(1 for r in registry if r["recordings"])
    print(f"\nDone: {with_audio}/{len(metadata)} species have recordings")
    print(f"Output: {OUTPUT_PATH}\n")


if __name__ == "__main__":
    main()
