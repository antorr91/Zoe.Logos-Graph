"""
setup_v2.py
-----------
One-shot initializer for Zoe.Logos v2.x.

Run this BEFORE any other pipeline step to ensure all v2 tables exist.

Usage:
    python setup_v2.py

If the DB has schema drift, run fix_all.py first:
    python fix_all.py
    python setup_v2.py
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(ROOT))

from src.db import get_connection, init_db, DEFAULT_DB_PATH


def fmt_size(p: Path) -> str:
    if not p.exists():
        return "(does not exist yet)"
    n = p.stat().st_size
    if n < 1024**2:
        return f"{n/1024:.0f} KB"
    return f"{n/1024**2:.1f} MB"


EXPECTED_TABLES = [
    "species", "species_metadata", "species_synonyms",
    "papers", "paper_species", "open_literature",
    "signal_terms", "signal_aliases",
    "context_terms", "function_terms", "method_terms", "research_topic_terms",
    "communication_claims", "claim_evidence",
    "recording_assets", "signal_annotations", "spectrograms",
    "vocab_suggestions",
]


def main():
    print(f"\n🔧 Zoe.Logos — Setup v2.1")
    print(f"   Database: {DEFAULT_DB_PATH} ({fmt_size(DEFAULT_DB_PATH)})")
    print("─" * 60)

    con = get_connection()
    existing = {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}

    print("→ Ensuring v2 schema exists...")
    try:
        init_db(con)
        print("  ✓ Schema OK")
    except Exception as e:
        print(f"  ✗ init_db failed: {e}")
        print()
        print("  Schema drift detected. Please run:")
        print("    python fix_all.py")
        print("  Then retry: python setup_v2.py")
        return

    after = {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    new = sorted(after - existing)
    if new:
        print(f"  Created {len(new)} new tables: {new}")

    print()
    print("→ Database state:")
    all_ok = True
    for t in EXPECTED_TABLES:
        if t in after:
            n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            print(f"   ✓ {t:35s} {n:>6} rows")
        else:
            print(f"   ✗ {t:35s} MISSING")
            all_ok = False

    print()
    if all_ok:
        print("✓ All tables present. Ready to run pipeline.\n")
        print("Next steps:")
        print("  python scripts/02_fetch_species_metadata.py")
        print("  python scripts/06_fetch_literature.py")
        print("  python scripts/09_extract_claims.py --limit 200")
        print("  python scripts/07_export_web.py")
    else:
        print("⚠ Some tables are missing. Run: python fix_all.py")
    print()


if __name__ == "__main__":
    main()
