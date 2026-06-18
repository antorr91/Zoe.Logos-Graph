"""
src/services/claim_ingest.py
-----------------------------
Pipeline: PaperExtractionResult → normalised DB rows.

This is the operational core of Zoe.Logos. It bridges the LLM extraction
output with the evidence-backed DB schema.

Pipeline steps per claim:
  1. Parse and validate PaperExtractionResult (Pydantic).
  2. Resolve species mentions to taxon_ids (GBIF anchor).
  3. Normalise raw labels → controlled vocabulary IDs via VocabIndex.
  4. Upsert the canonical CommunicationClaim into claims_v2.
  5. Insert the ClaimEvidence row into claim_evidence.
  6. Queue unknown labels into vocab_suggestions for curator review.
  7. Update aggregate_confidence on the claim.
  8. Return ingest statistics.

Usage:
    from src.services.claim_ingest import ingest_extraction_result
    from src.vocab import VocabIndex

    idx = VocabIndex(con)
    stats = ingest_extraction_result(con, result, idx, paper_id="paper_001")
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from typing import Optional

from src.models.schema_evidence import (
    ExtractedClaimItem,
    PaperExtractionResult,
    CurationStatus,
)
from src.vocab import VocabIndex, _queue_vocab_suggestion


# ─────────────────────────────────────────────────────────────────────────────
# Result dataclass
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class IngestStats:
    """Statistics returned by ingest_extraction_result."""
    paper_id:           str
    species_resolved:   int = 0
    species_unresolved: int = 0
    claims_created:     int = 0
    claims_updated:     int = 0
    evidence_inserted:  int = 0
    vocab_queued:       int = 0
    errors:             list[str] = field(default_factory=list)

    @property
    def total_claims(self) -> int:
        return self.claims_created + self.claims_updated

    def summary(self) -> str:
        return (
            f"[{self.paper_id}] "
            f"species={self.species_resolved}/{self.species_resolved + self.species_unresolved} "
            f"claims={self.claims_created}new+{self.claims_updated}upd "
            f"evidence={self.evidence_inserted} "
            f"queued={self.vocab_queued} "
            f"errors={len(self.errors)}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Species resolution
# ─────────────────────────────────────────────────────────────────────────────

def resolve_species_mention(
    con: sqlite3.Connection,
    scientific_name: str,
    common_name: str = "",
) -> Optional[str]:
    """
    Resolve a species mention to a species_id in the DB.

    Tries, in order:
      1. Exact match on canonical_name.
      2. Exact match on scientific_name (includes authorship).
      3. Common name match on common_name_en (English only, for simplicity).

    Returns species_id or None if unresolved.
    """
    if not scientific_name or scientific_name.lower() in ("unknown", ""):
        return None

    name = scientific_name.strip()

    row = con.execute(
        "SELECT species_id FROM species WHERE canonical_name = ? COLLATE NOCASE",
        (name,),
    ).fetchone()
    if row:
        return row["species_id"]

    row = con.execute(
        "SELECT species_id FROM species WHERE scientific_name LIKE ?",
        (f"{name}%",),
    ).fetchone()
    if row:
        return row["species_id"]

    if common_name:
        row = con.execute(
            "SELECT species_id FROM species WHERE common_name_en = ? COLLATE NOCASE",
            (common_name.strip(),),
        ).fetchone()
        if row:
            return row["species_id"]

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Claim upsert
# ─────────────────────────────────────────────────────────────────────────────

def _upsert_claim(
    con: sqlite3.Connection,
    taxon_id: str,
    signal_id: Optional[str],
    context_id: Optional[str],
    function_id: Optional[str],
    topic_id: Optional[str],
    item: ExtractedClaimItem,
    main_outcome: Optional[str],
) -> tuple[int, bool]:
    """
    Insert or retrieve a claims_v2 row.

    Uses the COALESCE-based unique index to detect existing claims.
    Returns (claim_id, was_created).
    """
    # Try insert; unique index will reject duplicates.
    try:
        cur = con.execute("""
            INSERT INTO claims_v2 (
                species_id, signal_id, context_id, function_id, topic_id,
                life_stage, signal_label_raw, context_label_raw, function_label_raw,
                topic_label_raw, main_outcome, curation_status, aggregate_confidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            taxon_id,
            signal_id,
            context_id,
            function_id,
            topic_id,
            item.life_stage or "",
            item.signal or "",
            item.context or "",
            item.function or "",
            "",               # topic_label_raw: not in ExtractedClaimItem yet
            main_outcome or "",
            CurationStatus.extracted.value,
            item.confidence,
        ))
        return cur.lastrowid, True

    except sqlite3.IntegrityError:
        # Claim already exists — retrieve its ID.
        row = con.execute("""
            SELECT claim_id FROM claims_v2
            WHERE species_id = ?
              AND COALESCE(signal_id,   '') = COALESCE(?, '')
              AND COALESCE(context_id,  '') = COALESCE(?, '')
              AND COALESCE(function_id, '') = COALESCE(?, '')
              AND COALESCE(life_stage,  '') = COALESCE(?, '')
        """, (
            taxon_id,
            signal_id,
            context_id,
            function_id,
            item.life_stage or "",
        )).fetchone()
        if row:
            return row["claim_id"], False
        raise  # unexpected


