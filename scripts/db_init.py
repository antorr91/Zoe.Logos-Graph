"""
scripts/db_init.py
------------------
Initialise the Zoe.Logos-Graph SQLite database and import all existing data:

  - species from data/built/species/*.json
  - papers and claims from data/annotations/pilot.json
  - open literature DOIs from built species files
  - communication claims (seed level)

Usage:
    python scripts/db_init.py
    python scripts/db_init.py --reset   (drop and recreate all tables)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.db import get_connection, init_db, update_all_profile_levels

SPECIES_DIR = Path("data/built/species")
PILOT_PATH  = Path("data/annotations/pilot.json")
NOW         = datetime.utcnow().isoformat()


# ── Import species ────────────────────────────────────────────────────────────

def import_species(con, files: list[Path]) -> int:
    inserted = 0
    for f in files:
        sp = json.loads(f.read_text(encoding="utf-8"))
        tax = sp.get("taxonomy", {})

        con.execute("""
            INSERT OR IGNORE INTO species (
                species_id, gbif_usage_key, scientific_name, canonical_name,
                common_name_en, common_name_it, common_name_es, common_name_fr, common_name_de,
                class_, order_, family, genus,
                gbif_match_confidence, gbif_match_status,
                audio_provider, xeno_canto_query, wiki_title, created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            sp["species_id"],
            sp.get("gbif_usage_key"),
            sp["scientific_name"],
            sp.get("scientific_name"),
            sp.get("common_name_en",""),
            sp.get("common_names",{}).get("it",""),
            sp.get("common_names",{}).get("es",""),
            sp.get("common_names",{}).get("fr",""),
            sp.get("common_names",{}).get("de",""),
            tax.get("class_",""),
            tax.get("order_",""),
            tax.get("family",""),
            tax.get("genus",""),
            tax.get("gbif_match_confidence",0),
            tax.get("gbif_match_status","ACCEPTED"),
            sp.get("audio",{}).get("provider","external_links"),
            sp.get("audio",{}).get("xc_query",""),
            sp.get("wiki_title",""),
            NOW, NOW,
        ))

        # Metadata
        img = sp.get("image", {})
        con.execute("""
            INSERT OR IGNORE INTO species_metadata (
                species_id, summary, image_url, image_url_full,
                image_source, image_license, image_attribution,
                wiki_url, conservation_status, fetched_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (
            sp["species_id"],
            sp.get("summary",""),
            img.get("url",""),
            img.get("url_full",""),
            img.get("source","Wikimedia Commons"),
            img.get("license",""),
            img.get("attribution",""),
            sp.get("wiki_url",""),
            sp.get("conservation_status",""),
            NOW,
        ))

        # Open literature DOIs
        for ol in sp.get("open_papers", []):
            con.execute("""
                INSERT OR IGNORE INTO open_literature (species_id, doi, url, source)
                VALUES (?,?,?,'seed')
            """, (sp["species_id"], ol["doi"], ol["url"]))

        # Communication claims from seed (confidence=0.5, source='seed')
        for voc in sp.get("vocalisations", []):
            con.execute("""
                INSERT OR IGNORE INTO communication_claims
                (species_id, claim_type, value, confidence, source)
                VALUES (?,'vocalisation',?,0.5,'seed')
            """, (sp["species_id"], voc))
        for ctx in sp.get("contexts", []):
            con.execute("""
                INSERT OR IGNORE INTO communication_claims
                (species_id, claim_type, value, confidence, source)
                VALUES (?,'context',?,0.5,'seed')
            """, (sp["species_id"], ctx))
        for fn in sp.get("functions", []):
            con.execute("""
                INSERT OR IGNORE INTO communication_claims
                (species_id, claim_type, value, confidence, source)
                VALUES (?,'function',?,0.5,'seed')
            """, (sp["species_id"], fn))

        # Audio assets from xeno-canto (if already fetched)
        for rec in sp.get("audio", {}).get("recordings", []):
            con.execute("""
                INSERT OR IGNORE INTO media_assets
                (species_id, media_type, provider, url, audio_url, spectrogram_url,
                 license, xc_id, recording_type, location, recorded_by, recorded_date, fetched_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                sp["species_id"], "audio", "xeno_canto",
                rec.get("url",""), rec.get("audio",""), rec.get("sono",""),
                rec.get("license",""), str(rec.get("id","")),
                rec.get("type",""), rec.get("loc",""),
                rec.get("rec",""), rec.get("date",""), NOW,
            ))

        inserted += 1

    return inserted


# ── Import pilot annotations ─────────────────────────────────────────────────

