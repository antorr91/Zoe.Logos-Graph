"""
scripts/06_fetch_literature.py
-------------------------------
Step 6 — Fetch literature for each species from Crossref and OpenAlex.

For each species queries:
  - "{scientific_name} vocal*"
  - "{scientific_name} communication"
  - "{scientific_name} call OR song OR alarm"

Saves paper metadata to DB: title, DOI, year, abstract, journal, OA status.

Usage:
    python scripts/06_fetch_literature.py
    python scripts/06_fetch_literature.py --max-per-species 10
    python scripts/06_fetch_literature.py --only "Taeniopygia guttata"

Requires:
    data/zoe_logos.db  (from scripts/db_init.py)
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import requests
except ImportError:
    print("ERROR: install requests first: pip install requests")
    sys.exit(1)

from src.db import get_connection

DELAY   = 0.5
NOW     = datetime.utcnow().isoformat()
HEADERS = {
    "User-Agent": "ZoeLogosGraph/0.3 (research; mailto:your@email.com)",
    "Accept": "application/json",
}

QUERY_TEMPLATES = [
    "{sci} vocal",
    "{sci} communication",
    "{sci} call",
    "{sci} song bioacoustic",
    "{sci} alarm vocalisation",
]


# ── Crossref ──────────────────────────────────────────────────────────────────

def fetch_crossref(sci: str, max_results: int = 5) -> list[dict]:
    """Query Crossref Works API for papers about a species."""
    results = []
    for tpl in QUERY_TEMPLATES[:3]:
        query = tpl.format(sci=sci)
        try:
            r = requests.get(
                "https://api.crossref.org/works",
                params={"query": query, "rows": max_results, "select":
                        "DOI,title,published,abstract,container-title,is-referenced-by-count"},
                headers=HEADERS, timeout=15,
            )
            if r.status_code != 200:
                continue
            items = r.json().get("message", {}).get("items", [])
            for item in items:
                doi   = item.get("DOI","")
                title = " ".join(item.get("title", [""])) if isinstance(item.get("title"), list) else item.get("title","")
                year  = None
                pd    = item.get("published")
                if pd and "date-parts" in pd:
                    year = pd["date-parts"][0][0] if pd["date-parts"] else None
                abstract = item.get("abstract","")
                journal  = ""
                if "container-title" in item and item["container-title"]:
                    journal = item["container-title"][0]
                results.append({
                    "doi": doi, "title": title, "year": year,
                    "abstract": abstract[:1000] if abstract else "",
                    "journal": journal, "source": "crossref",
                    "open_access": 0,
                })
            time.sleep(DELAY)
        except Exception as e:
            print(f"    Crossref error: {e}")
    return results


# ── OpenAlex ──────────────────────────────────────────────────────────────────

def fetch_openalex(sci: str, max_results: int = 5) -> list[dict]:
    """Query OpenAlex for papers about a species."""
    results = []
    query = f"{sci} vocal communication"
    try:
        r = requests.get(
            "https://api.openalex.org/works",
            params={"search": query, "per-page": max_results,
                    "select": "doi,title,publication_year,abstract_inverted_index,primary_location,open_access"},
            headers=HEADERS, timeout=15,
        )
        if r.status_code != 200:
            return []
        items = r.json().get("results", [])
        for item in items:
            doi   = (item.get("doi") or "").replace("https://doi.org/","")
            title = item.get("title","")
            year  = item.get("publication_year")
            oa    = 1 if item.get("open_access",{}).get("is_oa") else 0
            # Reconstruct abstract from inverted index
            abstract = ""
            inv = item.get("abstract_inverted_index")
            if inv:
                word_pos = sorted([(pos, word) for word, positions in inv.items() for pos in positions])
                abstract = " ".join(w for _, w in word_pos[:200])
            journal = ""
            loc = item.get("primary_location",{})
            if loc and loc.get("source"):
                journal = loc["source"].get("display_name","")
            results.append({
                "doi": doi, "title": title, "year": year,
                "abstract": abstract[:1000],
                "journal": journal, "source": "openalex",
                "open_access": oa,
            })
        time.sleep(DELAY)
    except Exception as e:
        print(f"    OpenAlex error: {e}")
    return results


# ── Save to DB ────────────────────────────────────────────────────────────────

def save_papers(con: sqlite3.Connection, species_id: str, sci: str, papers: list[dict]) -> int:
    saved = 0
    seen_dois = set()
    for p in papers:
        doi   = p.get("doi","").strip()
        title = p.get("title","").strip()
        if not title or (doi and doi in seen_dois):
            continue
        if doi:
            seen_dois.add(doi)

        pid = doi.replace("/","_").replace(".","_") if doi else f"lit_{species_id}_{saved}"
        try:
            con.execute("""
                INSERT OR IGNORE INTO papers (paper_id, title, year, doi, abstract, journal, open_access, source, fetched_at)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (pid, title, p.get("year"), doi or None, p.get("abstract",""), p.get("journal",""), p.get("open_access",0), p.get("source","unknown"), NOW))

            con.execute("""
                INSERT OR IGNORE INTO paper_species (paper_id, species_id, matched_by)
                VALUES (?,?,'literature_fetch')
            """, (pid, species_id))

            if doi:
                con.execute("""
                    INSERT OR IGNORE INTO open_literature (species_id, doi, url, title, year, source)
                    VALUES (?,?,?,?,?,?)
                """, (species_id, doi, f"https://doi.org/{doi}", title, p.get("year"), p.get("source","unknown")))

            saved += 1
        except Exception as e:
            pass

    return saved


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Fetch literature from Crossref and OpenAlex.")
    parser.add_argument("--max-per-species", type=int, default=8, help="Max papers per species.")
    parser.add_argument("--only", default=None, help="Only process this scientific name.")
    parser.add_argument("--crossref-only", action="store_true")
    parser.add_argument("--openalex-only", action="store_true")
    args = parser.parse_args()

    con = get_connection()

    query = "SELECT species_id, scientific_name FROM species"
    if args.only:
        query += f" WHERE scientific_name = '{args.only}'"
    species = con.execute(query).fetchall()

    print(f"\nFetching literature for {len(species)} species...\n")
    total_saved = 0

    for i, row in enumerate(species, 1):
        sid = row["species_id"]
        sci = row["scientific_name"]
        print(f"[{i}/{len(species)}] {sci}", end="  ")

        papers = []
        if not args.openalex_only:
            papers += fetch_crossref(sci, args.max_per_species)
        if not args.crossref_only:
            papers += fetch_openalex(sci, args.max_per_species)

        n = save_papers(con, sid, sci, papers)
        con.commit()
        total_saved += n
        print(f"→ {n} papers saved")

    # Update profile levels after enrichment
    from src.db import update_all_profile_levels
    update_all_profile_levels(con)

    print(f"\nDone: {total_saved} total papers saved across {len(species)} species.\n")


if __name__ == "__main__":
    main()