def _insert_evidence(
    con: sqlite3.Connection,
    claim_id: int,
    paper_id: str,
    item: ExtractedClaimItem,
    method_id: Optional[str],
    extraction_version: str = "0.2",
) -> int:
    """Insert a claim_evidence row. Returns evidence_id."""
    cur = con.execute("""
        INSERT INTO claim_evidence (
            claim_id, paper_id, method_id,
            evidence_text, support_level, extraction_method,
            confidence, extraction_version
        ) VALUES (?, ?, ?, ?, ?, 'llm_abstract', ?, ?)
    """, (
        claim_id,
        paper_id,
        method_id,
        item.evidence_text,
        item.support_level,
        item.confidence,
        extraction_version,
    ))
    return cur.lastrowid


def _update_aggregate_confidence(con: sqlite3.Connection, claim_id: int) -> None:
    """Recompute aggregate_confidence as the average of all evidence items."""
    row = con.execute(
        "SELECT AVG(confidence) AS avg_conf FROM claim_evidence WHERE claim_id = ?",
        (claim_id,),
    ).fetchone()
    if row and row["avg_conf"] is not None:
        con.execute(
            "UPDATE claims_v2 SET aggregate_confidence=?, updated_at=datetime('now') WHERE claim_id=?",
            (round(row["avg_conf"], 4), claim_id),
        )


# ─────────────────────────────────────────────────────────────────────────────
# Main ingest function
# ─────────────────────────────────────────────────────────────────────────────

def ingest_extraction_result(
    con: sqlite3.Connection,
    result: PaperExtractionResult,
    vocab: VocabIndex,
    paper_id: Optional[str] = None,
    extraction_version: str = "0.2",
) -> IngestStats:
    """
    Persist a PaperExtractionResult into the claims_v2 / claim_evidence tables.

    Steps:
      1. Resolve species mentions → taxon_ids.
      2. For each claim × each resolved taxon:
         a. Normalise raw labels via VocabIndex.
         b. Queue unknown labels in vocab_suggestions.
         c. Upsert canonical claim in claims_v2.
         d. Insert evidence row in claim_evidence.
         e. Update aggregate_confidence.
      3. Return IngestStats.

    con must already have init_db() applied and vocabs loaded.
    """
    pid = paper_id or result.paper_id
    stats = IngestStats(paper_id=pid)

    # ── 1. Resolve species ────────────────────────────────────────────────────
    taxon_ids: list[str] = []
    for mention in result.species:
        sci = mention.get("scientific_name", "")
        common = mention.get("common_name", "")
        taxon_id = resolve_species_mention(con, sci, common)
        if taxon_id:
            taxon_ids.append(taxon_id)
            stats.species_resolved += 1
        else:
            stats.species_unresolved += 1

    if not taxon_ids:
        stats.errors.append("No species resolved — skipping all claims.")
        return stats

    # ── 2. Process each claim × each taxon ───────────────────────────────────
    for item in result.claims:
        if not item.evidence_text or len(item.evidence_text.strip()) < 5:
            stats.errors.append(
                f"Skipped claim (missing evidence_text): signal={item.signal!r}"
            )
            continue

        # Normalise raw labels → controlled IDs
        normed = vocab.normalise_all(
            signal=item.signal,
            context=item.context,
            function=item.function,
            method=item.method,
            con=con,
            source_id=pid,
        )
        signal_id   = normed["signal_id"]
        context_id  = normed["context_id"]
        function_id = normed["function_id"]
        method_id   = normed["method_id"]

        # Count how many raw labels went unresolved → queued
        for key, raw in [
            ("signal", item.signal),
            ("context", item.context),
            ("function", item.function),
            ("method", item.method),
        ]:
            if raw and normed.get(f"{key}_id") is None:
                stats.vocab_queued += 1

        for taxon_id in taxon_ids:
            try:
                claim_id, created = _upsert_claim(
                    con, taxon_id, signal_id, context_id, function_id,
                    topic_id=None,   # not extracted yet at claim-item level
                    item=item,
                    main_outcome=result.main_outcome,
                )
                if created:
                    stats.claims_created += 1
                else:
                    stats.claims_updated += 1

                _insert_evidence(
                    con, claim_id, pid, item, method_id, extraction_version
                )
                stats.evidence_inserted += 1

                _update_aggregate_confidence(con, claim_id)

            except sqlite3.IntegrityError as exc:
                stats.errors.append(
                    f"IntegrityError for taxon={taxon_id} signal={item.signal!r}: {exc}"
                )

    con.commit()
    return stats


# ─────────────────────────────────────────────────────────────────────────────
# Batch ingest
# ─────────────────────────────────────────────────────────────────────────────

def ingest_batch(
    con: sqlite3.Connection,
    results: list[PaperExtractionResult],
    vocab: VocabIndex,
    extraction_version: str = "0.2",
    verbose: bool = True,
) -> list[IngestStats]:
    """
    Ingest a list of PaperExtractionResult objects in sequence.

    Returns one IngestStats per paper. Errors in one paper do not
    stop processing of subsequent papers.
    """
    all_stats = []
    for result in results:
        stats = ingest_extraction_result(
            con, result, vocab, extraction_version=extraction_version
        )
        all_stats.append(stats)
        if verbose:
            print(stats.summary())
    return all_stats
