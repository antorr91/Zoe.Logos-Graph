"""
tests/test_validation.py
------------------------
Tests for the validation layer.
"""

import json
import pytest
from pathlib import Path

from src.schema import PaperRecord, DatasetAvailability
from src.validation import validate_record, soft_checks


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VALID_RECORD = {
    "paper_id": "test_001",
    "title": "Test paper on zebra finch song",
    "year": 2023,
    "species_common_name": "zebra finch",
    "species_scientific_name": "Taeniopygia guttata",
    "taxonomic_family": "Estrildidae",
    "developmental_stage": "juvenile",
    "communication_domain": "vocal",
    "vocalisation_type": ["song", "subsong"],
    "behavioural_context": ["vocal learning"],
    "putative_function": ["mate attraction"],
    "analysis_method": ["spectrogram analysis", "ANOVA"],
    "main_outcome": "Juvenile finches copy tutor songs with high fidelity during the sensitive period.",
    "dataset_or_recording_available": "yes",
    "dataset_name": "OSF_ZF_Test",
    "notes_uncertainty": None,
}


# ---------------------------------------------------------------------------
# Basic validation
# ---------------------------------------------------------------------------

def test_valid_record_passes():
    record, errors = validate_record(VALID_RECORD)
    assert record is not None
    assert errors == []


def test_missing_required_field_fails():
    bad = {k: v for k, v in VALID_RECORD.items() if k != "title"}
    record, errors = validate_record(bad)
    assert record is None
    assert any("title" in e for e in errors)


def test_invalid_enum_fails():
    bad = {**VALID_RECORD, "developmental_stage": "larval"}
    record, errors = validate_record(bad)
    assert record is None


def test_year_out_of_range_fails():
    bad = {**VALID_RECORD, "year": 1850}
    record, errors = validate_record(bad)
    assert record is None


# ---------------------------------------------------------------------------
# dataset_name / availability consistency
# ---------------------------------------------------------------------------

def test_dataset_name_requires_yes():
    """
    Core business rule: if dataset_name is set, availability must be 'yes'.
    'unknown' is no longer acceptable — this was the bug.
    """
    bad_unknown = {**VALID_RECORD, "dataset_name": "Dryad", "dataset_or_recording_available": "unknown"}
    record, errors = validate_record(bad_unknown)
    assert record is None, "Should fail: dataset_name set but availability is 'unknown'"

    bad_no = {**VALID_RECORD, "dataset_name": "Dryad", "dataset_or_recording_available": "no"}
    record, errors = validate_record(bad_no)
    assert record is None, "Should fail: dataset_name set but availability is 'no'"

    good = {**VALID_RECORD, "dataset_name": "Dryad", "dataset_or_recording_available": "yes"}
    record, errors = validate_record(good)
    assert record is not None, "Should pass: dataset_name with availability 'yes'"


def test_no_dataset_name_with_any_availability():
    """No dataset_name → any availability value is fine."""
    for avail in ("yes", "no", "unknown"):
        r = {**VALID_RECORD, "dataset_name": None, "dataset_or_recording_available": avail}
        record, errors = validate_record(r)
        assert record is not None, f"Should pass with no dataset_name and availability={avail}"


# ---------------------------------------------------------------------------
# Soft checks
# ---------------------------------------------------------------------------

def test_soft_checks_empty_fields():
    empty = {
        **VALID_RECORD,
        "vocalisation_type": [],
        "analysis_method": [],
        "dataset_name": None,
        "dataset_or_recording_available": "unknown",
    }
    record, _ = validate_record(empty)
    warnings = soft_checks(record)
    warning_text = " ".join(warnings)
    assert "vocalisation_type" in warning_text
    assert "analysis_method" in warning_text


def test_soft_checks_clean_record():
    record, _ = validate_record(VALID_RECORD)
    warnings = soft_checks(record)
    assert warnings == []


# ---------------------------------------------------------------------------
# Pilot dataset regression test
# ---------------------------------------------------------------------------

def test_pilot_dataset_all_valid():
    """All 10 records in the gold pilot must pass validation."""
    pilot_path = Path("data/annotations/pilot.json")
    if not pilot_path.exists():
        pytest.skip("Pilot dataset not found — skipping regression test.")

    records = json.loads(pilot_path.read_text())
    for raw in records:
        record, errors = validate_record(raw)
        assert record is not None, f"Pilot record {raw.get('paper_id')} failed: {errors}"
