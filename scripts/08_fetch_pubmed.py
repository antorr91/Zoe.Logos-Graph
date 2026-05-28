"""
scripts/08_fetch_pubmed.py
---------------------------
Fetch paper abstracts from PubMed using NCBI E-utilities.

For each species in the DB, searches PubMed with queries like:
  "Taeniopygia guttata" AND (vocal OR call OR song OR communication)

Stores paper metadata + abstracts in the DB papers table.

Usage:
    python scripts/08_fetch_pubmed.py
    python scripts/08_fetch_pubmed.py --max-per-species 20
    python scripts/08_fetch_pubmed.py --only "Taeniopygia guttata"
    python scripts/08_fetch_pubmed.py --topic "alarm call"

No API key required. Adding your email improves rate limits:
    set NCBI_EMAIL=your@email.com

Docs: https://www.ncbi.nlm.nih.gov/books/NBK25499/
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import requests
except ImportError:
    print("pip install requests")
    sys.exit(1)

from src.db import get_connection

NOW       = datetime.utcnow().isoformat()
DELAY     = 0.34   # NCBI allows 3 requests/sec without key
EMAIL     = os.environ.get("NCBI_EMAIL", "zoelogos@research.org")
BASE_URL  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

COMM_TERMS = "(vocal[tiab] OR call[tiab] OR song[tiab] OR communication[tiab] OR vocalisation[tiab] OR vocalization[tiab] OR bioacoustic[tiab] OR acoustic[tiab] OR alarm[tiab] OR playback[tiab])"


def esearch(query: str, max_results: int = 20) -> list[str]:
    """Search PubMed and return list of PMIDs."""
    try:
        r = requests.get(f"{BASE_URL}/esearch.fcgi", params={
            "db": "pubmed", "term": query, "retmax": max_results,
            "retmode": "json", "email": EMAIL,
        }, timeout=15)
        r.raise_for_status()
        return r.json().get("esearchresult", {}).get("idlist", [])
    except Exception as e:
        print(f"    esearch error: {e}")
        return []


def efetch(pmids: list[str]) -> list[dict]:
    """Fetch paper details for a list of PMIDs."""
    if not pmids:
        return []
    try:
        r = requests.get(f"{BASE_URL}/efetch.fcgi", params={
            "db": "pubmed", "id": ",".join(pmids),
            "retmode": "xml", "rettype": "abstract", "email": EMAIL,
        }, timeout=30)
        r.raise_for_status()
        return parse_pubmed_xml(r.text)
    except Exception as e:
        print(f"    efetch error: {e}")
        return []


def parse_pubmed_xml(xml_text: str) -> list[dict]:
    """Parse PubMed XML response into structured records."""
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    records = []
    for article in root.findall(".//PubmedArticle"):
        try:
            # PMID
            pmid = article.findtext(".//PMID") or ""

            # Title
            title = article.findtext(".//ArticleTitle") or ""
            title = title.strip().rstrip(".")

            # Abstract
            abstract_parts = article.findall(".//AbstractText")
            if abstract_parts:
                abstract = " ".join(
                    (a.get("Label", "") + ": " if a.get("Label") else "") + (a.text or "")
                    for a in abstract_parts
                ).strip()
            else:
                abstract = ""

            # Year
            year = None
            pub_date = article.find(".//PubDate")
            if pub_date is not None:
                year_el = pub_date.find("Year")
                if year_el is not None and year_el.text:
                    try:
                        year = int(year_el.text)
                    except ValueError:
                        pass

            # DOI
            doi = ""
            for id_el in article.findall(".//ArticleId"):
                if id_el.get("IdType") == "doi":
                    doi = id_el.text or ""
                    break

            # Journal
            journal = article.findtext(".//Journal/Title") or \
                      article.findtext(".//Journal/ISOAbbreviation") or ""

            # Open access flag (PMC = open access)
            pmc = article.findtext(".//ArticleId[@IdType='pmc']") or ""
            open_access = 1 if pmc else 0

            if not title:
                continue

            records.append({
                "paper_id":    f"pmid_{pmid}",
                "title":       title,
                "year":        year,
                "doi":         doi,
                "abstract":    abstract[:2000],
                "journal":     journal,
                "open_access": open_access,
                "source":      "pubmed",
                "pmid":        pmid,
                "pmc":         pmc,
            })

        except Exception:
            continue

    return records


def save_papers(con, species_id: str, papers: list[dict]) -> int:
    saved = 0
    for p in papers:
        try:
            con.execute("""
                INSERT OR IGNORE INTO papers
                (paper_id, title, year, doi, abstract, journal, open_access, source, fetched_at)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (p["paper_id"], p["title"], p.get("year"), p.get("doi") or None,
                  p.get("abstract",""), p.get("journal",""), p.get("open_access",0),
                  "pubmed", NOW))

            con.execute("""
                INSERT OR IGNORE INTO paper_species (paper_id, species_id, matched_by)
                VALUES (?,?,'pubmed_search')
            """, (p["paper_id"], species_id))

            # Add DOI to open_literature if OA
            if p.get("open_access") and p.get("doi"):
                con.execute("""
                    INSERT OR IGNORE INTO open_literature
                    (species_id, doi, url, title, year, source)
                    VALUES (?,?,?,?,?,'pubmed')
                """, (species_id, p["doi"],
                      f"https://doi.org/{p['doi']}", p["title"], p.get("year")))

            saved += 1
        except Exception as e:
            pass
    return saved


def main():
    parser = argparse.ArgumentParser(description="Fetch PubMed abstracts for species.")
    parser.add_argument("--max-per-species", type=int, default=15)
    parser.add_argument("--only", default=None, help="Only this scientific name.")
    parser.add_argument("--topic", default=None, help="Extra topic filter e.g. 'alarm call'")
    args = parser.parse_args()

    con = get_connection()

    if args.only:
        species = con.execute(
            "SELECT species_id, scientific_name FROM species WHERE scientific_name=?",
            (args.only,)
        ).fetchall()
    else:
        species = con.execute(
            "SELECT species_id, scientific_name FROM species ORDER BY common_name_en"
        ).fetchall()

    topic_filter = f' AND ("{args.topic}"[tiab])' if args.topic else ""
    total_saved = 0

    print(f"\nSearching PubMed for {len(species)} species"
          f"{' · topic: '+args.topic if args.topic else ''}...\n")

    for i, row in enumerate(species, 1):
        sid = row["species_id"]
        sci = row["scientific_name"]

        query = f'"{sci}"[tiab] AND {COMM_TERMS}{topic_filter}'
        print(f"[{i}/{len(species)}] {sci}", end="  ")

        pmids = esearch(query, args.max_per_species)
        time.sleep(DELAY)

        if not pmids:
            print("→ 0 results")
            continue

        papers = efetch(pmids)
        time.sleep(DELAY)

        n = save_papers(con, sid, papers)
        con.commit()
        total_saved += n
        print(f"→ {len(pmids)} found, {n} saved")

    from src.db import update_all_profile_levels
    update_all_profile_levels(con)

    # Summary
    total_papers = con.execute("SELECT COUNT(*) FROM papers WHERE source='pubmed'").fetchone()[0]
    with_abstract = con.execute("SELECT COUNT(*) FROM papers WHERE source='pubmed' AND abstract!=''").fetchone()[0]
    print(f"\n✓ Done: {total_saved} papers saved from PubMed")
    print(f"  Total PubMed papers in DB: {total_papers}")
    print(f"  With abstracts: {with_abstract}\n")


if __name__ == "__main__":
    main()
