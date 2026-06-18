"""
src/db.py
---------
SQLite schema and connection helper for Zoe.Logos-Graph.

Tables:
  species              — core identity + taxonomy
  species_metadata     — Wikipedia/Wikidata/iNaturalist enrichment
  papers               — literature records (pilot + Crossref/OpenAlex)
  paper_species        — species↔paper relationship
  communication_claims — provenance-aware claims (vocalisation, context, function, method)
  media_assets         — audio/image/spectrogram assets
  open_literature      — open-access DOI links per species

Quality tiers:
  basic         — taxonomy + image + summary
  enriched      — + audio + DOI links + paper count
  evidence_backed — + curated communication claims with provenance

Usage:
    from src.db import get_connection, init_db
    con = get_connection()
    init_db(con)
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path("data/zoe_logos.db")

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- ── Core species identity ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS species (
    species_id              TEXT PRIMARY KEY,
    gbif_usage_key          INTEGER,
    scientific_name         TEXT NOT NULL,
    canonical_name          TEXT,
    common_name_en          TEXT DEFAULT '',
    common_name_it          TEXT DEFAULT '',
    common_name_es          TEXT DEFAULT '',
    common_name_fr          TEXT DEFAULT '',
    common_name_de          TEXT DEFAULT '',
    class_                  TEXT DEFAULT '',
    order_                  TEXT DEFAULT '',
    family                  TEXT DEFAULT '',
    genus                   TEXT DEFAULT '',
    gbif_match_confidence   INTEGER DEFAULT 0,
    gbif_match_status       TEXT DEFAULT 'UNKNOWN',
    profile_level           TEXT DEFAULT 'basic',
    audio_provider          TEXT DEFAULT 'external_links',
    xeno_canto_query        TEXT DEFAULT '',
    wiki_title              TEXT DEFAULT '',
    created_at              TEXT DEFAULT (datetime('now')),
    updated_at              TEXT DEFAULT (datetime('now'))
);

-- ── Wikipedia / Wikidata / iNaturalist metadata ───────────────────────────────
CREATE TABLE IF NOT EXISTS species_metadata (
    species_id          TEXT PRIMARY KEY REFERENCES species(species_id),
    summary             TEXT DEFAULT '',
    image_url           TEXT DEFAULT '',
    image_url_full      TEXT DEFAULT '',
    image_source        TEXT DEFAULT 'Wikimedia Commons',
    image_license       TEXT DEFAULT '',
    image_attribution   TEXT DEFAULT '',
    wiki_url            TEXT DEFAULT '',
    inat_id             INTEGER,
    inat_iconic_taxon   TEXT DEFAULT '',
    conservation_status TEXT DEFAULT '',
    fetched_at          TEXT
);

-- ── Literature ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS papers (
    paper_id        TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    year            INTEGER,
    doi             TEXT,
    abstract        TEXT DEFAULT '',
    journal         TEXT DEFAULT '',
    open_access     INTEGER DEFAULT 0,
    source          TEXT DEFAULT 'unknown',
    fetched_at      TEXT DEFAULT (datetime('now'))
);

-- ── Species ↔ paper ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS paper_species (
    paper_id            TEXT REFERENCES papers(paper_id),
    species_id          TEXT REFERENCES species(species_id),
    matched_by          TEXT DEFAULT 'seed',
    developmental_stage TEXT DEFAULT 'unknown',
    main_outcome        TEXT DEFAULT '',
    dataset_available   TEXT DEFAULT 'unknown',
    dataset_name        TEXT,
    PRIMARY KEY (paper_id, species_id)
);

-- ── Communication claims (provenance-aware) ───────────────────────────────────
CREATE TABLE IF NOT EXISTS communication_claims (
    claim_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    species_id          TEXT NOT NULL REFERENCES species(species_id),
    paper_id            TEXT REFERENCES papers(paper_id),
    claim_type          TEXT NOT NULL,
    value               TEXT NOT NULL,
    evidence_text       TEXT DEFAULT '',
    confidence          REAL DEFAULT 0.5,
    source              TEXT DEFAULT 'seed',
    extraction_version  TEXT DEFAULT '0.1',
    created_at          TEXT DEFAULT (datetime('now')),
    UNIQUE (species_id, claim_type, value, source)
);

-- ── Media assets ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS media_assets (
    asset_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    species_id      TEXT NOT NULL REFERENCES species(species_id),
    media_type      TEXT NOT NULL,
    provider        TEXT NOT NULL,
    url             TEXT NOT NULL,
    audio_url       TEXT DEFAULT '',
    spectrogram_url TEXT DEFAULT '',
    license         TEXT DEFAULT '',
    attribution     TEXT DEFAULT '',
    xc_id           TEXT DEFAULT '',
    recording_type  TEXT DEFAULT '',
    duration_s      REAL,
    location        TEXT DEFAULT '',
    recorded_by     TEXT DEFAULT '',
    recorded_date   TEXT DEFAULT '',
    fetched_at      TEXT DEFAULT (datetime('now'))
);

-- ── Open-access DOI links ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS open_literature (
    species_id  TEXT NOT NULL REFERENCES species(species_id),
    doi         TEXT NOT NULL,
    url         TEXT NOT NULL,
    title       TEXT DEFAULT '',
    year        INTEGER,
    source      TEXT DEFAULT 'seed',
    PRIMARY KEY (species_id, doi)
);

-- ── Indexes ───────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_species_class ON species(class_);
CREATE INDEX IF NOT EXISTS idx_species_order ON species(order_);
CREATE INDEX IF NOT EXISTS idx_species_family ON species(family);
CREATE INDEX IF NOT EXISTS idx_species_profile ON species(profile_level);
CREATE INDEX IF NOT EXISTS idx_claims_species ON communication_claims(species_id);
CREATE INDEX IF NOT EXISTS idx_claims_type ON communication_claims(claim_type);
CREATE INDEX IF NOT EXISTS idx_media_species ON media_assets(species_id);
CREATE INDEX IF NOT EXISTS idx_media_type ON media_assets(media_type, provider);
CREATE INDEX IF NOT EXISTS idx_paper_species_sp ON paper_species(species_id);
"""

