"""
tests/test_models_v2.py
------------------------
Tests for the Zoe.Logos v2 model layer.

Covers:
  - Taxon model instantiation and field validation
  - SignalTerm, ContextTerm, FunctionTerm, MethodTerm models
  - CommunicationClaim + ClaimEvidence constraints
  - PaperExtractionResult structure
  - RecordingAsset model
  - VocabIndex normalisation
  - DB v2 schema (in-memory)
"""

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from src.models import (
    Taxon, TaxonRank, TaxonomicStatus,
    SignalTerm, ContextTerm, FunctionTerm, MethodTerm,
    CommunicationClaim, ClaimEvidence,
    ExtractedClaimItem, PaperExtractionResult,
    CurationStatus, SupportLevel, ExtractionMethod,
    RecordingAsset, RecordingProvider,
)
from src.db import get_connection, init_db
from src.vocab import load_all_vocabs, VocabIndex


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def mem_db():
    """In-memory SQLite DB with v2 schema and vocab loaded."""
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    init_db(con)
    load_all_vocabs(con)
    return con


@pytest.fixture
def vocab_index(mem_db):
    return VocabIndex(mem_db)


# ─────────────────────────────────────────────────────────────────────────────
# Taxon model
# ─────────────────────────────────────────────────────────────────────────────

class TestTaxon:
    def test_minimal_valid(self):
        t = Taxon(
            species_id="gbif:2493440",
            scientific_name="Taeniopygia guttata (Vieillot, 1817)",
            canonical_name="Taeniopygia guttata",
        )
        assert t.species_id == "gbif:2493440"
        assert t.taxon_rank == TaxonRank.unknown.value

    def test_full_taxonomy(self):
        t = Taxon(
            species_id="gbif:2493440",
            scientific_name="Taeniopygia guttata (Vieillot, 1817)",
            canonical_name="Taeniopygia guttata",
            taxon_rank=TaxonRank.species,
            taxonomic_status=TaxonomicStatus.accepted,
            kingdom="Animalia",
            phylum="Chordata",
            class_name="Aves",
            order="Passeriformes",
            family="Estrildidae",
            genus="Taeniopygia",
            common_name_en="zebra finch",
            common_name_it="diamante mandarino",
            gbif_match_confidence=99,
        )
        assert t.family == "Estrildidae"
        assert t.common_name_en == "zebra finch"
        assert t.gbif_match_confidence == 99

    def test_confidence_bounds(self):
        with pytest.raises(Exception):
            Taxon(
                species_id="gbif:1",
                scientific_name="X",
                canonical_name="X",
                gbif_match_confidence=101,  # out of range
            )


# ─────────────────────────────────────────────────────────────────────────────
# Signal / vocab term models
# ─────────────────────────────────────────────────────────────────────────────

class TestSignalTerm:
    def test_basic(self):
        s = SignalTerm(
            signal_id="signal:alarm_call",
            canonical_label="alarm call",
            modality="acoustic",
            aliases=["alarm vocalisation", "alarm vocalization"],
        )
        assert s.signal_id == "signal:alarm_call"
        assert "alarm vocalisation" in s.aliases

    def test_with_parent(self):
        s = SignalTerm(
            signal_id="signal:alarm_call",
            canonical_label="alarm call",
            modality="acoustic",
            parent_signal_id="signal:call",
        )
        assert s.parent_signal_id == "signal:call"


class TestContextTerm:
    def test_basic(self):
        c = ContextTerm(
            context_id="context:predator_response",
            canonical_label="predator response",
            aliases=["anti-predator context", "alarm context"],
        )
        assert c.context_id == "context:predator_response"


class TestFunctionTerm:
    def test_basic(self):
        f = FunctionTerm(
            function_id="fn:mate_attraction",
            canonical_label="mate attraction",
        )
        assert f.function_id == "fn:mate_attraction"


