"""
tests/test_v2_1_improvements.py
--------------------------------
Tests for the 8 improvements in Zoe.Logos v2.1.

Coverage:
  1. SignalAnnotation model + signal_annotations table
  2. claims_v2 uniqueness with COALESCE (NULL-safe)
  3. method_id in claim_evidence (not claims_v2)
  4. vocab_suggestions review queue
  5. Fail-fast on ambiguous aliases
  6. research_topic_terms table + ResearchTopicTerm model
  7. Prompt does NOT infer function from context
  8. claim_ingest.py end-to-end pipeline
"""

import sqlite3

import pytest

from src.db import get_connection, init_db
from src.models import SignalAnnotation, ResearchTopicTerm
from src.models.schema_evidence import (
    CommunicationClaim, ClaimEvidence, CurationStatus,
    ExtractedClaimItem, PaperExtractionResult,
)
from src.prompts import SYSTEM_PROMPT, build_extraction_prompt
from src.vocab import VocabIndex, load_all_vocabs, get_pending_suggestions
from src.services.claim_ingest import ingest_extraction_result, resolve_species_mention


# ─────────────────────────────────────────────────────────────────────────────
# Shared fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def mem_db():
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    init_db(con)
    load_all_vocabs(con)
    return con


@pytest.fixture
def idx(mem_db):
    return VocabIndex(mem_db)


@pytest.fixture
def mem_db_with_species(mem_db):
    """DB with a single species row for ingest tests."""
    mem_db.execute("""
        INSERT INTO species (species_id, scientific_name, canonical_name, common_name_en)
        VALUES ('gbif:2493440', 'Taeniopygia guttata (Vieillot, 1817)',
                'Taeniopygia guttata', 'zebra finch')
    """)
    mem_db.commit()
    return mem_db


# ─────────────────────────────────────────────────────────────────────────────
# 1. SignalAnnotation model
# ─────────────────────────────────────────────────────────────────────────────