# ── Views (useful for querying) ────────────────────────────────────────────────

VIEWS = """
CREATE VIEW IF NOT EXISTS species_summary AS
SELECT
    s.species_id,
    s.scientific_name,
    s.common_name_en,
    s.class_,
    s.order_,
    s.family,
    s.profile_level,
    m.image_url,
    m.conservation_status,
    COUNT(DISTINCT ps.paper_id)  AS paper_count,
    COUNT(DISTINCT cc.claim_id)  AS claim_count,
    COUNT(DISTINCT ma.asset_id)  AS media_count,
    COUNT(DISTINCT ol.doi)       AS open_doi_count
FROM species s
LEFT JOIN species_metadata   m  ON s.species_id = m.species_id
LEFT JOIN paper_species      ps ON s.species_id = ps.species_id
LEFT JOIN communication_claims cc ON s.species_id = cc.species_id
LEFT JOIN media_assets       ma ON s.species_id = ma.species_id
LEFT JOIN open_literature    ol ON s.species_id = ol.species_id
GROUP BY s.species_id;

CREATE VIEW IF NOT EXISTS vocalisation_counts AS
SELECT
    cc.value AS vocalisation,
    COUNT(DISTINCT cc.species_id) AS species_count,
    COUNT(DISTINCT cc.paper_id)   AS paper_count,
    AVG(cc.confidence)            AS avg_confidence
FROM communication_claims cc
WHERE cc.claim_type = 'vocalisation'
GROUP BY cc.value
ORDER BY species_count DESC;

CREATE VIEW IF NOT EXISTS function_counts AS
SELECT
    cc.value AS function,
    COUNT(DISTINCT cc.species_id) AS species_count,
    COUNT(DISTINCT cc.paper_id)   AS paper_count,
    AVG(cc.confidence)            AS avg_confidence
FROM communication_claims cc
WHERE cc.claim_type = 'function'
GROUP BY cc.value
ORDER BY species_count DESC;
"""


def get_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Open (or create) the SQLite database and return a connection."""
    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con


def init_db(con: sqlite3.Connection) -> None:
    """Create all tables, indexes, and views."""
    con.executescript(SCHEMA)
    con.executescript(VIEWS)
    con.commit()
    print(f"Database initialised at {DEFAULT_DB_PATH}")


def compute_profile_level(con: sqlite3.Connection, species_id: str) -> str:
    """
    Compute the profile level for a species based on available data.

    basic          — taxonomy exists
    enriched       — + image OR audio OR DOIs
    evidence_backed — + at least 1 evidence-backed claim (from paper extraction)
    """
    row = con.execute("""
        SELECT
            m.image_url,
            (SELECT COUNT(*) FROM open_literature WHERE species_id = ?) AS doi_count,
            (SELECT COUNT(*) FROM media_assets    WHERE species_id = ?) AS media_count,
            (SELECT COUNT(*) FROM claim_evidence ce
             JOIN communication_claims cc ON ce.claim_id = cc.claim_id
             WHERE cc.species_id = ?
               AND ce.extraction_method IN ('llm', 'manual', 'curated')
            ) AS extracted_claims
        FROM species s
        LEFT JOIN species_metadata m ON s.species_id = m.species_id
        WHERE s.species_id = ?
    """, (species_id, species_id, species_id, species_id)).fetchone()

    if not row:
        return "basic"

    has_image   = bool(row["image_url"])
    has_dois    = row["doi_count"] > 0
    has_media   = row["media_count"] > 0
    has_evidence = row["extracted_claims"] > 0

    if has_evidence:
        return "evidence_backed"
    if has_image or has_dois or has_media:
        return "enriched"
    return "basic"


def update_all_profile_levels(con: sqlite3.Connection) -> None:
    """Recompute profile_level for all species."""
    ids = [row[0] for row in con.execute("SELECT species_id FROM species")]
    for sid in ids:
        level = compute_profile_level(con, sid)
        con.execute(
            "UPDATE species SET profile_level=?, updated_at=datetime('now') WHERE species_id=?",
            (level, sid)
        )
    con.commit()
    print(f"Updated profile levels for {len(ids)} species.")


if __name__ == "__main__":
    con = get_connection()
    init_db(con)