def import_pilot(con) -> int:
    if not PILOT_PATH.exists():
        print("  No pilot.json found — skipping.")
        return 0

    records = json.loads(PILOT_PATH.read_text(encoding="utf-8"))
    inserted = 0
    for r in records:
        pid = r["paper_id"]

        # Paper
        con.execute("""
            INSERT OR IGNORE INTO papers (paper_id, title, year, source, fetched_at)
            VALUES (?,?,?,'pilot',?)
        """, (pid, r.get("title",""), r.get("year"), NOW))

        # Species link
        sci = r.get("species_scientific_name","unknown")
        sid_row = con.execute(
            "SELECT species_id FROM species WHERE scientific_name=?", (sci,)
        ).fetchone()
        if sid_row:
            sid = sid_row["species_id"]
            con.execute("""
                INSERT OR IGNORE INTO paper_species
                (paper_id, species_id, matched_by, developmental_stage, main_outcome, dataset_available, dataset_name)
                VALUES (?,?,'pilot',?,?,?,?)
            """, (
                pid, sid,
                r.get("developmental_stage","unknown"),
                r.get("main_outcome",""),
                r.get("dataset_or_recording_available","unknown"),
                r.get("dataset_name"),
            ))

            # Evidence-backed claims from pilot (confidence=0.9, source='extraction')
            for voc in r.get("vocalisation_type", []):
                con.execute("""
                    INSERT OR IGNORE INTO communication_claims
                    (species_id, paper_id, claim_type, value, confidence, source, extraction_version)
                    VALUES (?,?,?,?,?,?,?)
                """, (sid, pid, 'vocalisation', voc, 0.9, 'extraction', 'pilot_v1'))

            for ctx in r.get("behavioural_context", []):
                con.execute("""
                    INSERT OR IGNORE INTO communication_claims
                    (species_id, paper_id, claim_type, value, confidence, source, extraction_version)
                    VALUES (?,?,?,?,?,?,?)
                """, (sid, pid, 'context', ctx, 0.9, 'extraction', 'pilot_v1'))

            for fn in r.get("putative_function", []):
                con.execute("""
                    INSERT OR IGNORE INTO communication_claims
                    (species_id, paper_id, claim_type, value, confidence, source, extraction_version)
                    VALUES (?,?,?,?,?,?,?)
                """, (sid, pid, 'function', fn, 0.9, 'extraction', 'pilot_v1'))

            for method in r.get("analysis_method", []):
                con.execute("""
                    INSERT OR IGNORE INTO communication_claims
                    (species_id, paper_id, claim_type, value, confidence, source, extraction_version)
                    VALUES (?,?,?,?,?,?,?)
                """, (sid, pid, 'method', method, 0.9, 'extraction', 'pilot_v1'))

        inserted += 1

    return inserted


# ── Stats ─────────────────────────────────────────────────────────────────────

def print_stats(con) -> None:
    print(f"\n{'='*55}")
    print("Zoe.Logos-Graph — Database Summary")
    print(f"{'='*55}")
    tables = ["species","papers","paper_species","communication_claims","media_assets","open_literature"]
    for t in tables:
        n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t:30s} {n:>6} rows")

    print()
    print("  Profile levels:")
    for row in con.execute("SELECT profile_level, COUNT(*) AS n FROM species GROUP BY profile_level ORDER BY n DESC"):
        print(f"    {row['profile_level']:20s} {row['n']:>5}")

    print()
    print("  Claim sources:")
    for row in con.execute("SELECT source, COUNT(*) AS n FROM communication_claims GROUP BY source ORDER BY n DESC"):
        print(f"    {row['source']:20s} {row['n']:>5}")

    print()
    print("  Species by class:")
    for row in con.execute("SELECT class_, COUNT(*) AS n FROM species GROUP BY class_ ORDER BY n DESC"):
        print(f"    {row['class_']:20s} {row['n']:>5}")
    print(f"{'='*55}\n")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Initialise Zoe.Logos-Graph database.")
    parser.add_argument("--reset", action="store_true", help="Drop and recreate all tables.")
    args = parser.parse_args()

    con = get_connection()

    if args.reset:
        print("Resetting database...")
        con.executescript("""
            DROP TABLE IF EXISTS open_literature;
            DROP TABLE IF EXISTS media_assets;
            DROP TABLE IF EXISTS communication_claims;
            DROP TABLE IF EXISTS paper_species;
            DROP TABLE IF EXISTS papers;
            DROP TABLE IF EXISTS species_metadata;
            DROP TABLE IF EXISTS species;
            DROP VIEW IF EXISTS species_summary;
            DROP VIEW IF EXISTS vocalisation_counts;
            DROP VIEW IF EXISTS function_counts;
        """)
        con.commit()

    print("Initialising schema...")
    init_db(con)

    # Import species
    species_files = sorted(SPECIES_DIR.glob("*.json"))
    if not species_files:
        print(f"WARNING: no species files in {SPECIES_DIR} — run scripts/00_generate_species_db.py first")
    else:
        print(f"Importing {len(species_files)} species...")
        n = import_species(con, species_files)
        con.commit()
        print(f"  ✓ {n} species imported")

    # Import pilot
    print("Importing pilot annotations...")
    n = import_pilot(con)
    con.commit()
    print(f"  ✓ {n} pilot records imported")

    # Update profile levels
    print("Computing profile levels...")
    update_all_profile_levels(con)

    print_stats(con)
    print(f"Database: data/zoe_logos.db\n")


if __name__ == "__main__":
    main()