class TestMethodTerm:
    def test_basic(self):
        m = MethodTerm(
            method_id="method:spectrogram_analysis",
            canonical_label="spectrogram analysis",
            method_category="acoustic",
        )
        assert m.method_category == "acoustic"


# ─────────────────────────────────────────────────────────────────────────────
# ClaimEvidence model
# ─────────────────────────────────────────────────────────────────────────────

class TestClaimEvidence:
    def test_valid(self):
        e = ClaimEvidence(
            paper_id="paper_001",
            evidence_text="Males produced directed alarm calls in response to aerial predators.",
            support_level=SupportLevel.explicit,
            confidence=0.85,
        )
        assert e.evidence_text.startswith("Males")
        assert e.confidence == 0.85

    def test_evidence_text_required(self):
        with pytest.raises(Exception):
            ClaimEvidence(evidence_text="")   # too short (min_length=5)

    def test_confidence_bounds(self):
        with pytest.raises(Exception):
            ClaimEvidence(evidence_text="Valid text here.", confidence=1.5)


# ─────────────────────────────────────────────────────────────────────────────
# CommunicationClaim model
# ─────────────────────────────────────────────────────────────────────────────

class TestCommunicationClaim:
    EVIDENCE = ClaimEvidence(
        paper_id="paper_001",
        evidence_text="Females produced contact calls to maintain flock cohesion during foraging.",
        support_level=SupportLevel.explicit,
        confidence=0.88,
    )

    def test_valid_extracted(self):
        claim = CommunicationClaim(
            taxon_id="gbif:2493440",
            signal_id="signal:contact_call",
            context_id="context:group_cohesion",
            function_id="fn:group_cohesion",
            curation_status=CurationStatus.extracted,
            evidence_items=[self.EVIDENCE],
        )
        assert claim.taxon_id == "gbif:2493440"
        assert len(claim.evidence_items) == 1

    def test_extracted_requires_evidence(self):
        with pytest.raises(ValueError, match="must have at least one evidence item"):
            CommunicationClaim(
                taxon_id="gbif:2493440",
                signal_id="signal:song",
                curation_status=CurationStatus.extracted,
                evidence_items=[],   # empty — should fail
            )

    def test_seed_allows_no_evidence(self):
        """Seed claims don't require evidence items."""
        claim = CommunicationClaim(
            taxon_id="gbif:2493440",
            signal_id="signal:song",
            curation_status=CurationStatus.seed,
            evidence_items=[],
        )
        assert claim.curation_status == "seed"

    def test_curated_requires_evidence(self):
        with pytest.raises(ValueError):
            CommunicationClaim(
                taxon_id="gbif:2493440",
                curation_status=CurationStatus.curated,
                evidence_items=[],
            )


# ─────────────────────────────────────────────────────────────────────────────
# PaperExtractionResult
# ─────────────────────────────────────────────────────────────────────────────

class TestPaperExtractionResult:
    def test_valid(self):
        result = PaperExtractionResult(
            paper_id="paper_001",
            title="Alarm calls in vervet monkeys",
            year=2023,
            species=[{"scientific_name": "Chlorocebus pygerythrus", "common_name": "vervet monkey"}],
            claims=[
                ExtractedClaimItem(
                    signal="alarm call",
                    context="predator response",
                    function="predator warning",
                    evidence_text="Vervet monkeys produced distinct alarm calls for aerial predators.",
                    support_level="explicit",
                    confidence=0.9,
                )
            ],
            main_outcome="Distinct alarm call types encode predator category.",
        )
        assert len(result.claims) == 1
        assert result.claims[0].signal == "alarm call"

    def test_empty_claims_valid(self):
        """Papers with no extractable claims are still valid."""
        result = PaperExtractionResult(
            paper_id="paper_002",
            title="Acoustic ecology of the forest",
            notes_uncertainty="No specific communication claims found in abstract.",
        )
        assert result.claims == []


