"""
fix_all.py
----------
One-shot repair script for Zoe.Logos v2.x.

Reconciles the database with the actual code paths in src/db.py and src/db_v2.py.
Safe to run multiple times (idempotent). Backs up before destructive operations.

What it fixes:
  1. signal_terms / context_terms / function_terms column drift
  2. Dead/duplicate tables (claims_v2, research_topics duplication)
  3. Broken v_species_summary view
  4. Missing semiotic columns in species_metadata
  5. Unpopulated method_terms / research_topic_terms vocabulary
  6. Stale `source` column reference in compute_profile_level

Run:
    python fix_all.py              # diagnose + apply (with backup)
    python fix_all.py --dry-run    # diagnose only
    python fix_all.py --no-backup  # skip backup (faster but risky)
"""

from __future__ import annotations
import argparse
import shutil
import sqlite3
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(ROOT))

DB_PATH = ROOT / "data" / "zoe_logos.db"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_columns(con, table):
    return [r[1] for r in con.execute(f"PRAGMA table_info({table})").fetchall()]

def table_exists(con, name):
    return con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None

def view_exists(con, name):
    return con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='view' AND name=?", (name,)
    ).fetchone() is not None

def row_count(con, table):
    try:
        return con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    except Exception:
        return -1

def col_exists(con, table, col):
    return col in get_columns(con, table)


# ─────────────────────────────────────────────────────────────────────────────
# Diagnose
# ─────────────────────────────────────────────────────────────────────────────

def diagnose(con):
    issues = []

    # Schema drift on vocab tables
    if table_exists(con, "signal_terms"):
        cols = get_columns(con, "signal_terms")
        if "canonical_label" not in cols and "label" in cols:
            issues.append(("signal_terms", "needs column rename: label → canonical_label", "fix"))
        if "parent_signal_id" not in cols and "parent_id" in cols:
            issues.append(("signal_terms", "needs column rename: parent_id → parent_signal_id", "fix"))
        if "definition" not in cols:
            issues.append(("signal_terms", "missing column: definition", "fix"))
        if "scope_note" not in cols:
            issues.append(("signal_terms", "missing column: scope_note", "fix"))
        if "aliases_json" not in cols:
            issues.append(("signal_terms", "missing column: aliases_json", "fix"))

    if table_exists(con, "context_terms"):
        cols = get_columns(con, "context_terms")
        if "canonical_label" not in cols and "label" in cols:
            issues.append(("context_terms", "needs column rename: label → canonical_label", "fix"))
        if "parent_context_id" not in cols and "parent_id" in cols:
            issues.append(("context_terms", "needs column rename: parent_id → parent_context_id", "fix"))

    if table_exists(con, "function_terms"):
        cols = get_columns(con, "function_terms")
        if "canonical_label" not in cols and "label" in cols:
            issues.append(("function_terms", "needs column rename: label → canonical_label", "fix"))
        if "parent_function_id" not in cols and "parent_id" in cols:
            issues.append(("function_terms", "needs column rename: parent_id → parent_function_id", "fix"))

    # Dead tables
    if table_exists(con, "claims_v2") and row_count(con, "claims_v2") == 0:
        issues.append(("claims_v2", f"dead table (0 rows, communication_claims has {row_count(con, 'communication_claims')})", "fix"))

    if table_exists(con, "research_topics") and table_exists(con, "research_topic_terms"):
        rt = row_count(con, "research_topics")
        rtt = row_count(con, "research_topic_terms")
        if rt == 0 and rtt == 0:
            issues.append(("research_topics", "duplicate empty table (research_topic_terms also empty)", "fix"))

    # Missing columns on species_metadata for semiotic data
    if table_exists(con, "species_metadata"):
        cols = get_columns(con, "species_metadata")
        for needed in ["semiotic_class", "comm_level", "learning_basis", "referentiality", "signal_channel"]:
            if needed not in cols:
                issues.append(("species_metadata", f"missing semiotic column: {needed}", "fix"))

    # Broken view
    if view_exists(con, "v_species_summary"):
        try:
            con.execute("SELECT * FROM v_species_summary LIMIT 1").fetchone()
        except Exception as e:
            issues.append(("v_species_summary", f"broken view: {str(e)[:60]}", "fix"))

    # Duplicate species (different species_id, same scientific_name)
    if table_exists(con, "species"):
        n_dup = con.execute(
            "SELECT COUNT(*)-COUNT(DISTINCT scientific_name) FROM species"
        ).fetchone()[0]
        if n_dup > 0:
            issues.append(("species", f"{n_dup} duplicate rows (same scientific_name, different species_id)", "fix"))

    return issues


