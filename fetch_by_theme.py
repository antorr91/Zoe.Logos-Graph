#!/usr/bin/env python3
"""
fetch_by_theme.py  —  Zoe.Logos-Graph
=====================================
Fetch ADDITIONAL peer-reviewed papers for one or more research themes from
OpenAlex (and, optionally, Semantic Scholar), filter to genuine peer-reviewed
journal articles, deduplicate against the papers already in the corpus, and
write a clean JSON ready to merge into the site.

Stdlib only — no pip install required (Python 3.8+).

TYPICAL USAGE
-------------
    # boost the thin themes, 60 candidates each, journals only, since 2000
    python fetch_by_theme.py --themes infrasound,deception,turn_taking \
        --per-theme 60 --since 2000 --email you@university.edu \
        --existing species_explorer.html --out new_papers.json

    # all 16 themes
    python fetch_by_theme.py --themes all --per-theme 40 --email you@uni.edu \
        --existing species_explorer.html

OUTPUT
------
  * new_papers.json          - flat list of new paper objects (site schema)
  * new_papers_by_theme.json - same, grouped by theme id
Each paper object matches the fields the site already uses:
  title, authors[], year, journal, doi, url, open_access(0/1),
  citations, abstract (truncated), themes[], study_type, setting,
  recording_type, sample_size
Merging these into species_explorer.html (nesting under species) is a separate
step — see the note printed at the end.
"""

import argparse, json, re, sys, time, urllib.parse, urllib.request
from collections import defaultdict

# ─────────────────────────────────────────────────────────────────────────────
# Theme search definitions. Each theme gets a few focused query strings; every
# query is AND-ed with an animal-communication guard so we stay on topic.
# ─────────────────────────────────────────────────────────────────────────────
GUARD = "animal communication vocalization bioacoustics"

