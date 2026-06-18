"""
scripts/db_migrate_v2.py
-------------------------
Migrate an existing v1 Zoe.Logos database into the v2 schema.

What this does:
  1. Renames v1 communication_claims to communication_claims_v1 (backup).
  2. Creates new v2 tables (CommunicationClaim + ClaimEvidence + controlled vocab).
  3. Builds controlled vocabulary entries from v1 free-text claim values.
  4. Reconstructs CommunicationClaims as joined records (species + signal + context + function).
  5. Creates ClaimEvidence records linking each claim to its source paper.

Usage:
    python scripts/db_migrate_v2.py
    python scripts/db_migrate_v2.py --dry-run
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.db_v2 import get_connection, SCHEMA_V2


def backup_v1_table(con):
    """Rename old communication_claims to communication_claims_v1 if present."""
    # Check if v1-shape exists (has claim_type, value columns)
    cols = [r[1] for r in con.execute("PRAGMA table_info(communication_claims)").fetchall()]
    if "claim_type" in cols and "value" in cols:
        # This is v1 schema — back it up
        try:
            con.execute("ALTER TABLE communication_claims RENAME TO communication_claims_v1")
            con.commit()
            print("✓ Backed up v1 communication_claims → communication_claims_v1")
            return True
        except Exception as e:
            print(f"  Note: {e}")
            return False
    elif "signal_id" in cols:
        print("✓ communication_claims is already v2 shape")
        return False
    return False


def build_vocab_from_v1(con):
    """Extract controlled vocabulary entries from v1 free-text claim values."""
    counts = {"signal": 0, "context": 0, "function": 0}

    if not table_exists(con, "communication_claims_v1"):
        print("  No v1 table to extract vocabulary from.")
        return counts

    # Vocalisation types → signal_terms
    rows = con.execute("""
        SELECT DISTINCT value FROM communication_claims_v1 WHERE claim_type='vocalisation'
    """).fetchall()
    for r in rows:
        val = r[0].strip()
        if not val: continue
        slug = slugify(val)
        # Determine signal family heuristically
        family = "call" if "call" in val.lower() else \
                 "song" if "song" in val.lower() else \
                 "click" if "click" in val.lower() else \
                 "whistle" if "whistle" in val.lower() else \
                 "drumming" if "drum" in val.lower() else ""
        modality = "acoustic"
        cur = con.execute("""
            INSERT OR IGNORE INTO signal_terms (signal_id, label, family, modality, description)
            VALUES (?, ?, ?, ?, ?)
        """, (slug, val, family, modality, ""))
        if cur.rowcount:
            counts["signal"] += 1

    # Contexts → context_terms
    rows = con.execute("""
        SELECT DISTINCT value FROM communication_claims_v1 WHERE claim_type='context'
    """).fetchall()
    for r in rows:
        val = r[0].strip()
        if not val: continue
        slug = slugify(val)
        cur = con.execute("INSERT OR IGNORE INTO context_terms (context_id, label) VALUES (?, ?)",
                         (slug, val))
        if cur.rowcount:
            counts["context"] += 1

    # Functions → function_terms (level inferred where possible)
    rows = con.execute("""
        SELECT DISTINCT value FROM communication_claims_v1 WHERE claim_type='function'
    """).fetchall()
    for r in rows:
        val = r[0].strip()
        if not val: continue
        slug = slugify(val)
        # Heuristic level assignment
        v = val.lower()
        if any(w in v for w in ["mate attraction","male competition","territory","predator avoid"]):
            level = "biological"
        elif any(w in v for w in ["identity","encoding","signal","recognition","information"]):
            level = "communicative"
        elif any(w in v for w in ["response","retrieval","approach","flee","attention","sharing"]):
            level = "pragmatic"
        else:
            level = "biological"
        cur = con.execute("""
            INSERT OR IGNORE INTO function_terms (function_id, label, level)
            VALUES (?, ?, ?)
        """, (slug, val, level))
        if cur.rowcount:
            counts["function"] += 1

    con.commit()
    return counts


def reconstruct_claims_from_v1(con):
    """
    Build CommunicationClaim records by joining v1 free-text rows.

    In v1, three rows might describe one biological claim:
      species=vervet, type=vocalisation, value=alarm_call, paper=p1
      species=vervet, type=context, value=predator_response, paper=p1
      species=vervet, type=function, value=predator_warning, paper=p1

    These collapse into one CommunicationClaim with one ClaimEvidence linked to p1.
    """
    if not table_exists(con, "communication_claims_v1"):
        return 0

    # Group by (species, paper) — within a group, take cartesian product of signal x context x function
    grouped = {}
    for row in con.execute("SELECT * FROM communication_claims_v1"):
        sid = row["species_id"]
        pid = row["paper_id"] or ""
        ct, val = row["claim_type"], slugify(row["value"])
        src = row["source"] or "seed"
        conf = row["confidence"] or 0.5

        key = (sid, pid)
        if key not in grouped:
            grouped[key] = {"signals":set(),"contexts":set(),"functions":set(),
                            "sources":set(),"confidence":conf}
        if ct == "vocalisation": grouped[key]["signals"].add(val)
        elif ct == "context":    grouped[key]["contexts"].add(val)
        elif ct == "function":   grouped[key]["functions"].add(val)
        grouped[key]["sources"].add(src)
        grouped[key]["confidence"] = max(grouped[key]["confidence"], conf)

    n_claims = n_evidence = 0
    for (sid, pid), data in grouped.items():
        signals = list(data["signals"]) or [None]
        contexts = list(data["contexts"]) or [None]
        functions = list(data["functions"]) or [None]

        for sig in signals:
            for ctx in contexts:
                for fn in functions:
                    if sig is None and ctx is None and fn is None:
                        continue
                    cur = con.execute("""
                        INSERT OR IGNORE INTO communication_claims
                        (species_id, signal_id, context_id, function_id, confidence, curation_status)
                        VALUES (?, ?, ?, ?, ?, 'seed')
                    """, (sid, sig, ctx, fn, data["confidence"]))
                    if cur.rowcount:
                        n_claims += 1
                        claim_id = cur.lastrowid
                    else:
                        # already exists — find it
                        existing = con.execute("""
                            SELECT claim_id FROM communication_claims
                            WHERE species_id=? AND
                                  COALESCE(signal_id,'')=COALESCE(?,'') AND
                                  COALESCE(context_id,'')=COALESCE(?,'') AND
                                  COALESCE(function_id,'')=COALESCE(?,'')
                        """, (sid, sig, ctx, fn)).fetchone()
                        claim_id = existing[0] if existing else None

                    if claim_id and pid:
                        # Add ClaimEvidence
                        for src in data["sources"]:
                            extraction = "seed" if src == "seed" else "llm" if "extract" in src else "manual"
                            support = "explicit" if src == "extraction" else "inferred"
                            con.execute("""
                                INSERT INTO claim_evidence
                                (claim_id, paper_id, support_level, extraction_method, confidence, source_type)
                                VALUES (?, ?, ?, ?, ?, 'paper')
                            """, (claim_id, pid, support, extraction, data["confidence"]))
                            n_evidence += 1
                    elif claim_id:
                        # Seed-only claim — single evidence record without paper
                        con.execute("""
                            INSERT INTO claim_evidence
                            (claim_id, support_level, extraction_method, confidence, source_type)
                            VALUES (?, 'inferred', 'seed', ?, 'paper')
                        """, (claim_id, data["confidence"]))
                        n_evidence += 1

    con.commit()
    return n_claims, n_evidence


def queue_review_items(con):
    """Add curation items for problematic data."""
    n = 0

    # Claims without any paper-backed evidence
    for row in con.execute("""
        SELECT cc.claim_id FROM communication_claims cc
        WHERE NOT EXISTS (
            SELECT 1 FROM claim_evidence ce
            WHERE ce.claim_id = cc.claim_id AND ce.paper_id IS NOT NULL
        )
    """).fetchall():
        con.execute("""
            INSERT INTO review_queue (item_type, item_id, issue, severity, suggested_fix)
            VALUES ('claim', ?, 'No paper-backed evidence', 'medium', 'Run scripts/09_extract_claims.py to find supporting literature')
        """, (str(row["claim_id"]),))
        n += 1

    # Papers without DOI
    for row in con.execute("SELECT paper_id FROM papers WHERE doi IS NULL OR doi=''").fetchall():
        con.execute("""
            INSERT INTO review_queue (item_type, item_id, issue, severity, suggested_fix)
            VALUES ('paper', ?, 'Missing DOI', 'low', 'Look up DOI via Crossref or OpenAlex')
        """, (row["paper_id"],))
        n += 1

    # Recordings without license
    for row in con.execute("""
        SELECT recording_id FROM recording_assets WHERE license IS NULL OR license=''
    """).fetchall():
        con.execute("""
            INSERT INTO review_queue (item_type, item_id, issue, severity, suggested_fix)
            VALUES ('recording', ?, 'Missing license', 'high', 'Add license metadata before reuse')
        """, (row["recording_id"],))
        n += 1

    con.commit()
    return n


def slugify(s):
    return s.strip().lower().replace(" ","_").replace("-","_").replace("/","_")


def table_exists(con, name):
    return con.execute("""
        SELECT 1 FROM sqlite_master WHERE type='table' AND name=?
    """, (name,)).fetchone() is not None


def print_stats(con):
    print(f"\n{'='*60}")
    print("Zoe.Logos v2 — Database state")
    print(f"{'='*60}")
    tables = ["species","signal_terms","context_terms","function_terms",
              "papers","communication_claims","claim_evidence",
              "recording_assets","signal_annotations","spectrograms","review_queue"]
    for t in tables:
        if table_exists(con, t):
            n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            print(f"  {t:30s} {n:>6}")

    if table_exists(con, "communication_claims"):
        print()
        print("  Curation status:")
        for r in con.execute("""
            SELECT curation_status, COUNT(*) n FROM communication_claims
            GROUP BY curation_status ORDER BY n DESC
        """):
            print(f"    {r['curation_status']:20s} {r['n']:>5}")
        print()
        print("  Evidence by extraction method:")
        for r in con.execute("""
            SELECT extraction_method, COUNT(*) n FROM claim_evidence
            GROUP BY extraction_method ORDER BY n DESC
        """):
            print(f"    {r['extraction_method']:20s} {r['n']:>5}")
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    con = get_connection()

    print("→ Backing up v1 communication_claims (if exists)...")
    backup_v1_table(con)

    print("→ Initialising v2 schema...")
    con.executescript(SCHEMA_V2)
    con.commit()

    print("→ Building controlled vocabulary from v1 data...")
    vocab_counts = build_vocab_from_v1(con)
    if vocab_counts:
        for k, v in vocab_counts.items():
            print(f"    {k}_terms: {v} new entries")

    print("→ Reconstructing claims + evidence from v1...")
    result = reconstruct_claims_from_v1(con)
    if result:
        n_claims, n_evidence = result
        print(f"    {n_claims} claims, {n_evidence} evidence records")

    print("→ Populating review queue...")
    n = queue_review_items(con)
    print(f"    {n} items queued for review")

    print_stats(con)
    print("✓ Migration complete. v1 data preserved in communication_claims_v1.\n")


if __name__ == "__main__":
    main()