class TestSignalAnnotation:
    def test_valid_annotation(self):
        ann = SignalAnnotation(
            recording_id="xc:XC12345",
            taxon_id="gbif:2493440",
            signal_id="signal:alarm_call",
            start_time_s=2.5,
            end_time_s=3.1,
            low_freq_hz=1500.0,
            high_freq_hz=8000.0,
            annotator="researcher_A",
            confidence=0.92,
        )
        assert ann.duration_s == pytest.approx(0.6, abs=1e-9)
        assert ann.curation_status == "extracted"

    def test_end_before_start_fails(self):
        with pytest.raises(ValueError, match="end_time_s"):
            SignalAnnotation(
                recording_id="xc:XC12345",
                start_time_s=5.0,
                end_time_s=3.0,   # invalid
            )

    def test_zero_duration_fails(self):
        with pytest.raises(ValueError):
            SignalAnnotation(
                recording_id="xc:XC12345",
                start_time_s=3.0,
                end_time_s=3.0,   # equal → not > start
            )

    def test_freq_range_invalid(self):
        with pytest.raises(ValueError, match="high_freq_hz"):
            SignalAnnotation(
                recording_id="xc:XC12345",
                start_time_s=1.0,
                end_time_s=2.0,
                low_freq_hz=8000.0,
                high_freq_hz=2000.0,   # inverted
            )

    def test_confidence_bounds(self):
        with pytest.raises(Exception):
            SignalAnnotation(
                recording_id="xc:XC12345",
                start_time_s=1.0,
                end_time_s=2.0,
                confidence=1.5,
            )

    def test_table_exists(self, mem_db):
        tables = {r[0] for r in mem_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        assert "signal_annotations" in tables

    def test_table_check_constraint_time(self, mem_db):
        """DB CHECK rejects end_time_s <= start_time_s."""
        with pytest.raises(sqlite3.IntegrityError):
            mem_db.execute("""
                INSERT INTO signal_annotations
                    (recording_id, start_time_s, end_time_s)
                VALUES ('xc:1', 5.0, 3.0)
            """)

    def test_table_insert_valid(self, mem_db):
        mem_db.execute("""
            INSERT INTO signal_annotations
                (recording_id, start_time_s, end_time_s, confidence)
            VALUES ('xc:XC99', 0.5, 1.5, 0.85)
        """)
        mem_db.commit()
        row = mem_db.execute("SELECT * FROM signal_annotations WHERE recording_id='xc:XC99'").fetchone()
        assert row is not None
        assert row["confidence"] == 0.85


# ─────────────────────────────────────────────────────────────────────────────
# 2. COALESCE uniqueness on claims_v2
# ─────────────────────────────────────────────────────────────────────────────

class TestClaimsV2Uniqueness:
    def _insert_species(self, con):
        con.execute("""
            INSERT OR IGNORE INTO species (species_id, scientific_name, canonical_name)
            VALUES ('gbif:test1', 'Testus species', 'Testus species')
        """)
        con.commit()

    def test_exact_duplicate_rejected(self, mem_db):
        self._insert_species(mem_db)
        mem_db.execute("""
            INSERT INTO claims_v2 (species_id, signal_id, context_id, function_id)
            VALUES ('gbif:test1', 'signal:alarm_call', 'context:predator_response', 'fn:predator_warning')
        """)
        mem_db.commit()
        with pytest.raises(sqlite3.IntegrityError):
            mem_db.execute("""
                INSERT INTO claims_v2 (species_id, signal_id, context_id, function_id)
                VALUES ('gbif:test1', 'signal:alarm_call', 'context:predator_response', 'fn:predator_warning')
            """)

    def test_null_duplicate_rejected(self, mem_db):
        """Two rows with all-NULL vocab IDs for the same species must be rejected."""
        self._insert_species(mem_db)
        mem_db.execute("""
            INSERT INTO claims_v2 (species_id, signal_id, context_id, function_id)
            VALUES ('gbif:test1', NULL, NULL, NULL)
        """)
        mem_db.commit()
        with pytest.raises(sqlite3.IntegrityError):
            mem_db.execute("""
                INSERT INTO claims_v2 (species_id, signal_id, context_id, function_id)
                VALUES ('gbif:test1', NULL, NULL, NULL)
            """)

    def test_different_signal_allowed(self, mem_db):
        """Different signal_id → different claim → should be accepted."""
        self._insert_species(mem_db)
        mem_db.execute("""
            INSERT INTO claims_v2 (species_id, signal_id, context_id, function_id)
            VALUES ('gbif:test1', 'signal:alarm_call', NULL, NULL)
        """)
        mem_db.execute("""
            INSERT INTO claims_v2 (species_id, signal_id, context_id, function_id)
            VALUES ('gbif:test1', 'signal:contact_call', NULL, NULL)
        """)
        mem_db.commit()
        count = mem_db.execute(
            "SELECT COUNT(*) FROM claims_v2 WHERE species_id='gbif:test1'"
        ).fetchone()[0]
        assert count == 2


# ─────────────────────────────────────────────────────────────────────────────
# 3. method_id in claim_evidence (not claims_v2)
# ─────────────────────────────────────────────────────────────────────────────

class TestMethodInEvidence:
    def test_claim_evidence_has_method_id_column(self, mem_db):
        cols = {r[1] for r in mem_db.execute("PRAGMA table_info(claim_evidence)")}
        assert "method_id" in cols

    def test_claims_v2_has_no_method_id_column(self, mem_db):
        cols = {r[1] for r in mem_db.execute("PRAGMA table_info(claims_v2)")}
        assert "method_id" not in cols

    def test_evidence_check_constraints(self, mem_db):
        """evidence_text length < 5 should fail."""
        mem_db.execute("""
            INSERT OR IGNORE INTO species (species_id, scientific_name, canonical_name)
            VALUES ('gbif:m1', 'Method Test', 'Method Test')
        """)
        mem_db.execute("""
            INSERT INTO claims_v2 (species_id, curation_status)
            VALUES ('gbif:m1', 'extracted')
        """)
        mem_db.commit()
        claim_id = mem_db.execute("SELECT last_insert_rowid()").fetchone()[0]

        with pytest.raises(sqlite3.IntegrityError):
            mem_db.execute("""
                INSERT INTO claim_evidence
                    (claim_id, paper_id, evidence_text, support_level)
                VALUES (?, 'p1', 'Hi', 'explicit')
            """, (claim_id,))   # evidence_text too short (len=2 < 5)

    def test_evidence_requires_paper_or_recording(self, mem_db):
        """paper_id and recording_id both NULL should fail."""
        mem_db.execute("""
            INSERT OR IGNORE INTO species (species_id, scientific_name, canonical_name)
            VALUES ('gbif:m2', 'Method Test2', 'Method Test2')
        """)
        mem_db.execute("""
            INSERT INTO claims_v2 (species_id, curation_status)
            VALUES ('gbif:m2', 'extracted')
        """)
        mem_db.commit()
        claim_id = mem_db.execute("SELECT last_insert_rowid()").fetchone()[0]

        with pytest.raises(sqlite3.IntegrityError):
            mem_db.execute("""
                INSERT INTO claim_evidence
                    (claim_id, paper_id, recording_id, evidence_text, support_level)
                VALUES (?, NULL, NULL, 'Valid evidence text here.', 'explicit')
            """, (claim_id,))

    def test_invalid_support_level_fails(self, mem_db):
        """support_level not in ('explicit','implicit','uncertain') should fail."""
        mem_db.execute("""
            INSERT OR IGNORE INTO species (species_id, scientific_name, canonical_name)
            VALUES ('gbif:m3', 'Method Test3', 'Method Test3')
        """)
        mem_db.execute("""
            INSERT INTO claims_v2 (species_id, curation_status)
            VALUES ('gbif:m3', 'extracted')
        """)
        mem_db.commit()
        claim_id = mem_db.execute("SELECT last_insert_rowid()").fetchone()[0]

        with pytest.raises(sqlite3.IntegrityError):
            mem_db.execute("""
                INSERT INTO claim_evidence
                    (claim_id, paper_id, evidence_text, support_level)
                VALUES (?, 'p1', 'Valid evidence text here.', 'definite')
            """, (claim_id,))  # 'definite' not in allowed values


# ─────────────────────────────────────────────────────────────────────────────
# 4. vocab_suggestions review queue
# ─────────────────────────────────────────────────────────────────────────────

class TestVocabSuggestions:
    def test_table_exists(self, mem_db):
        tables = {r[0] for r in mem_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        assert "vocab_suggestions" in tables

    def test_unknown_signal_queued(self, mem_db, idx):
        """Looking up an unknown label with con= should queue a suggestion."""
        result = idx.signal("completely unknown call type xyz", con=mem_db, source_id="paper_test")
        assert result is None
        pending = get_pending_suggestions(mem_db, vocab_type="signal")
        labels = [r["raw_label"] for r in pending]
        assert "completely unknown call type xyz" in labels

    def test_count_increments(self, mem_db, idx):
        """Looking up the same unknown label twice increments count_seen."""
        for _ in range(3):
            idx.signal("mystery bark", con=mem_db)
        row = mem_db.execute(
            "SELECT count_seen FROM vocab_suggestions WHERE raw_label='mystery bark'"
        ).fetchone()
        assert row["count_seen"] == 3

    def test_known_label_not_queued(self, mem_db, idx):
        """Known labels must NOT appear in vocab_suggestions."""
        idx.signal("alarm call", con=mem_db)
        row = mem_db.execute(
            "SELECT * FROM vocab_suggestions WHERE raw_label='alarm call'"
        ).fetchone()
        assert row is None

    def test_none_not_queued(self, mem_db, idx):
        """None input must not create a suggestion."""
        idx.signal(None, con=mem_db)
        count = mem_db.execute(
            "SELECT COUNT(*) FROM vocab_suggestions"
        ).fetchone()[0]
        assert count == 0

    def test_unique_constraint(self, mem_db):
        """Two inserts of same (vocab_type, raw_label) → upsert, not duplicate rows."""
        from src.vocab import _queue_vocab_suggestion
        _queue_vocab_suggestion(mem_db, "signal", "weird chirp")
        _queue_vocab_suggestion(mem_db, "signal", "weird chirp")
        count = mem_db.execute(
            "SELECT COUNT(*) FROM vocab_suggestions WHERE raw_label='weird chirp'"
        ).fetchone()[0]
        assert count == 1


# ─────────────────────────────────────────────────────────────────────────────
# 5. Fail-fast on ambiguous aliases
# ─────────────────────────────────────────────────────────────────────────────

class TestAmbiguousAlias:
    def test_conflict_raises_on_build(self, mem_db):
        """Inserting two terms with the same alias should raise ValueError on VocabIndex build."""
        mem_db.execute("""
            INSERT INTO signal_terms (signal_id, canonical_label, aliases_json)
            VALUES ('signal:test_a', 'test signal A', '["shared alias"]')
        """)
        mem_db.execute("""
            INSERT INTO signal_terms (signal_id, canonical_label, aliases_json)
            VALUES ('signal:test_b', 'test signal B', '["shared alias"]')
        """)
        mem_db.commit()
        with pytest.raises(ValueError, match="Ambiguous alias"):
            VocabIndex(mem_db)

    def test_clean_yaml_has_no_conflicts(self, mem_db):
        """The loaded YAML vocabs must not produce any alias conflicts."""
        # If VocabIndex builds without raising, the YAML is clean.
        idx = VocabIndex(mem_db)
        assert idx.stats()["signals"] > 0

    def test_distress_call_disambiguation(self, mem_db):
        """'distress call' should map to isolation_call only (removed from alarm_call)."""
        idx = VocabIndex(mem_db)
        result = idx.signal("distress call")
        # Must map to exactly one term — isolation_call
        assert result == "signal:isolation_call", (
            f"Expected 'signal:isolation_call', got {result!r}. "
            "Check that 'distress call' was removed from signal:alarm_call aliases."
        )


# ─────────────────────────────────────────────────────────────────────────────
# 6. Research topic terms
# ─────────────────────────────────────────────────────────────────────────────

class TestResearchTopics:
    def test_table_exists(self, mem_db):
        tables = {r[0] for r in mem_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        assert "research_topic_terms" in tables

    def test_topics_loaded(self, mem_db):
        count = mem_db.execute(
            "SELECT COUNT(*) FROM research_topic_terms"
        ).fetchone()[0]
        assert count >= 10, f"Expected ≥10 topic terms, got {count}"

    def test_topic_lookup(self, mem_db, idx):
        assert idx.topic("vocal learning") == "topic:vocal_learning"
        assert idx.topic("song learning") == "topic:vocal_learning"
        assert idx.topic("individual recognition") == "topic:individual_recognition"
        assert idx.topic("mate choice") == "topic:mate_choice"

    def test_topic_model(self):
        t = ResearchTopicTerm(
            topic_id="topic:vocal_learning",
            canonical_label="vocal learning",
            topic_category="developmental",
        )
        assert t.topic_id == "topic:vocal_learning"
        assert t.topic_category == "developmental"

    def test_claims_v2_has_topic_column(self, mem_db):
        cols = {r[1] for r in mem_db.execute("PRAGMA table_info(claims_v2)")}
        assert "topic_id" in cols

    def test_topic_in_evidence_explorer_view(self, mem_db):
        cur = mem_db.execute("SELECT * FROM evidence_explorer LIMIT 0")
        cols = {d[0] for d in cur.description} if cur.description else set()
        assert "topic_label" in cols, f"topic_label not in view columns: {cols}"


# ─────────────────────────────────────────────────────────────────────────────
# 7. Prompt conservatism — function not inferred from context
# ─────────────────────────────────────────────────────────────────────────────

class TestPromptConservatism:
    def test_function_rule_present_in_system_prompt(self):
        """The system prompt must explicitly forbid inferring function from context."""
        assert "DO NOT infer function from context" in SYSTEM_PROMPT
        assert "null" in SYSTEM_PROMPT

    def test_species_as_written_rule_present(self):
        """The prompt must instruct the LLM to extract species names as-written."""
        assert "as they appear in the abstract" in SYSTEM_PROMPT
        assert "GBIF" in SYSTEM_PROMPT

    def test_evidence_text_required_in_prompt(self):
        assert "evidence_text" in SYSTEM_PROMPT
        assert "REQUIRED" in SYSTEM_PROMPT

    def test_topic_field_in_prompt(self):
        """The v2.1 prompt must include the topic field."""
        assert '"topic"' in SYSTEM_PROMPT

    def test_extraction_prompt_includes_paper_id(self):
        prompt = build_extraction_prompt("p_001", "Test Title", "Test abstract text.")
        assert "p_001" in prompt
        assert "Test Title" in prompt


# ─────────────────────────────────────────────────────────────────────────────
# 8. claim_ingest.py — end-to-end pipeline tests
# ─────────────────────────────────────────────────────────────────────────────

def _make_result(species_sci="Taeniopygia guttata", **claim_kwargs) -> PaperExtractionResult:
    defaults = dict(
        signal="alarm call",
        context="predator response",
        function="predator warning",
        evidence_text="Zebra finches produced alarm calls in response to simulated aerial predators.",
        support_level="explicit",
        confidence=0.88,
    )
    defaults.update(claim_kwargs)
    return PaperExtractionResult(
        paper_id="paper_test_001",
        title="Alarm calls in zebra finches",
        species=[{"scientific_name": species_sci, "common_name": "zebra finch"}],
        claims=[ExtractedClaimItem(**defaults)],
        main_outcome="Alarm calls encode predator category.",
    )


class TestClaimIngest:
    def test_resolve_species_known(self, mem_db_with_species):
        sid = resolve_species_mention(mem_db_with_species, "Taeniopygia guttata")
        assert sid == "gbif:2493440"

    def test_resolve_species_unknown(self, mem_db_with_species):
        sid = resolve_species_mention(mem_db_with_species, "Nonexistus fakebird")
        assert sid is None

    def test_ingest_creates_claim_and_evidence(self, mem_db_with_species):
        """Full pipeline: extraction result → claim + evidence rows in DB."""
        # Insert paper
        mem_db_with_species.execute("""
            INSERT INTO papers (paper_id, title) VALUES ('paper_test_001', 'Test paper')
        """)
        mem_db_with_species.commit()

        idx = VocabIndex(mem_db_with_species)
        result = _make_result()
        stats = ingest_extraction_result(mem_db_with_species, result, idx)

        assert stats.claims_created == 1
        assert stats.evidence_inserted == 1
        assert stats.errors == []

        # Claim row exists
        row = mem_db_with_species.execute(
            "SELECT * FROM claims_v2 WHERE species_id='gbif:2493440'"
        ).fetchone()
        assert row is not None
        assert row["signal_id"] == "signal:alarm_call"
        assert row["context_id"] == "context:predator_response"
        assert row["function_id"] == "fn:predator_warning"

        # Evidence row exists
        ev = mem_db_with_species.execute(
            "SELECT * FROM claim_evidence WHERE claim_id=?", (row["claim_id"],)
        ).fetchone()
        assert ev is not None
        assert "alarm calls" in ev["evidence_text"]

    def test_ingest_deduplicates_claim(self, mem_db_with_species):
        """Ingesting the same extraction twice → 1 claim, 2 evidence rows."""
        mem_db_with_species.execute("""
            INSERT OR IGNORE INTO papers (paper_id, title) VALUES ('paper_test_001', 'Test')
        """)
        mem_db_with_species.commit()

        idx = VocabIndex(mem_db_with_species)
        result = _make_result()
        ingest_extraction_result(mem_db_with_species, result, idx)
        stats2 = ingest_extraction_result(mem_db_with_species, result, idx)

        assert stats2.claims_created == 0
        assert stats2.claims_updated == 1   # claim already existed
        assert stats2.evidence_inserted == 1

        total_evidence = mem_db_with_species.execute(
            "SELECT COUNT(*) FROM claim_evidence"
        ).fetchone()[0]
        assert total_evidence == 2

    def test_ingest_queues_unknown_vocab(self, mem_db_with_species):
        """Unknown signal label → queued in vocab_suggestions."""
        mem_db_with_species.execute("""
            INSERT OR IGNORE INTO papers (paper_id, title) VALUES ('paper_test_002', 'Test2')
        """)
        mem_db_with_species.commit()

        idx = VocabIndex(mem_db_with_species)
        result = PaperExtractionResult(
            paper_id="paper_test_002",
            title="Weird sounds paper",
            species=[{"scientific_name": "Taeniopygia guttata", "common_name": "zebra finch"}],
            claims=[ExtractedClaimItem(
                signal="weird undocumented trill",
                context="predator response",
                function=None,
                evidence_text="The birds produced a weird undocumented trill when threatened.",
                support_level="explicit",
                confidence=0.6,
            )],
        )
        stats = ingest_extraction_result(mem_db_with_species, result, idx)
        assert stats.vocab_queued >= 1

        pending = get_pending_suggestions(mem_db_with_species, vocab_type="signal")
        assert any("weird undocumented trill" in r["raw_label"] for r in pending)

    def test_ingest_evidence_explorer_visible(self, mem_db_with_species):
        """After ingest, the claim must be visible in evidence_explorer view."""
        mem_db_with_species.execute("""
            INSERT OR IGNORE INTO papers (paper_id, title, year, doi)
            VALUES ('paper_test_001', 'Test', 2023, '10.1234/test')
        """)
        mem_db_with_species.commit()

        idx = VocabIndex(mem_db_with_species)
        ingest_extraction_result(mem_db_with_species, _make_result(), idx)

        row = mem_db_with_species.execute(
            "SELECT * FROM evidence_explorer WHERE species_id='gbif:2493440'"
        ).fetchone()
        assert row is not None
        assert row["signal_label"] == "alarm call"
        assert row["context_label"] == "predator response"
        assert row["function_label"] == "predator warning"

    def test_ingest_unresolved_species_skips(self, mem_db):
        """If species cannot be resolved, all claims are skipped (no orphan rows)."""
        idx = VocabIndex(mem_db)
        result = _make_result(species_sci="Unknownus birdus")
        stats = ingest_extraction_result(mem_db, result, idx)
        assert stats.claims_created == 0
        assert stats.species_unresolved == 1
        assert len(stats.errors) > 0

    def test_ingest_missing_evidence_text_skipped(self, mem_db_with_species):
        """Claims without valid evidence_text must be skipped, not inserted."""
        # Pydantic will reject evidence_text="" at model level, so we test
        # that the model correctly enforces this.
        with pytest.raises(Exception):
            ExtractedClaimItem(
                signal="alarm call",
                evidence_text="",   # too short
                support_level="explicit",
                confidence=0.8,
            )
