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

    # ── Papers ────────────────────────────────────────────────────────────────
    papers_rows = con.execute("""
        SELECT p.paper_id, p.title, p.year, p.doi, p.abstract, p.journal,
               p.open_access, p.source
        FROM papers p
        JOIN paper_species ps ON p.paper_id = ps.paper_id
        WHERE ps.species_id = ?
        ORDER BY p.year DESC
    """, (sid,)).fetchall()
    papers = [dict(r) for r in papers_rows]

    # ── Communication claims (v2 schema) ──────────────────────────────────────
    claims_rows = con.execute("""
        SELECT
            cc.claim_id, cc.confidence, cc.curation_status,
            sig.canonical_label AS signal_label,
            ctx.canonical_label AS context_label,
            fn.canonical_label  AS function_label,
            ce.evidence_text, ce.support_level, ce.extraction_method,
            ce.paper_id AS evidence_paper_id,
            p.doi AS evidence_doi, p.year AS evidence_year,
            p.title AS evidence_paper_title,
            (SELECT COUNT(*) FROM claim_evidence ce2
             WHERE ce2.claim_id = cc.claim_id) AS evidence_count
        FROM communication_claims cc
        LEFT JOIN signal_terms  sig ON cc.signal_id   = sig.signal_id
        LEFT JOIN context_terms ctx ON cc.context_id  = ctx.context_id
        LEFT JOIN function_terms fn ON cc.function_id = fn.function_id
        LEFT JOIN claim_evidence ce ON cc.claim_id    = ce.claim_id
        LEFT JOIN papers p          ON ce.paper_id    = p.paper_id
        WHERE cc.species_id = ?
        GROUP BY cc.claim_id
        ORDER BY cc.confidence DESC
    """, (sid,)).fetchall()

    vocalisations, contexts, functions, claims_full = [], [], [], []
    seen_v, seen_c, seen_f, seen_cid = set(), set(), set(), set()
    for r in claims_rows:
        cid = r["claim_id"]
        if cid in seen_cid:
            continue
        seen_cid.add(cid)
        conf = round(r["confidence"] or 0.5, 2)
        src  = r["extraction_method"] or "seed"
        ec   = r["evidence_count"] or 0
        if r["signal_label"] and r["signal_label"] not in seen_v:
            seen_v.add(r["signal_label"])
            vocalisations.append({"value": r["signal_label"], "confidence": conf,
                                  "source": src, "evidence_count": ec})
        if r["context_label"] and r["context_label"] not in seen_c:
            seen_c.add(r["context_label"])
            contexts.append({"value": r["context_label"], "confidence": conf,
                             "source": src, "evidence_count": ec})
        if r["function_label"] and r["function_label"] not in seen_f:
            seen_f.add(r["function_label"])
            functions.append({"value": r["function_label"], "confidence": conf,
                              "source": src, "evidence_count": ec})
        claims_full.append({
            "claim_id": cid, "confidence": conf,
            "curation_status": r["curation_status"] or "seed",
            "evidence_count": ec,
            "evidence_text": r["evidence_text"] or "",
            "support_level": r["support_level"] or "",
            "extraction_method": src,
            "paper_id": r["evidence_paper_id"] or "",
            "paper_title": r["evidence_paper_title"] or "",
            "doi": r["evidence_doi"] or "",
            "year": r["evidence_year"],
        })

    # ── Recordings (recording_assets) ─────────────────────────────────────────
    rec_rows = con.execute("""
        SELECT ra.*, sp.image_path AS spectrogram_path
        FROM recording_assets ra
        LEFT JOIN (SELECT recording_id, image_path FROM spectrograms
                   GROUP BY recording_id) sp ON sp.recording_id = ra.recording_id
        WHERE ra.species_id = ?
    """, (sid,)).fetchall()
    audio_recs = []
    for r in rec_rows:
        r = dict(r)
        audio_recs.append({
            "id":          r.get("recording_id",""),
            "provider":    r.get("provider",""),
            "provider_id": r.get("provider_id",""),
            "type":        r.get("title","vocalisation"),
            "rec":         r.get("recorded_by",""),
            "loc":         r.get("location",""),
            "date":        r.get("recorded_date",""),
            "url":         r.get("url",""),
            "audio":       r.get("audio_url","") or r.get("audio_path",""),
            "sono":        r.get("spectrogram_path","") or "",
            "license":     r.get("license",""),
            "attribution": r.get("attribution",""),
        })

    # ── Open literature DOIs ──────────────────────────────────────────────────
    dois_rows = con.execute("""
        SELECT doi, url, title, year, source FROM open_literature
        WHERE species_id=? ORDER BY year DESC
    """, (sid,)).fetchall()
    open_dois = [dict(r) for r in dois_rows]

    profile_level = sp.get("profile_level", "basic")
    paper_count   = len(papers)
    claim_count   = len(claims_full)
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
            "recording_count": len(audio_recs),
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
        "vocalisations": [c["value"] for c in vocalisations],
        "contexts":      [c["value"] for c in contexts],
        "functions":     [c["value"] for c in functions],
        "communication_profile": {
            "vocalisations": vocalisations,
            "contexts":      contexts,
            "functions":     functions,
            "methods":       [],
        },
        "claims": claims_full,

        # ── Audio ─────────────────────────────────────────────────────────────
        "audio": {
            "provider":       "xeno_canto" if audio_recs else "external_links",
            "xc_query":       sp.get("xeno_canto_query", sp.get("scientific_name","")),
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