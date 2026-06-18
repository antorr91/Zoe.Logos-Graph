"""
scripts/09_extract_claims.py
-----------------------------
Estrae claim strutturati dagli abstract con Claude — adattato allo schema v2.

Schema reale del DB:
  communication_claims: species_id, signal_id, context_id, function_id,
                        research_topic_id, confidence, curation_status
  claim_evidence:       claim_id, paper_id, method_id, evidence_text,
                        support_level, confidence, extraction_method

Il normalizzatore cerca i label estratti da Claude nelle tabelle vocab:
  signal_terms (80) + signal_aliases → signal_id
  context_terms (66) → context_id
  function_terms (78) → function_id

Label non riconosciuti vengono salvati in claim_evidence.evidence_text
per revisione manuale.

Uso:
    python scripts/09_extract_claims.py
    python scripts/09_extract_claims.py --limit 10
    python scripts/09_extract_claims.py --species "Taeniopygia guttata"
    python scripts/09_extract_claims.py --rerun

Richiede: ANTHROPIC_API_KEY
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db_v2 import get_connection

NOW = datetime.utcnow().isoformat()

SYSTEM_PROMPT = """\
You are a scientific knowledge extraction assistant for Zoe.Logos, \
an evidence-backed knowledge graph for animal communication research.

Read the abstract and extract structured communication claims.

RULES:
- Extract ONLY what is explicitly stated in the abstract.
- Do not infer or add external knowledge.
- Species: extract names EXACTLY as written in the abstract.
- Function: ONLY assign if explicitly stated. Never infer from context alone.
- evidence_text: REQUIRED for every claim — the exact source sentence.

Return ONLY valid JSON. No markdown. No commentary.