THEME_QUERIES = {
    "vocal_learning": [
        "vocal learning", "vocal production learning", "song learning", "vocal imitation",
        "vocal plasticity", "auditory feedback song", "song development juvenile",
        "vocal convergence", "open-ended vocal learning", "vocal usage learning",
        "learned vocalization", "song tutoring", "sensorimotor song learning", "vocal mimicry learning"],
    "referential": [
        "referential alarm call", "functionally referential signal", "food associated call",
        "referential communication animal", "semantic communication animal", "predator-specific call",
        "object-specific call", "referential signaling", "information content alarm call",
        "external referent vocalization", "meaning animal call"],
    "syntax": [
        "compositional syntax animal", "call combination", "combinatorial communication",
        "syntactic structure animal call", "phonological syntax", "call sequence rules",
        "proto-syntax", "word order animal communication", "hierarchical vocal sequence",
        "rule-governed call combination", "vocal sequence organization", "syntactic complexity birdsong"],
    "individual_recognition": [
        "individual vocal recognition", "signature whistle", "vocal signature",
        "individual distinctiveness call", "vocal individuality", "voice recognition conspecific",
        "individual acoustic identity", "kin recognition vocal", "mother-offspring vocal recognition",
        "name-like call", "individual identity vocalization", "vocal fingerprint", "caller identity acoustic"],
    "cultural_transmission": [
        "cultural transmission song", "vocal tradition", "song cultural evolution",
        "social transmission vocalization", "vocal culture animal", "song meme spread",
        "horizontal transmission song", "song innovation spread", "cumulative culture vocal",
        "song tradition population", "cultural evolution call", "dialect cultural transmission"],
    "turn_taking": [
        "vocal turn-taking", "duetting", "antiphonal calling", "coordinated duet",
        "call-and-response vocal", "temporal coordination calls", "vocal exchange timing",
        "overlap avoidance calling", "alternating calls", "chorus synchronization",
        "conversational turn-taking animal", "duet coordination pair", "vocal alternation"],
    "honest_signalling": [
        "honest signal body size", "formant frequency body size", "acoustic indicator quality",
        "vocal honest signaling", "fundamental frequency body size", "size exaggeration vocalization",
        "condition-dependent call", "index signal acoustic", "vocal quality mate choice",
        "roar body size", "source-filter body size", "call amplitude quality", "honest acoustic cue"],
    "echolocation": [
        "echolocation", "biosonar", "bat echolocation call", "click train sonar",
        "echolocation call design", "active acoustic sensing", "FM echolocation", "CF echolocation",
        "echolocation prey capture", "toothed whale echolocation", "echolocation buzz",
        "sonar pulse animal", "echolocation foraging"],
    "infrasound": [
        "infrasound communication", "infrasonic call", "elephant infrasound rumble",
        "low frequency long distance vocalization", "infrasonic signaling", "seismic communication",
        "long-range low frequency call", "rumble long distance communication",
        "below human hearing communication", "very low frequency vocalization", "infrasound whale"],
    "dialects": [
        "vocal dialect", "song dialect", "geographic song variation", "regional call variation",
        "dialect boundary", "microgeographic variation song", "population vocal divergence",
        "call dialect", "whale song dialect", "bird song dialect", "acoustic geographic variation",
        "dialect formation vocal", "geographic variation vocalization"],
    "emotion": [
        "emotional vocalization", "vocal expression of emotion animal", "affective vocalization",
        "vocal correlates arousal valence", "vocal emotional state animal", "vocal indicators of emotion",
        "emotional contagion vocalization", "stress vocalization", "positive affect vocalization",
        "fear vocalization acoustic", "vocal emotional prosody animal", "affective state vocalization",
        "emotion encoding call", "vocal expression arousal"],
    "multimodal": [
        "multimodal communication", "multimodal signal", "acoustic visual display",
        "cross-modal signaling", "audiovisual communication animal", "multicomponent signal",
        "combined acoustic visual signal", "multimodal courtship display", "visual acoustic integration",
        "multisensory signal animal", "gesture vocalization combined", "multimodal display mate choice"],
    "deception": [
        "deceptive signal animal", "vocal mimicry deception", "false alarm call",
        "tactical deception vocal", "dishonest signal", "aggressive acoustic mimicry",
        "deceptive mimicry", "brood parasite call", "manipulative signal", "acoustic deception",
        "alarm call deception", "kleptoparasitism false alarm"],
    "parent_offspring": [
        "mother offspring vocal recognition", "begging call", "isolation call offspring",
        "parent-offspring communication", "maternal call recognition", "nestling begging vocalization",
        "pup isolation call", "prenatal vocal learning", "offspring solicitation call",
        "chick recognition call", "mother-infant vocal", "contact call mother offspring"],
    "alarm": [
        "alarm call predator", "anti-predator vocalization", "mobbing call", "predator-specific alarm",
        "warning call animal", "alarm call urgency", "referential alarm call", "predator alarm response",
        "snake alarm call", "aerial predator alarm", "graded alarm call", "heterospecific alarm call",
        "alarm calling behaviour"],
    "cooperation": [
        "cooperative recruitment call", "group coordination vocalization", "collective acoustic signal",
        "food recruitment call", "cooperative hunting vocalization", "coordinated group movement call",
        "quorum signal animal", "contact call group cohesion", "recruitment vocalization foraging",
        "cooperative breeding call", "group decision vocal", "consensus call animal", "alliance call"],
}

# Preprint / repository hosts we explicitly reject (defence in depth; we already
# require source.type == 'journal').
PREPRINT_HINTS = ("biorxiv", "arxiv", "preprint", "ssrn", "researchsquare",
                  "authorea", "osf", "zenodo", "figshare", "techrxiv")

OPENALEX = "https://api.openalex.org/works"
SEMSCH   = "https://api.semanticscholar.org/graph/v1/paper/search"


