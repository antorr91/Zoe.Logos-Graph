"""
scripts/13_import_recordings.py
--------------------------------
Import audio recordings into the v2 recording_assets table.

Sources:
  - Xeno-canto (birds, frogs) via API or cached JSON
  - Local audio files (data/local_audio/<species>/<file>)
  - Manual seed for cetaceans, primates, mammals (curated public-domain references)

Usage:
    python scripts/13_import_recordings.py                  # all sources
    python scripts/13_import_recordings.py --xeno-only      # only Xeno-canto
    python scripts/13_import_recordings.py --local-only     # only local files
    python scripts/13_import_recordings.py --species "Megaptera novaeangliae"
"""

from __future__ import annotations
import argparse
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.db_v2 import get_connection

try:
    import requests
except ImportError:
    print("pip install requests")
    sys.exit(1)

LOCAL_AUDIO_DIR = Path("data/local_audio")
XC_CACHE        = Path("data/cache/xeno_canto")
NOW             = datetime.utcnow().isoformat()
DELAY           = 0.5
MAX_PER_SPECIES = 4


# ── Curated public-domain recordings for non-bird species ────────────────────
# These are reference recordings with permissive licenses that we can link to.
# Format: scientific_name -> [{title, provider, url, license, attribution, recorded_by}]

CURATED_RECORDINGS = {
    "Megaptera novaeangliae": [
        {"title":"Humpback whale song — NOAA Pacific Islands","provider":"noaa",
         "url":"https://www.fisheries.noaa.gov/national/science-data/sounds-ocean-mammals",
         "license":"Public Domain (US Govt work)","attribution":"NOAA Pacific Islands Fisheries Science Center",
         "recorded_by":"NOAA","provider_id":"noaa-humpback-01"},
    ],
    "Tursiops truncatus": [
        {"title":"Bottlenose dolphin signature whistle reference","provider":"macaulay",
         "url":"https://www.macaulaylibrary.org/asset/207879411",
         "license":"Macaulay Library","attribution":"Cornell Lab of Ornithology",
         "recorded_by":"various","provider_id":"ML207879411"},
    ],
    "Orcinus orca": [
        {"title":"Killer whale call — NOAA Northwest","provider":"noaa",
         "url":"https://www.fisheries.noaa.gov/national/science-data/sounds-ocean-mammals",
         "license":"Public Domain","attribution":"NOAA NWFSC",
         "recorded_by":"NOAA","provider_id":"noaa-orca-01"},
    ],
    "Physeter macrocephalus": [
        {"title":"Sperm whale codas reference","provider":"noaa",
         "url":"https://www.fisheries.noaa.gov/national/science-data/sounds-ocean-mammals",
         "license":"Public Domain","attribution":"NOAA",
         "recorded_by":"NOAA","provider_id":"noaa-spermwhale-01"},
    ],
    "Loxodonta africana": [
        {"title":"African elephant rumble — ElephantVoices","provider":"elephantvoices",
         "url":"https://www.elephantvoices.org/elephants-in-recovery/sound-archive.html",
         "license":"Educational use","attribution":"ElephantVoices / Joyce Poole",
         "recorded_by":"Joyce Poole","provider_id":"ev-rumble-01"},
    ],
    "Chlorocebus pygerythrus": [
        {"title":"Vervet monkey alarm calls — Macaulay","provider":"macaulay",
         "url":"https://www.macaulaylibrary.org/asset/482631",
         "license":"Macaulay Library","attribution":"Cornell Lab",
         "recorded_by":"various","provider_id":"ML482631"},
    ],
    "Pan troglodytes": [
        {"title":"Chimpanzee pant-hoot reference","provider":"macaulay",
         "url":"https://www.macaulaylibrary.org/",
         "license":"Macaulay Library","attribution":"Cornell Lab",
         "recorded_by":"various","provider_id":"ml-chimp-01"},
    ],
    "Eptesicus fuscus": [
        {"title":"Big brown bat echolocation","provider":"macaulay",
         "url":"https://www.macaulaylibrary.org/",
         "license":"Macaulay Library","attribution":"Cornell Lab",
         "recorded_by":"various","provider_id":"ml-bat-01"},
    ],
    "Apis mellifera": [
        {"title":"Honeybee waggle dance buzz","provider":"bioacoustica",
         "url":"https://bioacoustica.org/",
         "license":"CC BY","attribution":"Bioacoustica",
         "recorded_by":"various","provider_id":"ba-bee-01"},
    ],
}