# ─────────────────────────────────────────────────────────────────────────────
# RecordingAsset
# ─────────────────────────────────────────────────────────────────────────────

class TestRecordingAsset:
    def test_xeno_canto(self):
        r = RecordingAsset(
            provider=RecordingProvider.xeno_canto,
            provider_recording_id="XC12345",
            taxon_id="gbif:2493440",
            url="https://www.xeno-canto.org/12345",
            audio_url="https://www.xeno-canto.org/sounds/uploaded/...mp3",
            license="CC-BY-4.0",
            recording_type="song",
            quality_grade="A",
        )
        assert r.provider == "xeno-canto"
        assert r.license == "CC-BY-4.0"

    def test_lat_lon_bounds(self):
        with pytest.raises(Exception):
            RecordingAsset(
                provider="xeno-canto",
                taxon_id="gbif:1",
                url="https://example.com",
                latitude=95.0,   # invalid
            )


# ─────────────────────────────────────────────────────────────────────────────
# DB v2 schema
# ─────────────────────────────────────────────────────────────────────────────

class TestDbV2Schema:
    def test_tables_exist(self, mem_db):
        tables = {r[0] for r in mem_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        assert "signal_terms"   in tables
        assert "context_terms"  in tables
        assert "function_terms" in tables
        assert "method_terms"   in tables
        assert "claims_v2"      in tables
        assert "claim_evidence" in tables

    def test_views_exist(self, mem_db):
        views = {r[0] for r in mem_db.execute(
            "SELECT name FROM sqlite_master WHERE type='view'"
        )}
        assert "evidence_explorer"     in views
        assert "signal_species_counts" in views
        assert "species_summary"       in views

    def test_species_v2_columns(self, mem_db):
        cols = {r[1] for r in mem_db.execute("PRAGMA table_info(species)")}
        assert "kingdom"        in cols
        assert "phylum"         in cols
        assert "parent_taxon_id" in cols

    def test_media_assets_v2_columns(self, mem_db):
        cols = {r[1] for r in mem_db.execute("PRAGMA table_info(media_assets)")}
        assert "latitude"       in cols
        assert "sample_rate_hz" in cols
        assert "rights_holder"  in cols


# ─────────────────────────────────────────────────────────────────────────────
# VocabIndex normalisation
# ─────────────────────────────────────────────────────────────────────────────

class TestVocabIndex:
    def test_vocab_loaded(self, mem_db):
        count = mem_db.execute("SELECT COUNT(*) FROM signal_terms").fetchone()[0]
        assert count > 5, "Expected >5 signal terms loaded from YAML"

    def test_canonical_lookup(self, vocab_index):
        assert vocab_index.signal("alarm call") == "signal:alarm_call"
        assert vocab_index.context("predator response") == "context:predator_response"
        assert vocab_index.function("mate attraction") == "fn:mate_attraction"

    def test_alias_lookup(self, vocab_index):
        assert vocab_index.signal("alarm vocalisation") == "signal:alarm_call"
        assert vocab_index.signal("alarm vocalization") == "signal:alarm_call"
        assert vocab_index.signal("anti-predator call") == "signal:alarm_call"
        assert vocab_index.context("hawk alarm") == "context:aerial_predator"
        assert vocab_index.function("sexual signalling") == "fn:mate_attraction"

    def test_case_insensitive(self, vocab_index):
        assert vocab_index.signal("Alarm Call") == "signal:alarm_call"
        assert vocab_index.signal("ALARM CALL") == "signal:alarm_call"

    def test_unknown_returns_none(self, vocab_index):
        assert vocab_index.signal("nonexistent_signal_xyz") is None
        assert vocab_index.context(None) is None

    def test_stats(self, vocab_index):
        stats = vocab_index.stats()
        assert stats["signals"] > 5
        assert stats["contexts"] > 5
        assert stats["functions"] > 5
        assert stats["methods"] > 5