def print_diagnostic(con):
    print("\n── Schema diagnostic ─────────────────────────────────────")
    issues = diagnose(con)
    if not issues:
        print("  ✓ No issues found.")
        return issues
    for tbl, desc, sev in issues:
        marker = "✗" if sev == "fix" else "?"
        print(f"  {marker} {tbl}: {desc}")
    print(f"\n  Total: {len(issues)} issue(s)")
    return issues


# ─────────────────────────────────────────────────────────────────────────────
# Fixes
# ─────────────────────────────────────────────────────────────────────────────

def fix_signal_terms(con):
    """Rebuild signal_terms with the canonical schema, preserving data."""
    if not table_exists(con, "signal_terms"):
        return False

    cols = get_columns(con, "signal_terms")
    if "canonical_label" in cols and "parent_signal_id" in cols and "aliases_json" in cols:
        return False  # already fixed

    n = row_count(con, "signal_terms")
    print(f"   → rebuilding signal_terms ({n} rows preserved)")

    # Read existing data
    rows = con.execute("SELECT * FROM signal_terms").fetchall()

    con.execute("DROP TABLE IF EXISTS signal_terms_old")
    con.execute("ALTER TABLE signal_terms RENAME TO signal_terms_old")

    con.execute("""
        CREATE TABLE signal_terms (
            signal_id           TEXT PRIMARY KEY,
            canonical_label     TEXT NOT NULL,
            modality            TEXT NOT NULL DEFAULT 'unknown',
            parent_signal_id    TEXT REFERENCES signal_terms(signal_id),
            definition          TEXT DEFAULT '',
            scope_note          TEXT DEFAULT '',
            acoustic_descriptor TEXT DEFAULT '',
            aliases_json        TEXT DEFAULT '[]',
            created_at          TEXT DEFAULT (datetime('now'))
        )
    """)

    # Map old columns → new columns
    old_cols = [r[1] for r in con.execute("PRAGMA table_info(signal_terms_old)").fetchall()]
    has_label_old = "label" in old_cols
    has_parent_old = "parent_id" in old_cols
    has_family = "family" in old_cols
    has_desc = "description" in old_cols

    for row in rows:
        d = dict(row) if hasattr(row, 'keys') else {old_cols[i]: row[i] for i in range(len(old_cols))}
        con.execute("""
            INSERT OR IGNORE INTO signal_terms
            (signal_id, canonical_label, modality, parent_signal_id, definition, acoustic_descriptor)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            d.get("signal_id"),
            d.get("canonical_label") or d.get("label", ""),
            d.get("modality", "acoustic"),
            d.get("parent_signal_id") or d.get("parent_id"),
            d.get("definition") or d.get("description", ""),
            d.get("family", ""),
        ))

    con.execute("CREATE INDEX IF NOT EXISTS idx_signal_modality ON signal_terms(modality)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_signal_parent ON signal_terms(parent_signal_id)")
    con.commit()
    return True


def fix_context_terms(con):
    if not table_exists(con, "context_terms"):
        return False
    cols = get_columns(con, "context_terms")
    if "canonical_label" in cols and "parent_context_id" in cols:
        return False

    n = row_count(con, "context_terms")
    print(f"   → rebuilding context_terms ({n} rows preserved)")
    rows = con.execute("SELECT * FROM context_terms").fetchall()
    old_cols = [r[1] for r in con.execute("PRAGMA table_info(context_terms)").fetchall()]

    con.execute("DROP TABLE IF EXISTS context_terms_old")
    con.execute("ALTER TABLE context_terms RENAME TO context_terms_old")
    con.execute("""
        CREATE TABLE context_terms (
            context_id          TEXT PRIMARY KEY,
            canonical_label     TEXT NOT NULL,
            parent_context_id   TEXT REFERENCES context_terms(context_id),
            definition          TEXT DEFAULT '',
            scope_note          TEXT DEFAULT '',
            aliases_json        TEXT DEFAULT '[]',
            created_at          TEXT DEFAULT (datetime('now'))
        )
    """)
    for row in rows:
        d = {old_cols[i]: row[i] for i in range(len(old_cols))}
        con.execute("""
            INSERT OR IGNORE INTO context_terms
            (context_id, canonical_label, parent_context_id, definition)
            VALUES (?, ?, ?, ?)
        """, (
            d.get("context_id"),
            d.get("canonical_label") or d.get("label", ""),
            d.get("parent_context_id") or d.get("parent_id"),
            d.get("definition") or d.get("description", ""),
        ))
    con.commit()
    return True


def fix_function_terms(con):
    if not table_exists(con, "function_terms"):
        return False
    cols = get_columns(con, "function_terms")
    if "canonical_label" in cols and "parent_function_id" in cols:
        return False

    n = row_count(con, "function_terms")
    print(f"   → rebuilding function_terms ({n} rows preserved)")
    rows = con.execute("SELECT * FROM function_terms").fetchall()
    old_cols = [r[1] for r in con.execute("PRAGMA table_info(function_terms)").fetchall()]

    con.execute("DROP TABLE IF EXISTS function_terms_old")
    con.execute("ALTER TABLE function_terms RENAME TO function_terms_old")
    con.execute("""
        CREATE TABLE function_terms (
            function_id         TEXT PRIMARY KEY,
            canonical_label     TEXT NOT NULL,
            parent_function_id  TEXT REFERENCES function_terms(function_id),
            level               TEXT DEFAULT 'biological',
            receiver            TEXT DEFAULT 'unknown',
            definition          TEXT DEFAULT '',
            scope_note          TEXT DEFAULT '',
            aliases_json        TEXT DEFAULT '[]',
            created_at          TEXT DEFAULT (datetime('now'))
        )
    """)
    for row in rows:
        d = {old_cols[i]: row[i] for i in range(len(old_cols))}
        con.execute("""
            INSERT OR IGNORE INTO function_terms
            (function_id, canonical_label, parent_function_id, level, receiver, definition)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            d.get("function_id"),
            d.get("canonical_label") or d.get("label", ""),
            d.get("parent_function_id") or d.get("parent_id"),
            d.get("level", "biological"),
            d.get("receiver", "unknown"),
            d.get("definition") or d.get("description", ""),
        ))
    con.commit()
    return True