{
  "species": [
    {"scientific_name": "as written in abstract", "common_name": "as written"}
  ],
  "claims": [
    {
      "signal": "signal type label or null",
      "context": "behavioural context or null",
      "function": "communicative function (only if explicit) or null",
      "method": "analysis method or null",
      "topic": "research topic/cognitive phenomenon or null",
      "life_stage": "embryo|early-life|juvenile|adult|mixed or null",
      "evidence_text": "source sentence from abstract — REQUIRED, min 10 chars",
      "support_level": "explicit|implicit|uncertain",
      "confidence": 0.0
    }
  ],
  "main_outcome": "1-2 sentences summarising the finding",
  "dataset_available": "yes|no|unknown"
}
"""


# ─────────────────────────────────────────────────────────────────────────────
# Vocab normaliser (uses actual DB tables)
# ─────────────────────────────────────────────────────────────────────────────

class VocabNormaliser:
    """
    Normalizza label raw → ID canonici usando le tabelle del DB.

    signal_terms + signal_aliases → signal_id
    context_terms                 → context_id
    function_terms                → function_id
    """
    def __init__(self, con):
        self._signals:   dict[str, str] = {}
        self._contexts:  dict[str, str] = {}
        self._functions: dict[str, str] = {}
        self._build(con)

    def _build(self, con):
        import json as _json

        # Signal terms — canonical_label is the v2 column name
        for r in con.execute(
            "SELECT signal_id, canonical_label, aliases_json FROM signal_terms"
        ):
            key = (r["canonical_label"] or "").strip().lower()
            if key:
                self._signals[key] = r["signal_id"]
            # Also index any JSON-stored aliases
            try:
                for alias in _json.loads(r["aliases_json"] or "[]"):
                    ak = alias.strip().lower()
                    if ak:
                        self._signals.setdefault(ak, r["signal_id"])
            except Exception:
                pass

        # Signal aliases table (separate rows)
        for r in con.execute("SELECT signal_id, alias FROM signal_aliases"):
            ak = (r["alias"] or "").strip().lower()
            if ak:
                self._signals.setdefault(ak, r["signal_id"])

        # Context terms
        for r in con.execute(
            "SELECT context_id, canonical_label, aliases_json FROM context_terms"
        ):
            key = (r["canonical_label"] or "").strip().lower()
            if key:
                self._contexts[key] = r["context_id"]
            try:
                for alias in _json.loads(r["aliases_json"] or "[]"):
                    self._contexts.setdefault(alias.strip().lower(), r["context_id"])
            except Exception:
                pass

        # Function terms
        for r in con.execute(
            "SELECT function_id, canonical_label, aliases_json FROM function_terms"
        ):
            key = (r["canonical_label"] or "").strip().lower()
            if key:
                self._functions[key] = r["function_id"]
            try:
                for alias in _json.loads(r["aliases_json"] or "[]"):
                    self._functions.setdefault(alias.strip().lower(), r["function_id"])
            except Exception:
                pass

    def signal(self, raw: str | None) -> str | None:
        if not raw: return None
        return self._signals.get(raw.strip().lower())

    def context(self, raw: str | None) -> str | None:
        if not raw: return None
        return self._contexts.get(raw.strip().lower())

    def function(self, raw: str | None) -> str | None:
        if not raw: return None
        return self._functions.get(raw.strip().lower())

    def stats(self) -> str:
        return (f"signals={len(set(self._signals.values()))} "
                f"contexts={len(set(self._contexts.values()))} "
                f"functions={len(set(self._functions.values()))}")


# ─────────────────────────────────────────────────────────────────────────────
# Species resolver
# ─────────────────────────────────────────────────────────────────────────────

def resolve_species(con, scientific_name: str, common_name: str = "") -> str | None:
    """Risolve un nome specie → species_id nel DB."""
    if not scientific_name or scientific_name.lower() in ("unknown", ""):
        return None
    name = scientific_name.strip()
    row = con.execute(
        "SELECT species_id FROM species WHERE canonical_name = ? COLLATE NOCASE", (name,)
    ).fetchone()
    if row: return row["species_id"]
    row = con.execute(
        "SELECT species_id FROM species WHERE scientific_name LIKE ?", (f"{name}%",)
    ).fetchone()
    if row: return row["species_id"]
    if common_name:
        row = con.execute(
            "SELECT species_id FROM species WHERE common_name_en = ? COLLATE NOCASE",
            (common_name.strip(),)
        ).fetchone()
        if row: return row["species_id"]
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Claude API
# ─────────────────────────────────────────────────────────────────────────────

def get_client():
    try:
        import anthropic
        return anthropic.Anthropic()
    except ImportError:
        print("ERRORE: pip install anthropic")
        sys.exit(1)


def call_claude(client, paper_id: str, title: str, abstract: str) -> dict | None:
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": (
                f"Paper ID: {paper_id}\nTitle: {title}\n\nAbstract:\n{abstract}\n\n"
                "Return only the JSON object."
            )}],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = "\n".join(
                l for l in raw.splitlines()
                if not l.strip().startswith("```")
            ).strip()
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"  ✗ JSON error: {e}")
        return None
    except Exception as e:
        print(f"  ✗ API error: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# DB persistence
# ─────────────────────────────────────────────────────────────────────────────

def upsert_claim(con, species_id: str, signal_id: str | None,
                 context_id: str | None, function_id: str | None,
                 confidence: float, life_stage: str | None) -> tuple[int, bool]:
    """
    Inserisce o recupera un claim canonico.
    Ritorna (claim_id, creato).
    """
    try:
        cur = con.execute("""
            INSERT INTO communication_claims
                (species_id, signal_id, context_id, function_id,
                 confidence, curation_status, notes)
            VALUES (?, ?, ?, ?, ?, 'extracted', ?)
        """, (species_id, signal_id, context_id, function_id,
              confidence, life_stage or ""))
        return cur.lastrowid, True
    except Exception:
        # Già esiste — recupera l'ID
        row = con.execute("""
            SELECT claim_id FROM communication_claims
            WHERE species_id=?
              AND COALESCE(signal_id,'') = COALESCE(?,'')
              AND COALESCE(context_id,'') = COALESCE(?,'')
              AND COALESCE(function_id,'') = COALESCE(?,'')
        """, (species_id, signal_id, context_id, function_id)).fetchone()
        if row:
            return row["claim_id"], False
        raise


def insert_evidence(con, claim_id: int, paper_id: str, evidence_text: str,
                    support_level: str, confidence: float, method_id: str | None,
                    signal_raw: str, context_raw: str, function_raw: str) -> None:
    """Inserisce una riga in claim_evidence."""
    # Nota extra: salva i label raw per tracciabilità
    notes = ""
    if signal_raw and not method_id:
        notes = f"raw: signal={signal_raw!r} context={context_raw!r} function={function_raw!r}"

    con.execute("""
        INSERT INTO claim_evidence
            (claim_id, paper_id, method_id, evidence_text,
             support_level, confidence, extraction_method, extraction_version)
        VALUES (?, ?, ?, ?, ?, ?, 'llm_abstract', 'v2.1')
    """, (claim_id, paper_id, method_id,
          evidence_text, support_level, confidence))


def update_paper_outcome(con, paper_id: str, species_id: str,
                         main_outcome: str, dataset_available: str) -> None:
    con.execute("""
        UPDATE paper_species
        SET main_outcome=?, dataset_available=?
        WHERE paper_id=? AND species_id=?
    """, (main_outcome or "", dataset_available or "unknown", paper_id, species_id))

    con.execute("""
        UPDATE papers SET source=source||'|extracted', fetched_at=?
        WHERE paper_id=? AND source NOT LIKE '%extracted%'
    """, (NOW, paper_id))


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--species", default=None, help="Solo questa specie.")
    parser.add_argument("--limit",   type=int, default=50)
    parser.add_argument("--rerun",   action="store_true")
    parser.add_argument("--delay",   type=float, default=0.5)
    args = parser.parse_args()

    con    = get_connection()
    client = get_client()
    vocab  = VocabNormaliser(con)

    print(f"\n🔤 Vocabolari: {vocab.stats()}")

    not_extracted = "AND p.source NOT LIKE '%extracted%'" if not args.rerun else ""
    species_filter = "AND s.scientific_name = ?" if args.species else ""
    params = []
    if args.species: params.append(args.species)
    params.append(args.limit)

    rows = con.execute(f"""
        SELECT DISTINCT p.paper_id, p.title, p.abstract, ps.species_id, s.scientific_name
        FROM papers p
        JOIN paper_species ps ON p.paper_id = ps.paper_id
        JOIN species s ON ps.species_id = s.species_id
        WHERE p.abstract != '' AND length(p.abstract) > 100
        {not_extracted} {species_filter}
        ORDER BY s.common_name_en, p.year DESC
        LIMIT ?
    """, params).fetchall()

    if not rows:
        print("\n⚠️  Nessun abstract da processare.")
        print("   Tutti già estratti? Usa --rerun per riestrarre.")
        return

    print(f"\n📄 {len(rows)} abstract da estrarre\n")

    total_claims = 0
    total_evidence = 0
    total_unknown = 0
    errors = 0

    for i, row in enumerate(rows, 1):
        pid   = row["paper_id"]
        title = row["title"]
        abstr = row["abstract"]
        sid   = row["species_id"]
        sci   = row["scientific_name"]

        print(f"[{i:>3}/{len(rows)}] {sci[:28]:28s}  {title[:42]}...")

        raw = call_claude(client, pid, title, abstr)
        if not raw:
            errors += 1
            continue

        claims_raw = raw.get("claims", [])
        n_claims = 0
        n_unknown = 0

        for claim in claims_raw:
            ev = (claim.get("evidence_text") or "").strip()
            if len(ev) < 10:
                continue

            signal_raw   = claim.get("signal") or ""
            context_raw  = claim.get("context") or ""
            function_raw = claim.get("function") or ""

            signal_id   = vocab.signal(signal_raw)
            context_id  = vocab.context(context_raw)
            function_id = vocab.function(function_raw)

            # Conta label non risolti
            if signal_raw and not signal_id:   n_unknown += 1
            if context_raw and not context_id: n_unknown += 1
            if function_raw and not function_id: n_unknown += 1

            conf = float(claim.get("confidence", 0.65))
            support = claim.get("support_level", "uncertain")
            life_stage = claim.get("life_stage")

            try:
                claim_id, created = upsert_claim(
                    con, sid, signal_id, context_id, function_id, conf, life_stage
                )
                insert_evidence(
                    con, claim_id, pid, ev, support, conf,
                    method_id=None,
                    signal_raw=signal_raw,
                    context_raw=context_raw,
                    function_raw=function_raw,
                )
                n_claims += 1
                total_evidence += 1
                if created:
                    total_claims += 1
            except Exception as exc:
                print(f"  ⚠️  DB error: {exc}")

        # Aggiorna paper outcome
        update_paper_outcome(con, pid, sid,
                             raw.get("main_outcome", ""),
                             raw.get("dataset_available", "unknown"))
        con.commit()

        total_unknown += n_unknown
        conf_val = raw.get("confidence") or (
            claims_raw[0].get("confidence") if claims_raw else 0
        )
        status = f"✓  {n_claims} claim"
        if n_unknown:
            status += f"  ⚠️ {n_unknown} label non risolti"
        print(f"         {status}")

        if i < len(rows):
            time.sleep(args.delay)

    # Aggiorna profili specie
    try:
        from src.db import update_all_profile_levels
        update_all_profile_levels(con)
    except Exception:
        pass

    print(f"\n{'═'*55}")
    print(f"  ✅ Estrazione completata")
    print(f"{'═'*55}")
    print(f"  Paper processati:        {len(rows) - errors}/{len(rows)}")
    print(f"  Claim nuovi creati:      {total_claims}")
    print(f"  Evidenze inserite:       {total_evidence}")
    print(f"  Label non risolti:       {total_unknown}")
    if errors:
        print(f"  Errori API:              {errors}")
    print(f"\n→ Passo successivo: python scripts/07_export_web.py")

    # Suggerimento: mostra label non risolti più comuni
    if total_unknown > 0:
        print(f"\n💡 Suggerimento: i label non risolti sono salvati nel campo")
        print(f"   evidence_text per revisione. Aggiungili ai YAML in data/vocab/")
        print(f"   e ricarica i vocabolari.")


if __name__ == "__main__":
    main()