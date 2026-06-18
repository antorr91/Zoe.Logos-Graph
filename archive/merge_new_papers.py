#!/usr/bin/env python3
"""merge_new_papers.py — Zoe.Logos-Graph
Attach fetched papers (new_papers.json) to the species named in their
title/abstract, appending to that species' 'papers' array in the EMBEDDED_DB.
A timestamped backup of the HTML is written first. Stdlib only.
"""
import argparse, json, re, time, shutil

def extract_embedded_db(html):
    i = html.find("EMBEDDED_DB")
    if i < 0:
        raise SystemExit("EMBEDDED_DB not found in HTML.")
    eq = html.find("[", i)
    depth = 0; instr = False; esc = False; end = None
    for j in range(eq, len(html)):
        ch = html[j]
        if instr:
            if esc: esc = False
            elif ch == "\\": esc = True
            elif ch == '"': instr = False
        else:
            if ch == '"': instr = True
            elif ch == "[": depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    end = j; break
    if end is None:
        raise SystemExit("Could not find end of EMBEDDED_DB array.")
    return eq, end, json.loads(html[eq:end + 1])

def norm(s):
    return (s or "").lower()

def main():
    ap = argparse.ArgumentParser(description="Attach fetched papers to species.")
    ap.add_argument("--new", default="new_papers.json")
    ap.add_argument("--html", default="species_explorer.html")
    ap.add_argument("--add-species-themes", action="store_true")
    ap.add_argument("--no-genus-fallback", action="store_true")
    ap.add_argument("--unmatched-out", default="new_papers_unmatched.json")
    args = ap.parse_args()

    try:
        new_papers = json.load(open(args.new, encoding="utf-8"))
    except OSError as e:
        raise SystemExit(f"Cannot read {args.new}: {e}")
    if isinstance(new_papers, dict):
        flat = []
        for v in new_papers.values():
            flat.extend(v)
        new_papers = flat

    html = open(args.html, encoding="utf-8", errors="replace").read()
    start, end, db = extract_embedded_db(html)

    by_sci = {}
    by_genus = {}
    existing_dois_per_sci = {}
    for sp in db:
        sci = sp.get("sci", "").strip()
        if not sci:
            continue
        by_sci[sci.lower()] = sp
        genus = sci.split()[0].lower()
        by_genus.setdefault(genus, []).append(sp)
        dset = {(p.get("doi") or "").lower() for p in sp.get("papers", []) if p.get("doi")}
        existing_dois_per_sci[id(sp)] = dset

    added = 0
    matched_papers = 0
    unmatched = []
    per_species = {}

    for p in new_papers:
        text = norm(p.get("title", "")) + " " + norm(p.get("abstract", ""))
        targets = []
        for sci_l, sp in by_sci.items():
            if sci_l in text:
                targets.append(sp)
        if not targets and not args.no_genus_fallback:
            for genus, sps in by_genus.items():
                if len(sps) == 1 and re.search(r"\b" + re.escape(genus) + r"\b", text):
                    targets.append(sps[0])
        if not targets:
            unmatched.append(p)
            continue

        matched_papers += 1
        doi = (p.get("doi") or "").lower()
        paper_obj = {
            "title": p.get("title", ""),
            "authors": p.get("authors", []),
            "year": p.get("year"),
            "journal": p.get("journal", ""),
            "doi": p.get("doi", ""),
            "url": p.get("url", "") or (("https://doi.org/" + doi) if doi else ""),
            "open_access": 1 if p.get("open_access") else 0,
            "citations": p.get("citations", 0) or 0,
            "abstract": p.get("abstract", ""),
            "themes": p.get("themes", []),
            "study_type": p.get("study_type", "other"),
            "setting": p.get("setting", "unspecified"),
            "recording_type": p.get("recording_type", "unspecified"),
            "sample_size": p.get("sample_size", ""),
        }
        for sp in targets:
            dset = existing_dois_per_sci[id(sp)]
            if doi and doi in dset:
                continue
            sp.setdefault("papers", []).append(dict(paper_obj))
            if doi:
                dset.add(doi)
            if args.add_species_themes:
                th = set(sp.get("themes", []))
                th |= set(paper_obj["themes"])
                sp["themes"] = sorted(th)
            per_species[sp["sci"]] = per_species.get(sp["sci"], 0) + 1
            added += 1

    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup = f"{args.html}.{stamp}.bak"
    shutil.copy2(args.html, backup)

    new_db_text = json.dumps(db, ensure_ascii=False, separators=(",", ":"))
    updated = html[:start] + new_db_text + html[end + 1:]
    open(args.html, "w", encoding="utf-8").write(updated)

    json.dump(unmatched, open(args.unmatched_out, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    print("─" * 52)
    print(f"new papers read     : {len(new_papers)}")
    print(f"matched to species  : {matched_papers}")
    print(f"appends (incl. multi-species) : {added}")
    print(f"unmatched (saved)   : {len(unmatched)} -> {args.unmatched_out}")
    print(f"backup written      : {backup}")
    print("─" * 52)
    if per_species:
        print("top species by papers added:")
        for sci, n in sorted(per_species.items(), key=lambda x: -x[1])[:15]:
            print(f"  {sci:32s} +{n}")
    print("\nDone. Re-generate literature/compare pages from the updated HTML.")

if __name__ == "__main__":
    main()