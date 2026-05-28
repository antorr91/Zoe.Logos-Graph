"""
src/vocab.py
------------
Loader and normaliser for Zoe.Logos controlled vocabularies (v2.1).

v2.1 changes:
  - Fail-fast on ambiguous aliases: duplicate alias → ValueError at load time.
  - vocab_suggestions table: unknown labels queue for curator review.
  - VocabIndex.normalise_all(): normalises all four fields in one call.
  - load_research_topic_terms(): loads topic vocabulary.
  - _add_alias(): shared helper that detects conflicts.

Usage:
    from src.vocab import load_all_vocabs, VocabIndex

    con = get_connection(); init_db(con)
    load_all_vocabs(con)
    idx = VocabIndex(con)
    signal_id = idx.signal("alarm call", con=con)   # None → queued for review
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Optional

import yaml

VOCAB_DIR = Path("data/vocab")


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_yaml(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or []


def _canonicalise(label: str) -> str:
    """Lowercase + strip for alias matching."""
    return label.strip().lower()


def _add_alias(index: dict[str, str], alias: str, term_id: str) -> None:
    """
    Add an alias to the index.

    Raises ValueError if the same alias already maps to a DIFFERENT term.
    Same-term duplicates (same alias appearing twice for the same ID) are silently ignored.
    This is the fail-fast mechanism that catches ambiguous YAML entries at load time.
    """
    key = _canonicalise(alias)
    if key in index and index[key] != term_id:
        raise ValueError(
            f"Ambiguous alias {alias!r}: already maps to {index[key]!r}, "
            f"cannot also map to {term_id!r}. "
            f"Remove this alias from one of the YAML entries."
        )
    index[key] = term_id


# ─────────────────────────────────────────────────────────────────────────────
# Loaders
# ─────────────────────────────────────────────────────────────────────────────

def load_signal_terms(con: sqlite3.Connection, path: Path | None = None) -> int:
    path = path or (VOCAB_DIR / "signal_terms.yaml")
    rows = _load_yaml(path)
    count = 0
    for row in rows:
        con.execute("""
            INSERT INTO signal_terms
                (signal_id, canonical_label, modality, parent_signal_id,
                 definition, scope_note, acoustic_descriptor, aliases_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(signal_id) DO UPDATE SET
                canonical_label     = excluded.canonical_label,
                modality            = excluded.modality,
                parent_signal_id    = excluded.parent_signal_id,
                definition          = excluded.definition,
                scope_note          = excluded.scope_note,
                acoustic_descriptor = excluded.acoustic_descriptor,
                aliases_json        = excluded.aliases_json
        """, (
            row["signal_id"],
            row["canonical_label"],
            row.get("modality", "unknown"),
            row.get("parent_signal_id"),
            row.get("definition", ""),
            row.get("scope_note", ""),
            row.get("acoustic_descriptor", ""),
            json.dumps(row.get("aliases", [])),
        ))
        count += 1
    con.commit()
    return count


def load_context_terms(con: sqlite3.Connection, path: Path | None = None) -> int:
    path = path or (VOCAB_DIR / "context_terms.yaml")
    rows = _load_yaml(path)
    count = 0
    for row in rows:
        con.execute("""
            INSERT INTO context_terms
                (context_id, canonical_label, parent_context_id,
                 definition, scope_note, aliases_json)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(context_id) DO UPDATE SET
                canonical_label   = excluded.canonical_label,
                parent_context_id = excluded.parent_context_id,
                definition        = excluded.definition,
                scope_note        = excluded.scope_note,
                aliases_json      = excluded.aliases_json
        """, (
            row["context_id"],
            row["canonical_label"],
            row.get("parent_context_id"),
            row.get("definition", ""),
            row.get("scope_note", ""),
            json.dumps(row.get("aliases", [])),
        ))
        count += 1
    con.commit()
    return count


def load_function_terms(con: sqlite3.Connection, path: Path | None = None) -> int:
    path = path or (VOCAB_DIR / "function_terms.yaml")
    rows = _load_yaml(path)
    count = 0
    for row in rows:
        con.execute("""
            INSERT INTO function_terms
                (function_id, canonical_label, parent_function_id,
                 definition, scope_note, aliases_json)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(function_id) DO UPDATE SET
                canonical_label    = excluded.canonical_label,
                parent_function_id = excluded.parent_function_id,
                definition         = excluded.definition,
                scope_note         = excluded.scope_note,
                aliases_json       = excluded.aliases_json
        """, (
            row["function_id"],
            row["canonical_label"],
            row.get("parent_function_id"),
            row.get("definition", ""),
            row.get("scope_note", ""),
            json.dumps(row.get("aliases", [])),
        ))
        count += 1
    con.commit()
    return count


def load_method_terms(con: sqlite3.Connection, path: Path | None = None) -> int:
    path = path or (VOCAB_DIR / "method_terms.yaml")
    rows = _load_yaml(path)
    count = 0
    for row in rows:
        con.execute("""
            INSERT INTO method_terms
                (method_id, canonical_label, method_category,
                 definition, aliases_json)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(method_id) DO UPDATE SET
                canonical_label = excluded.canonical_label,
                method_category = excluded.method_category,
                definition      = excluded.definition,
                aliases_json    = excluded.aliases_json
        """, (
            row["method_id"],
            row["canonical_label"],
            row.get("method_category", ""),
            row.get("definition", ""),
            json.dumps(row.get("aliases", [])),
        ))
        count += 1
    con.commit()
    return count


def load_research_topic_terms(con: sqlite3.Connection, path: Path | None = None) -> int:
    path = path or (VOCAB_DIR / "research_topic_terms.yaml")
    if not path.exists():
        return 0
    rows = _load_yaml(path)
    count = 0
    for row in rows:
        con.execute("""
            INSERT INTO research_topic_terms
                (topic_id, canonical_label, topic_category, parent_topic_id,
                 definition, scope_note, aliases_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(topic_id) DO UPDATE SET
                canonical_label = excluded.canonical_label,
                topic_category  = excluded.topic_category,
                parent_topic_id = excluded.parent_topic_id,
                definition      = excluded.definition,
                scope_note      = excluded.scope_note,
                aliases_json    = excluded.aliases_json
        """, (
            row["topic_id"],
            row["canonical_label"],
            row.get("topic_category", ""),
            row.get("parent_topic_id"),
            row.get("definition", ""),
            row.get("scope_note", ""),
            json.dumps(row.get("aliases", [])),
        ))
        count += 1
    con.commit()
    return count


def load_all_vocabs(con: sqlite3.Connection) -> dict[str, int]:
    """Load all vocabulary files. Returns {table: rows_upserted}."""
    return {
        "signal_terms":          load_signal_terms(con),
        "context_terms":         load_context_terms(con),
        "function_terms":        load_function_terms(con),
        "method_terms":          load_method_terms(con),
        "research_topic_terms":  load_research_topic_terms(con),
    }


# ─────────────────────────────────────────────────────────────────────────────
# VocabIndex — in-memory alias lookup with conflict detection
# ─────────────────────────────────────────────────────────────────────────────

class VocabIndex:
    """
    In-memory alias → canonical ID lookup for all vocabularies.

    Build once per process:
        idx = VocabIndex(con)

    Normalise a raw label:
        signal_id = idx.signal("alarm vocalisation")   # → "signal:alarm_call"
        context_id = idx.context("hawk alarm")          # → "context:aerial_predator"

    Unknown labels (no alias match) return None AND optionally queue a
    vocab_suggestion for curator review when a DB connection is passed:
        signal_id = idx.signal("weird call", con=con, source_id="paper_123")

    Build raises ValueError immediately if any alias maps to two different terms.
    This protects against silent normalisation errors.
    """

    def __init__(self, con: sqlite3.Connection) -> None:
        self._signals:   dict[str, str] = {}
        self._contexts:  dict[str, str] = {}
        self._functions: dict[str, str] = {}
        self._methods:   dict[str, str] = {}
        self._topics:    dict[str, str] = {}
        self._build(con)

    def _build(self, con: sqlite3.Connection) -> None:
        for row in con.execute(
            "SELECT signal_id, canonical_label, aliases_json FROM signal_terms"
        ):
            _add_alias(self._signals, row["canonical_label"], row["signal_id"])
            for alias in json.loads(row["aliases_json"] or "[]"):
                _add_alias(self._signals, alias, row["signal_id"])

        for row in con.execute(
            "SELECT context_id, canonical_label, aliases_json FROM context_terms"
        ):
            _add_alias(self._contexts, row["canonical_label"], row["context_id"])
            for alias in json.loads(row["aliases_json"] or "[]"):
                _add_alias(self._contexts, alias, row["context_id"])

        for row in con.execute(
            "SELECT function_id, canonical_label, aliases_json FROM function_terms"
        ):
            _add_alias(self._functions, row["canonical_label"], row["function_id"])
            for alias in json.loads(row["aliases_json"] or "[]"):
                _add_alias(self._functions, alias, row["function_id"])

        for row in con.execute(
            "SELECT method_id, canonical_label, aliases_json FROM method_terms"
        ):
            _add_alias(self._methods, row["canonical_label"], row["method_id"])
            for alias in json.loads(row["aliases_json"] or "[]"):
                _add_alias(self._methods, alias, row["method_id"])

        # topics table may not exist in old DBs
        try:
            for row in con.execute(
                "SELECT topic_id, canonical_label, aliases_json FROM research_topic_terms"
            ):
                _add_alias(self._topics, row["canonical_label"], row["topic_id"])
                for alias in json.loads(row["aliases_json"] or "[]"):
                    _add_alias(self._topics, alias, row["topic_id"])
        except sqlite3.OperationalError:
            pass

    # ── Public lookup methods ─────────────────────────────────────────────────

    def signal(
        self,
        raw: Optional[str],
        con: Optional[sqlite3.Connection] = None,
        source_id: Optional[str] = None,
        example_text: str = "",
    ) -> Optional[str]:
        return self._lookup(
            self._signals, raw, "signal", con, source_id, example_text
        )

    def context(
        self,
        raw: Optional[str],
        con: Optional[sqlite3.Connection] = None,
        source_id: Optional[str] = None,
        example_text: str = "",
    ) -> Optional[str]:
        return self._lookup(
            self._contexts, raw, "context", con, source_id, example_text
        )

    def function(
        self,
        raw: Optional[str],
        con: Optional[sqlite3.Connection] = None,
        source_id: Optional[str] = None,
        example_text: str = "",
    ) -> Optional[str]:
        return self._lookup(
            self._functions, raw, "function", con, source_id, example_text
        )

    def method(
        self,
        raw: Optional[str],
        con: Optional[sqlite3.Connection] = None,
        source_id: Optional[str] = None,
        example_text: str = "",
    ) -> Optional[str]:
        return self._lookup(
            self._methods, raw, "method", con, source_id, example_text
        )

    def topic(
        self,
        raw: Optional[str],
        con: Optional[sqlite3.Connection] = None,
        source_id: Optional[str] = None,
        example_text: str = "",
    ) -> Optional[str]:
        return self._lookup(
            self._topics, raw, "topic", con, source_id, example_text
        )

    def normalise_all(
        self,
        signal: Optional[str] = None,
        context: Optional[str] = None,
        function: Optional[str] = None,
        method: Optional[str] = None,
        topic: Optional[str] = None,
        con: Optional[sqlite3.Connection] = None,
        source_id: Optional[str] = None,
    ) -> dict[str, Optional[str]]:
        """
        Normalise all five vocabulary fields in one call.

        Returns a dict with keys: signal_id, context_id, function_id,
        method_id, topic_id. Unknown labels resolve to None and are
        queued in vocab_suggestions if con is provided.
        """
        return {
            "signal_id":   self.signal(signal,   con=con, source_id=source_id),
            "context_id":  self.context(context,  con=con, source_id=source_id),
            "function_id": self.function(function, con=con, source_id=source_id),
            "method_id":   self.method(method,    con=con, source_id=source_id),
            "topic_id":    self.topic(topic,      con=con, source_id=source_id),
        }

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _lookup(
        self,
        index: dict[str, str],
        raw: Optional[str],
        vocab_type: str,
        con: Optional[sqlite3.Connection],
        source_id: Optional[str],
        example_text: str,
    ) -> Optional[str]:
        if not raw:
            return None
        result = index.get(_canonicalise(raw))
        if result is None and con is not None:
            _queue_vocab_suggestion(
                con, vocab_type, raw, source_id=source_id, example_text=example_text
            )
        return result

    def stats(self) -> dict:
        return {
            "signals":   len(set(self._signals.values())),
            "contexts":  len(set(self._contexts.values())),
            "functions": len(set(self._functions.values())),
            "methods":   len(set(self._methods.values())),
            "topics":    len(set(self._topics.values())),
        }


# ─────────────────────────────────────────────────────────────────────────────
# vocab_suggestions: curator review queue
# ─────────────────────────────────────────────────────────────────────────────

def _queue_vocab_suggestion(
    con: sqlite3.Connection,
    vocab_type: str,
    raw_label: str,
    source_id: Optional[str] = None,
    example_text: str = "",
) -> None:
    """
    Insert or increment a vocab_suggestion row for an unrecognised label.

    Uses INSERT OR IGNORE + UPDATE so each (vocab_type, raw_label) pair
    is accumulated into a single row with count_seen incrementing.
    """
    try:
        con.execute("""
            INSERT INTO vocab_suggestions
                (vocab_type, raw_label, source_table, source_id, example_text)
            VALUES (?, ?, 'claim_evidence', ?, ?)
            ON CONFLICT(vocab_type, raw_label) DO UPDATE SET
                count_seen = count_seen + 1,
                updated_at = datetime('now'),
                source_id  = CASE WHEN source_id = '' THEN excluded.source_id
                                  ELSE source_id END,
                example_text = CASE WHEN example_text = '' THEN excluded.example_text
                                    ELSE example_text END
        """, (vocab_type, raw_label, source_id or "", example_text))
        con.commit()
    except sqlite3.OperationalError:
        # vocab_suggestions table may not exist in very old DBs — fail silently
        pass


def get_pending_suggestions(
    con: sqlite3.Connection,
    vocab_type: Optional[str] = None,
    min_count: int = 1,
) -> list[dict]:
    """
    Return pending vocab suggestions, optionally filtered by vocab_type.

    Results sorted by count_seen DESC so the most common unknowns appear first.
    """
    if vocab_type:
        rows = con.execute("""
            SELECT * FROM vocab_suggestions
            WHERE status = 'pending'
              AND vocab_type = ?
              AND count_seen >= ?
            ORDER BY count_seen DESC
        """, (vocab_type, min_count)).fetchall()
    else:
        rows = con.execute("""
            SELECT * FROM vocab_suggestions
            WHERE status = 'pending'
              AND count_seen >= ?
            ORDER BY count_seen DESC
        """, (min_count,)).fetchall()
    return [dict(r) for r in rows]


def resolve_suggestion(
    con: sqlite3.Connection,
    suggestion_id: int,
    resolved_term_id: str,
    status: str = "resolved",
) -> None:
    """
    Mark a suggestion as resolved and record the target term ID.

    After resolving, the curator should also add the alias to the YAML
    file so it is picked up on the next VocabIndex build.
    """
    con.execute("""
        UPDATE vocab_suggestions
        SET status = ?, suggested_term_id = ?, updated_at = datetime('now')
        WHERE suggestion_id = ?
    """, (status, resolved_term_id, suggestion_id))
    con.commit()


if __name__ == "__main__":
    from src.db import get_connection, init_db

    con = get_connection()
    init_db(con)
    counts = load_all_vocabs(con)
    print("Loaded vocabulary rows:", counts)

    idx = VocabIndex(con)
    print("Index stats:", idx.stats())

    tests = [
        ("signal",   "alarm call",          "signal:alarm_call"),
        ("signal",   "alarm vocalisation",  "signal:alarm_call"),
        ("signal",   "contact note",        "signal:contact_call"),
        ("context",  "hawk alarm",          "context:aerial_predator"),
        ("function", "mate attraction",     "fn:mate_attraction"),
        ("function", "sexual signalling",   "fn:mate_attraction"),
        ("topic",    "vocal learning",      "topic:vocal_learning"),
        ("topic",    "song learning",       "topic:vocal_learning"),
    ]
    for kind, raw, expected in tests:
        result = getattr(idx, kind)(raw)
        status = "✓" if result == expected else f"✗ (got {result})"
        print(f"  {kind}({raw!r}) → {result}  {status}")