# ─────────────────────────────────────────────────────────────────────────────
# Small HTTP helper
# ─────────────────────────────────────────────────────────────────────────────
def http_json(url, params, headers=None, retries=3, pause=1.0):
    qs = urllib.parse.urlencode(params)
    full = f"{url}?{qs}"
    req = urllib.request.Request(full, headers=headers or {"User-Agent": "ZoeLogosGraph/1.0"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception as e:
            if attempt == retries - 1:
                print(f"   ! request failed ({e})", file=sys.stderr)
                return None
            time.sleep(pause * (attempt + 1))
    return None


# ─────────────────────────────────────────────────────────────────────────────
# OpenAlex helpers
# ─────────────────────────────────────────────────────────────────────────────
def reconstruct_abstract(inv):
    """OpenAlex stores abstracts as an inverted index {word: [positions]}."""
    if not inv:
        return ""
    pos = {}
    for word, idxs in inv.items():
        for i in idxs:
            pos[i] = word
    return " ".join(pos[i] for i in sorted(pos))


def is_peer_reviewed_openalex(w):
    """Keep only genuine peer-reviewed journal articles."""
    if (w.get("type") or "").lower() not in ("article", "journal-article"):
        return False
    loc = w.get("primary_location") or {}
    src = loc.get("source") or {}
    if (src.get("type") or "").lower() != "journal":
        return False
    name = (src.get("display_name") or "").lower()
    host = (src.get("host_organization_name") or "").lower()
    if any(h in name or h in host for h in PREPRINT_HINTS):
        return False
    if not w.get("doi"):
        return False
    # An ISSN is a strong peer-review signal for journals.
    if not (src.get("issn") or src.get("issn_l")):
        return False
    return True


def normalise_openalex(w, theme):
    src = (w.get("primary_location") or {}).get("source") or {}
    doi = (w.get("doi") or "").replace("https://doi.org/", "").lower()
    authors = []
    for a in (w.get("authorships") or [])[:10]:
        nm = (a.get("author") or {}).get("display_name")
        if nm:
            authors.append(nm)
    abstract = reconstruct_abstract(w.get("abstract_inverted_index"))
    return {
        "title":          (w.get("title") or "").strip(),
        "authors":        authors,
        "year":           w.get("publication_year"),
        "journal":        src.get("display_name", "") or "",
        "doi":            doi,
        "url":            ("https://doi.org/" + doi) if doi else (w.get("id") or ""),
        "open_access":    1 if (w.get("open_access") or {}).get("is_oa") else 0,
        "citations":      w.get("cited_by_count", 0) or 0,
        "abstract":       abstract,
        "themes":         [theme],
        "study_type":     "other",
        "setting":        "unspecified",
        "recording_type": "unspecified",
        "sample_size":    "",
    }


def fetch_openalex(theme, queries, per_theme, since, email, pause):
    out, seen = [], set()
    per_query = max(10, per_theme // max(1, len(queries)))
    for q in queries:
        params = {
            "search":   f"{q} {GUARD}",
            "filter":   f"type:article,from_publication_date:{since}-01-01,has_doi:true",
            "per_page": min(per_query, 200),
            "sort":     "relevance_score:desc",
        }
        if email:
            params["mailto"] = email
        data = http_json(OPENALEX, params)
        time.sleep(pause)
        if not data:
            continue
        for w in data.get("results", []):
            if not is_peer_reviewed_openalex(w):
                continue
            rec = normalise_openalex(w, theme)
            key = rec["doi"] or rec["title"].lower()
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(rec)
            if len(out) >= per_theme:
                return out
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Optional Semantic Scholar (fills gaps; no key needed but rate-limited)
# ─────────────────────────────────────────────────────────────────────────────
def fetch_semanticscholar(theme, queries, per_theme, since, pause):
    out, seen = [], set()
    per_query = max(10, per_theme // max(1, len(queries)))
    fields = "title,abstract,year,venue,externalIds,authors,citationCount,isOpenAccess,publicationTypes,publicationVenue"
    for q in queries:
        params = {"query": f"{q} {GUARD}", "limit": min(per_query, 100), "fields": fields}
        data = http_json(SEMSCH, params, pause=2.0)
        time.sleep(max(pause, 2.0))  # SS is strict on rate
        if not data:
            continue
        for p in data.get("data", []) or []:
            yr = p.get("year")
            if yr and yr < since:
                continue
            pv = p.get("publicationVenue") or {}
            if (pv.get("type") or "").lower() not in ("journal", ""):
                continue
            ptypes = [t.lower() for t in (p.get("publicationTypes") or [])]
            if "journalarticle" not in ptypes and ptypes:
                continue
            doi = ((p.get("externalIds") or {}).get("DOI") or "").lower()
            if not doi:
                continue
            key = doi
            if key in seen:
                continue
            seen.add(key)
            out.append({
                "title":          (p.get("title") or "").strip(),
                "authors":        [a.get("name", "") for a in (p.get("authors") or [])][:10],
                "year":           yr,
                "journal":        p.get("venue", "") or pv.get("name", ""),
                "doi":            doi,
                "url":            "https://doi.org/" + doi,
                "open_access":    1 if p.get("isOpenAccess") else 0,
                "citations":      p.get("citationCount", 0) or 0,
                "abstract":       (p.get("abstract") or "").strip(),
                "themes":         [theme],
                "study_type":     "other",
                "setting":        "unspecified",
                "recording_type": "unspecified",
                "sample_size":    "",
            })
            if len(out) >= per_theme:
                return out
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Existing-corpus DOIs (so we only KEEP genuinely new papers)
# ─────────────────────────────────────────────────────────────────────────────
def existing_dois(path):
    if not path:
        return set()
    try:
        html = open(path, encoding="utf-8", errors="replace").read()
    except OSError as e:
        print(f"   ! could not read {path}: {e}", file=sys.stderr)
        return set()
    return {d.lower() for d in re.findall(r'"doi":"([^"]+)"', html)}


# ─────────────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="Theme-targeted peer-reviewed paper fetcher.")
    ap.add_argument("--themes", default="all",
                    help="comma-separated theme ids, or 'all'. "
                         "Choices: " + ", ".join(THEME_QUERIES))
    ap.add_argument("--per-theme", type=int, default=40, help="max papers to keep per theme")
    ap.add_argument("--since", type=int, default=1990, help="earliest publication year")
    ap.add_argument("--email", default="", help="contact email for OpenAlex polite pool (recommended)")
    ap.add_argument("--existing", default="", help="path to species_explorer.html to dedup against")
    ap.add_argument("--source", choices=["openalex", "semanticscholar", "both"], default="openalex")
    ap.add_argument("--abstract-chars", type=int, default=600, help="truncate abstracts to N chars")
    ap.add_argument("--pause", type=float, default=0.4, help="seconds between API calls (politeness)")
    ap.add_argument("--out", default="new_papers.json", help="output JSON path")
    args = ap.parse_args()

    if args.themes.strip().lower() == "all":
        themes = list(THEME_QUERIES)
    else:
        themes = [t.strip() for t in args.themes.split(",") if t.strip()]
        bad = [t for t in themes if t not in THEME_QUERIES]
        if bad:
            ap.error("unknown theme(s): " + ", ".join(bad))

    known = existing_dois(args.existing)
    print(f"Existing DOIs to skip: {len(known)}")
    print(f"Themes: {', '.join(themes)}  |  source: {args.source}  |  since: {args.since}\n")

    grouped = defaultdict(list)
    seen_global = set(known)

    for t in themes:
        qs = THEME_QUERIES[t]
        print(f"→ {t}")
        cands = []
        if args.source in ("openalex", "both"):
            cands += fetch_openalex(t, qs, args.per_theme, args.since, args.email, args.pause)
        if args.source in ("semanticscholar", "both"):
            cands += fetch_semanticscholar(t, qs, args.per_theme, args.since, args.pause)

        kept = 0
        for rec in cands:
            doi = rec["doi"]
            if not doi or doi in seen_global:
                continue
            seen_global.add(doi)
            if args.abstract_chars and len(rec["abstract"]) > args.abstract_chars:
                rec["abstract"] = rec["abstract"][:args.abstract_chars].rstrip() + "…"
            grouped[t].append(rec)
            kept += 1
            if kept >= args.per_theme:
                break
        print(f"   kept {kept} new peer-reviewed papers")

    flat = [p for t in themes for p in grouped[t]]
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(flat, f, ensure_ascii=False, indent=1)
    by_theme_path = args.out.replace(".json", "_by_theme.json")
    with open(by_theme_path, "w", encoding="utf-8") as f:
        json.dump(grouped, f, ensure_ascii=False, indent=1)

    print("\n" + "─" * 48)
    print(f"TOTAL new papers: {len(flat)}")
    for t in themes:
        print(f"  {t:24s} {len(grouped[t])}")
    print("─" * 48)
    print(f"Wrote {args.out} and {by_theme_path}")
    print(
        "\nNext step (merge into the site):\n"
        "  These papers are theme-tagged but not yet attached to species.\n"
        "  Attach each to the species whose scientific name appears in the\n"
        "  title/abstract (or assign manually), append to that species'\n"
        "  'papers' array in species_explorer.html's EMBEDDED_DB, then\n"
        "  re-run the literature generator. Keep a backup of the .html first."
    )


if __name__ == "__main__":
    main()