def import_xc_for_species(con, species_id: str, sci: str, max_n: int = MAX_PER_SPECIES) -> int:
    """Import Xeno-canto recordings using cached JSON or API."""
    cache_file = XC_CACHE / f"xc_{sci.replace(' ','_').lower()}.json"

    recs = None
    if cache_file.exists():
        try:
            recs = json.loads(cache_file.read_text())
        except:
            pass

    if recs is None:
        # Try API
        XC_API_KEY = os.environ.get("XC_API_KEY", "")
        try:
            if XC_API_KEY:
                url = "https://xeno-canto.org/api/3/recordings"
                params = {"query": sci, "key": XC_API_KEY}
            else:
                url = "https://xeno-canto.org/api/2/recordings"
                params = {"query": sci, "page": 1}
            r = requests.get(url, params=params, timeout=15)
            if r.status_code == 200:
                data = r.json()
                recs = data.get("recordings", [])[:max_n]
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                cache_file.write_text(json.dumps(recs, indent=2))
                time.sleep(DELAY)
            else:
                return 0
        except Exception as e:
            return 0

    if not recs:
        return 0

    n = 0
    for rec in recs[:max_n]:
        rid = f"xc_{rec.get('id','')}"
        if not rec.get("id"):
            continue
        try:
            con.execute("""
                INSERT OR IGNORE INTO recording_assets
                (recording_id, species_id, title, provider, provider_id, url, audio_url,
                 license, attribution, recorded_by, recorded_date, location, fetched_at)
                VALUES (?, ?, ?, 'xeno-canto', ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                rid, species_id,
                rec.get("type","vocalisation") + " (XC" + str(rec.get("id")) + ")",
                str(rec.get("id","")),
                f"https://xeno-canto.org/{rec.get('id')}",
                f"https://xeno-canto.org/{rec.get('id')}/download",
                rec.get("lic","CC BY-NC"),
                f"Xeno-canto · {rec.get('rec','unknown')}",
                rec.get("rec",""),
                rec.get("date",""),
                f"{rec.get('loc','')}, {rec.get('cnt','')}".strip(", "),
                NOW,
            ))
            if con.total_changes:
                n += 1
        except Exception as e:
            print(f"    error: {e}")
    con.commit()
    return n


def import_curated_for_species(con, species_id: str, sci: str) -> int:
    """Import curated reference recordings."""
    if sci not in CURATED_RECORDINGS:
        return 0
    n = 0
    for rec in CURATED_RECORDINGS[sci]:
        rid = f"{rec['provider']}_{rec['provider_id']}"
        try:
            cur = con.execute("""
                INSERT OR IGNORE INTO recording_assets
                (recording_id, species_id, title, provider, provider_id, url,
                 license, attribution, recorded_by, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                rid, species_id, rec["title"], rec["provider"], rec["provider_id"],
                rec["url"], rec["license"], rec["attribution"], rec.get("recorded_by",""),
                NOW,
            ))
            if cur.rowcount:
                n += 1
        except Exception as e:
            pass
    con.commit()
    return n


def import_local_for_species(con, species_id: str, sci: str) -> int:
    """Import local audio files from data/local_audio/<species>/."""
    species_dir = LOCAL_AUDIO_DIR / sci.replace(" ","_")
    if not species_dir.exists():
        return 0
    n = 0
    for f in species_dir.glob("*"):
        if f.suffix.lower() not in (".wav",".mp3",".flac",".ogg"):
            continue
        rid = f"local_{species_id}_{f.stem}"
        try:
            cur = con.execute("""
                INSERT OR IGNORE INTO recording_assets
                (recording_id, species_id, title, provider, audio_path, license, fetched_at)
                VALUES (?, ?, ?, 'local', ?, 'see file metadata', ?)
            """, (rid, species_id, f.stem, str(f), NOW))
            if cur.rowcount:
                n += 1
        except Exception as e:
            print(f"    error: {e}")
    con.commit()
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--species", default=None)
    ap.add_argument("--xeno-only", action="store_true")
    ap.add_argument("--local-only", action="store_true")
    ap.add_argument("--curated-only", action="store_true")
    args = ap.parse_args()

    con = get_connection()

    if args.species:
        rows = con.execute("SELECT species_id, scientific_name FROM species WHERE scientific_name=?",
                          (args.species,)).fetchall()
    else:
        rows = con.execute("SELECT species_id, scientific_name FROM species ORDER BY common_name_en").fetchall()

    print(f"\nImporting recordings for {len(rows)} species...\n")
    totals = {"xc":0, "curated":0, "local":0}

    for i, sp in enumerate(rows, 1):
        sid = sp["species_id"]
        sci = sp["scientific_name"]
        print(f"[{i}/{len(rows)}] {sci}", end=" ")

        n_xc = n_cur = n_loc = 0
        if not args.curated_only and not args.local_only:
            n_xc = import_xc_for_species(con, sid, sci)
        if not args.xeno_only and not args.local_only:
            n_cur = import_curated_for_species(con, sid, sci)
        if not args.xeno_only and not args.curated_only:
            n_loc = import_local_for_species(con, sid, sci)

        totals["xc"] += n_xc
        totals["curated"] += n_cur
        totals["local"] += n_loc

        if n_xc or n_cur or n_loc:
            parts = []
            if n_xc: parts.append(f"XC:{n_xc}")
            if n_cur: parts.append(f"curated:{n_cur}")
            if n_loc: parts.append(f"local:{n_loc}")
            print(f"→ {' '.join(parts)}")
        else:
            print("→ —")

    print(f"\n✓ Total: {totals['xc']} XC + {totals['curated']} curated + {totals['local']} local")
    print(f"  Total recordings now in DB: {con.execute('SELECT COUNT(*) FROM recording_assets').fetchone()[0]}")
    print(f"\nNext: python scripts/12_generate_spectrograms.py --limit 10\n")


if __name__ == "__main__":
    main()