def fix_species_duplicates(con):
    """
    Merge species rows with the same scientific_name but different species_id.
    Picks the row with most papers/claims as canonical, redirects all FK refs to it.
    """
    dups = con.execute("""
        SELECT scientific_name, COUNT(*) n
        FROM species
        GROUP BY scientific_name
        HAVING n > 1
    """).fetchall()

    if not dups:
        return False

    print(f"   → found {len(dups)} duplicated scientific_names, merging…")
    merged = 0

    for d in dups:
        sci = d["scientific_name"]
        rows = con.execute("""
            SELECT species_id,
                (SELECT COUNT(*) FROM paper_species WHERE species_id=s.species_id) as np,
                (SELECT COUNT(*) FROM communication_claims WHERE species_id=s.species_id) as nc
            FROM species s WHERE scientific_name=?
            ORDER BY (np+nc) DESC
        """, (sci,)).fetchall()

        if len(rows) < 2:
            continue

        keeper = rows[0]["species_id"]
        losers = [r["species_id"] for r in rows[1:]]

        # Redirect all FK references from losers → keeper
        for loser in losers:
            for table, col in [("paper_species","species_id"), ("communication_claims","species_id"),
                              ("open_literature","species_id"), ("recording_assets","species_id"),
                              ("signal_annotations","species_id"), ("species_synonyms","species_id"),
                              ("media_assets","species_id")]:
                if not table_exists(con, table):
                    continue
                try:
                    # First, check if there'd be a primary-key conflict
                    if table == "paper_species":
                        # Composite PK (paper_id, species_id) — handle dedup
                        con.execute("""
                            DELETE FROM paper_species
                            WHERE species_id=? AND paper_id IN (
                                SELECT paper_id FROM paper_species WHERE species_id=?
                            )
                        """, (loser, keeper))
                    elif table == "open_literature":
                        con.execute("""
                            DELETE FROM open_literature
                            WHERE species_id=? AND doi IN (
                                SELECT doi FROM open_literature WHERE species_id=?
                            )
                        """, (loser, keeper))
                    con.execute(f"UPDATE {table} SET {col}=? WHERE {col}=?", (keeper, loser))
                except sqlite3.IntegrityError:
                    # Unique constraint — skip silently
                    pass

            # Delete species_metadata for loser, then species
            con.execute("DELETE FROM species_metadata WHERE species_id=?", (loser,))
            con.execute("DELETE FROM species WHERE species_id=?", (loser,))
            merged += 1

    con.commit()
    print(f"   → merged {merged} duplicate species into canonical entries")
    return merged > 0


def fix_dead_tables(con):
    """Drop empty duplicate tables that won't be used."""
    fixed = 0
    if table_exists(con, "claims_v2") and row_count(con, "claims_v2") == 0:
        con.execute("DROP TABLE claims_v2")
        print("   → dropped empty claims_v2")
        fixed += 1
    if table_exists(con, "research_topics") and row_count(con, "research_topics") == 0:
        # keep research_topic_terms (canonical name in src/db.py)
        con.execute("DROP TABLE research_topics")
        print("   → dropped empty research_topics (keeping research_topic_terms)")
        fixed += 1
    con.commit()
    return fixed > 0


