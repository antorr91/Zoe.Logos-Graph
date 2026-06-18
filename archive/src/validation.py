"""
validation.py
-------------
Validates extracted paper records against the Zoe.Logos-Graph schema.

Usage:
    python -m src.validation --input data/annotations/pilot.json
    python -m src.validation --input data/processed/extracted.json --strict
"""

from __future__ import annotations

import json
import sys
import argparse
from pathlib import Path
from typing import List, Optional, Tuple

from pydantic import ValidationError

from src.schema import PaperRecord


# ---------------------------------------------------------------------------
# Core validation
# ---------------------------------------------------------------------------

def validate_record(raw: dict) -> Tuple[Optional[PaperRecord], List[str]]:
    """
    Validate a single raw dict against PaperRecord.

    Returns:
        (record, errors) — record is None if validation failed.
    """
    try:
        record = PaperRecord(**raw)
        return record, []
    except ValidationError as e:
        errors = [f"{err['loc']}: {err['msg']}" for err in e.errors()]
        return None, errors


def validate_file(
    path: Path,
    strict: bool = False,
) -> Tuple[List[PaperRecord], List[dict]]:
    """
    Validate all records in a JSON file (list or single object).

    Args:
        path:   Path to the JSON file.
        strict: If True, raise on first error. If False, collect all errors.

    Returns:
        (valid_records, error_reports)
    """
    raw_data = json.loads(path.read_text(encoding="utf-8"))

    # Accept both a list and a single record
    if isinstance(raw_data, dict):
        raw_data = [raw_data]

    valid: List[PaperRecord] = []
    errors: List[dict] = []

    for i, raw in enumerate(raw_data):
        record, errs = validate_record(raw)
        paper_id = raw.get("paper_id", f"index_{i}")

        if errs:
            report = {"paper_id": paper_id, "errors": errs}
            errors.append(report)
            if strict:
                raise ValueError(f"Validation failed for {paper_id}:\n" + "\n".join(errs))
        else:
            valid.append(record)

    return valid, errors


# ---------------------------------------------------------------------------
# Field-level checks (beyond Pydantic)
# ---------------------------------------------------------------------------

WARN_IF_EMPTY = [
    "vocalisation_type",
    "behavioural_context",
    "putative_function",
    "analysis_method",
]

def soft_checks(record: PaperRecord) -> List[str]:
    """
    Return a list of soft warnings for a valid record.
    These do not fail validation but flag low-confidence extractions.
    """
    warnings = []

    for field in WARN_IF_EMPTY:
        if not getattr(record, field):
            warnings.append(f"Field '{field}' is empty — consider adding 'unknown' or reviewing abstract.")

    if record.species_scientific_name == "unknown":
        warnings.append("Species scientific name is 'unknown' — check if it appears in the abstract.")

    if len(record.main_outcome) > 300:
        warnings.append("main_outcome is long (>300 chars) — consider shortening.")

    if record.year and record.year < 1950:
        warnings.append(f"Year {record.year} is unusually early for this domain.")

    return warnings


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_report(
    valid: List[PaperRecord],
    errors: List[dict],
    warnings: dict,
) -> None:
    total = len(valid) + len(errors)
    print(f"\n{'='*50}")
    print(f"Zoe.Logos-Graph — Validation Report")
    print(f"{'='*50}")
    print(f"Total records:  {total}")
    print(f"Valid:          {len(valid)}")
    print(f"Invalid:        {len(errors)}")
    print()

    if errors:
        print("── ERRORS ──────────────────────────────────────")
        for e in errors:
            print(f"  [{e['paper_id']}]")
            for err in e["errors"]:
                print(f"    ✗ {err}")
        print()

    if warnings:
        print("── WARNINGS ────────────────────────────────────")
        for paper_id, w_list in warnings.items():
            print(f"  [{paper_id}]")
            for w in w_list:
                print(f"    ⚠  {w}")
        print()

    print(f"{'='*50}\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Validate Zoe.Logos-Graph extraction records."
    )
    parser.add_argument("--input", required=True, help="Path to JSON file of records.")
    parser.add_argument(
        "--strict", action="store_true", help="Stop on first validation error."
    )
    args = parser.parse_args()

    path = Path(args.input)
    if not path.exists():
        print(f"Error: file not found: {path}", file=sys.stderr)
        sys.exit(1)

    valid, errors = validate_file(path, strict=args.strict)

    warnings = {}
    for record in valid:
        w = soft_checks(record)
        if w:
            warnings[record.paper_id] = w

    print_report(valid, errors, warnings)

    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