def fix_species_metadata(con):
    """Add semiotic columns to species_metadata."""
    if not table_exists(con, "species_metadata"):
        return False
    cols = get_columns(con, "species_metadata")
    added = 0
    for col, default in [
        ("semiotic_class",  "'unknown'"),
        ("comm_level",      "'unknown'"),
        ("referentiality",  "'unknown'"),
        ("learning_basis",  "'unknown'"),
        ("signal_channel",  "'unknown'"),
        ("notes",           "''"),
    ]:
        if col not in cols:
            try:
                con.execute(f"ALTER TABLE species_metadata ADD COLUMN {col} TEXT DEFAULT {default}")
                added += 1
            except sqlite3.OperationalError as e:
                if "duplicate" not in str(e).lower():
                    raise
    if added:
        print(f"   → added {added} semiotic columns to species_metadata")
        con.commit()
    return added > 0


def fix_views(con):
    """Recreate v_species_summary with correct schema (always rebuild)."""
    con.execute("DROP VIEW IF EXISTS v_species_summary")
    con.execute("""
        CREATE VIEW v_species_summary AS
        SELECT
            s.species_id, s.scientific_name, s.common_name_en,
            s.class_, s.order_, s.family,
            sm.image_url,
            sm.semiotic_class, sm.comm_level, sm.learning_basis,
            (SELECT COUNT(DISTINCT ps.paper_id) FROM paper_species ps
             WHERE ps.species_id = s.species_id) AS paper_count,
            (SELECT COUNT(*) FROM communication_claims cc
             WHERE cc.species_id = s.species_id) AS claim_count,
            (SELECT COUNT(*) FROM communication_claims cc
             WHERE cc.species_id = s.species_id
               AND cc.curation_status='curated') AS curated_count,
            (SELECT COUNT(*) FROM recording_assets ra
             WHERE ra.species_id = s.species_id) AS recording_count
        FROM species s
        LEFT JOIN species_metadata sm ON s.species_id = sm.species_id
    """)
    print("   → recreated v_species_summary view")
    con.commit()
    return True


def populate_semiotic_data(con):
    """Backfill semiotic data from scripts/species_database.py if available."""
    try:
        import scripts.species_database as sdb
    except Exception as e:
        print(f"   ! cannot import species_database: {e}")
        return False

    species_lookup = {}
    for sp in getattr(sdb, "SPECIES", []):
        species_lookup[sp["sci"]] = sp

    if not species_lookup:
        print("   ! species_database.SPECIES is empty")
        return False

    n_updated = 0
    for sp_row in con.execute("SELECT species_id, scientific_name FROM species"):
        sp_data = species_lookup.get(sp_row["scientific_name"])
        if not sp_data:
            continue
        con.execute("""
            INSERT OR IGNORE INTO species_metadata (species_id) VALUES (?)
        """, (sp_row["species_id"],))
        con.execute("""
            UPDATE species_metadata SET
                semiotic_class = ?,
                comm_level = ?,
                referentiality = ?,
                learning_basis = ?,
                signal_channel = ?,
                notes = ?
            WHERE species_id = ?
        """, (
            sp_data.get("semiotic", "unknown"),
            sp_data.get("comm_level", "unknown"),
            sp_data.get("referentiality", "unknown"),
            sp_data.get("learning", "unknown"),
            sp_data.get("channel", "unknown"),
            sp_data.get("notes", ""),
            sp_row["species_id"],
        ))
        n_updated += 1

    con.commit()
    if n_updated:
        print(f"   → backfilled semiotic data for {n_updated} species")
    return n_updated > 0


def patch_compute_profile_level(con):
    """Patch the SQL in src/db.py to not reference stale `source` column."""
    db_py = ROOT / "src" / "db.py"
    if not db_py.exists():
        return False
    text = db_py.read_text()

    # Old line — reference stale `source` column
    bad = "(SELECT COUNT(*) FROM communication_claims WHERE species_id=? AND source='extraction') AS v1_extracted"
    if bad not in text:
        return False

    # Replace single-line bad SQL with single-line correct SQL
    fixed = (
        "(SELECT COUNT(*) FROM claim_evidence ce "
        "JOIN communication_claims cc ON ce.claim_id = cc.claim_id "
        "WHERE cc.species_id=? AND ce.extraction_method IN ('llm','manual','curated')) AS v1_extracted"
    )
    text = text.replace(bad, fixed)
    db_py.write_text(text)
    print(f"   → patched src/db.py compute_profile_level")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def recreate_default_views(con):
    """Recreate all canonical views after table fixes."""
    # v_claim_evidence_full
    con.execute("DROP VIEW IF EXISTS v_claim_evidence_full")
    con.execute("""
        CREATE VIEW v_claim_evidence_full AS
        SELECT
            cc.claim_id, cc.species_id,
            s.scientific_name, s.common_name_en,
            sig.canonical_label AS signal_label, sig.signal_id,
            ctx.canonical_label AS context_label, ctx.context_id,
            fn.canonical_label  AS function_label, fn.function_id, fn.level AS function_level,
            cc.confidence AS claim_confidence, cc.curation_status,
            ce.evidence_id, ce.paper_id, ce.evidence_text, ce.support_level,
            ce.confidence AS evidence_confidence, ce.extraction_method,
            p.title AS paper_title, p.year, p.doi, p.journal
        FROM communication_claims cc
        JOIN species s ON cc.species_id = s.species_id
        LEFT JOIN signal_terms   sig ON cc.signal_id   = sig.signal_id
        LEFT JOIN context_terms  ctx ON cc.context_id  = ctx.context_id
        LEFT JOIN function_terms fn  ON cc.function_id = fn.function_id
        LEFT JOIN claim_evidence ce  ON cc.claim_id    = ce.claim_id
        LEFT JOIN papers p           ON ce.paper_id    = p.paper_id
    """)
    # species_summary (legacy convenience)
    con.execute("DROP VIEW IF EXISTS species_summary")
    con.execute("""
        CREATE VIEW species_summary AS
        SELECT s.species_id, s.scientific_name, s.common_name_en, s.class_, s.order_, s.family,
               sm.image_url, s.profile_level
        FROM species s
        LEFT JOIN species_metadata sm ON s.species_id = sm.species_id
    """)
    print("   → recreated views (v_claim_evidence_full, species_summary)")
    con.commit()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Diagnose only")
    ap.add_argument("--no-backup", action="store_true", help="Skip DB backup")
    args = ap.parse_args()

    print(f"\n🔧 Zoe.Logos fix_all")
    print(f"   DB: {DB_PATH}")

    if not DB_PATH.exists():
        print("   ! DB does not exist. Run setup_v2.py first.")
        return

    print(f"   Size: {DB_PATH.stat().st_size // 1024} KB")

    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=OFF")  # turn off during reorg

    issues = print_diagnostic(con)

    if not issues:
        print("\n✓ Database is consistent. Nothing to fix.\n")
        return

    if args.dry_run:
        print("\n→ Run without --dry-run to apply fixes.\n")
        return

    # Backup
    if not args.no_backup:
        backup = DB_PATH.with_suffix(f".backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.db")
        shutil.copy2(DB_PATH, backup)
        print(f"\n   ✓ Backup created: {backup.name}")

    print("\n── Applying fixes ──────────────────────────────────────")
    # IMPORTANT: drop broken views FIRST so they don't block table renames
    for view_name in ["v_species_summary", "v_claim_evidence_full", "species_summary",
                      "vocalisation_counts", "function_counts"]:
        if view_exists(con, view_name):
            try:
                con.execute(f"DROP VIEW {view_name}")
            except Exception:
                pass
    con.commit()
    print("   → dropped views temporarily (will recreate at the end)")

    fix_signal_terms(con)
    fix_context_terms(con)
    fix_function_terms(con)
    fix_species_duplicates(con)
    fix_dead_tables(con)
    fix_species_metadata(con)
    populate_semiotic_data(con)
    fix_views(con)
    recreate_default_views(con)
    patch_compute_profile_level(con)

    con.execute("PRAGMA foreign_keys=ON")
    con.commit()
    con.close()

    # Re-diagnose
    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    print("\n── Post-fix diagnostic ─────────────────────────────────")
    remaining = diagnose(con)
    if not remaining:
        print("  ✓ All issues resolved.")
    else:
        print(f"  ! {len(remaining)} issue(s) remain:")
        for tbl, desc, _ in remaining:
            print(f"     {tbl}: {desc}")

    print("\n✓ fix_all complete.\n")
    print("Recommended next steps:")
    print("  1. python setup_v2.py                   # verify schema")
    print("  2. python scripts/06_fetch_literature.py --refresh-abstracts")
    print("  3. python scripts/09_extract_claims.py --limit 200")
    print("  4. python scripts/07_export_web.py")
    print()


if __name__ == "__main__":
    main()
