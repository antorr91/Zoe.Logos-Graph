#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
merge_approved_papers.py
========================
Merge dei 2292 paper enriched (approved_papers.json) nel species_explorer.html.

COSA FA:
1. Legge outputs/species_explorer.html del progetto (preservando l'audio Xeno-Canto fetchato)
2. Estrae EMBEDDED_DB (array JSON di 184 specie)
3. Legge approved_papers.json (~2292 paper su 273 specie)
4. Per ogni specie ESISTENTE: sostituisce il vecchio campo `papers` con i nuovi (schema Elicit-style)
5. Per ogni specie NUOVA (89): aggiunge un record minimo al DB
6. Aggiorna anche il rendering JavaScript della tab "evidence" per mostrare i nuovi campi
7. Scrive species_explorer_NEW.html (NON sovrascrive il file originale)

Lo script è SAFE-BY-DEFAULT: scrive sempre su un file _NEW.html.
Dopo aver verificato il risultato, l'utente può rinominare manualmente.

USAGE:
    cd E:\\zoe-logos-graph
    python merge_approved_papers.py

OUTPUT:
    outputs/species_explorer_NEW.html  (file da verificare prima di sostituire)
    merge_log.txt                      (log del processo)

IMPORTANTE: l'audio Xeno-Canto NON viene toccato perché modifichiamo solo
il campo `papers` di ogni specie esistente; tutti gli altri campi rimangono.
"""

import json
import re
import sys
from pathlib import Path
from datetime import datetime

# ── PATHS ───────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent
HTML_IN  = ROOT / 'outputs' / 'species_explorer.html'
HTML_OUT = ROOT / 'outputs' / 'species_explorer_NEW.html'
PAPERS_JSON = ROOT / 'approved_papers.json'
LOG_FILE = ROOT / 'merge_log.txt'

# Fallback paths se i file non sono dove ce li aspettiamo
FALLBACK_PAPERS_PATHS = [
    ROOT / 'approved_papers.json',
    ROOT / 'data' / 'approved_papers.json',
    ROOT / 'outputs' / 'data' / 'approved_papers.json',
]

# ── CONSTANTS ───────────────────────────────────────────────────────────────
ABSTRACT_MAX_CHARS = 300   # come da scelta dell'utente
RELEVANCE_ORDER = {'high': 0, 'medium': 1, 'low': 2, '': 3, None: 3}

# ── LOG HELPER ──────────────────────────────────────────────────────────────
log_lines = []
def log(msg):
    print(msg)
    log_lines.append(msg)

# ── LOAD APPROVED PAPERS ────────────────────────────────────────────────────
def load_papers():
    """
    Carica approved_papers.json con fallback path.

    Schema atteso (dal fetcher v3 + auto_tag):
    {
      "generated": "...",
      "approved_papers": 2292,
      "species_count": 273,
      "species": [
        {
          "sci": "Amphiprion ocellaris",
          "common": "clownfish",
          "group": "existing" | "new",
          "class_": "Actinopterygii",
          "order_": "...",
          "family": "...",
          "stats": {...},
          "papers": [ {...}, ... ]
        },
        ...
      ]
    }

    Ritorna: dict {sci: {common, class_, order_, family, group, papers}}
    """
    for p in [PAPERS_JSON] + FALLBACK_PAPERS_PATHS:
        if not p.exists():
            continue
        log(f"[OK] Trovato approved_papers.json: {p}")
        try:
            data = json.loads(p.read_text(encoding='utf-8'))
        except Exception as e:
            log(f"[ERROR] Errore parsing {p}: {e}")
            continue

        out = {}
        # Caso 1: schema completo del fetcher v3
        if isinstance(data, dict) and 'species' in data and isinstance(data['species'], list):
            log(f"[OK] Schema riconosciuto: fetcher v3 ({data.get('approved_papers', '?')} paper su {data.get('species_count', '?')} specie)")
            for sp in data['species']:
                sci = sp.get('sci')
                if not sci:
                    continue
                out[sci] = {
                    'common': sp.get('common', ''),
                    'class_': sp.get('class_', ''),
                    'order_': sp.get('order_', ''),
                    'family': sp.get('family', ''),
                    'group': sp.get('group', 'existing'),
                    'papers': sp.get('papers', []),
                }
            return out

        # Caso 2: dict {sci: [papers] | {meta+papers}}
        if isinstance(data, dict):
            for sci, val in data.items():
                if sci in ('generated', 'enriched_with', 'approved_papers', 'species_count'):
                    continue
                if isinstance(val, list):
                    out[sci] = {'papers': val, 'common': '', 'class_': '', 'order_': '', 'family': '', 'group': 'existing'}
                elif isinstance(val, dict) and 'papers' in val:
                    out[sci] = val
            if out:
                return out

        # Caso 3: list piatta di paper
        if isinstance(data, list):
            for rec in data:
                sci = rec.get('species_scientific') or rec.get('target_species') or rec.get('sci')
                if not sci:
                    continue
                if sci not in out:
                    out[sci] = {
                        'common': rec.get('species_common') or '',
                        'class_': rec.get('class') or rec.get('class_') or '',
                        'order_': rec.get('order') or rec.get('order_') or '',
                        'family': rec.get('family') or '',
                        'group': 'existing',
                        'papers': []
                    }
                out[sci]['papers'].append(rec)
            return out

    log(f"[FATAL] approved_papers.json non trovato o formato non riconosciuto. Cercato in:")
    for p in [PAPERS_JSON] + FALLBACK_PAPERS_PATHS:
        log(f"  - {p}")
    sys.exit(1)


# ── EXTRACT EMBEDDED_DB FROM HTML ───────────────────────────────────────────
def extract_db(html):
    """Trova l'array EMBEDDED_DB dentro l'HTML e ritorna (prefix, db_array, suffix)."""
    # Pattern: const EMBEDDED_DB = [...];
    # Usa un parser balanced bracket per gestire JSON annidato
    marker = 'const EMBEDDED_DB = ['
    idx = html.find(marker)
    if idx == -1:
        log("[FATAL] EMBEDDED_DB non trovato nell'HTML")
        sys.exit(1)
    start = idx + len(marker) - 1  # punta a '['
    # Bracket-balanced scan
    depth = 0
    in_str = False
    esc = False
    i = start
    while i < len(html):
        c = html[i]
        if esc:
            esc = False
        elif c == '\\' and in_str:
            esc = True
        elif c == '"' and not esc:
            in_str = not in_str
        elif not in_str:
            if c == '[':
                depth += 1
            elif c == ']':
                depth -= 1
                if depth == 0:
                    end = i + 1  # include ']'
                    # Trova il `;` dopo
                    while end < len(html) and html[end] in ' \t':
                        end += 1
                    if end < len(html) and html[end] == ';':
                        end += 1
                    json_text = html[start:i+1]  # solo [...]
                    prefix = html[:start]
                    suffix = html[i+1:]
                    return prefix, json.loads(json_text), suffix
        i += 1
    log("[FATAL] Impossibile trovare la fine di EMBEDDED_DB")
    sys.exit(1)


# ── BUILD NEW PAPER RECORD ──────────────────────────────────────────────────
def build_new_paper(p):
    """
    Trasforma un paper enriched (schema fetcher v3 + auto_tag) nello schema
    finale per il sito. NESSUNO score visibile (richiesto dall'utente).

    Schema input (dal fetcher):
      title, abstract, authors[], year, doi, pmid,
      venue, venue_issn, venue_type,
      cited_by (int), is_oa (bool),
      themes[], study_type,
      methods_setting, methods_recording_type, methods_sample_size,
      relevance, confidence, target_species
    """
    # Abstract troncato a ABSTRACT_MAX_CHARS (scelta dell'utente: sito leggero)
    abstract = (p.get('abstract') or '').strip()
    if len(abstract) > ABSTRACT_MAX_CHARS:
        # Tronca su uno spazio per non spezzare parole
        cut = abstract[:ABSTRACT_MAX_CHARS].rsplit(' ', 1)[0]
        abstract = cut + '…'

    # DOI -> URL
    doi = p.get('doi') or ''
    url = p.get('url') or (f"https://doi.org/{doi}" if doi else '')

    # Open access
    oa = p.get('is_oa')
    if oa is None:
        oa = p.get('open_access')
    if isinstance(oa, str):
        oa = oa.lower() in ('open', 'open_access', 'true', '1', 'yes')
    open_access = 1 if oa else 0

    # Authors
    authors = p.get('authors') or []
    if isinstance(authors, str):
        authors = [a.strip() for a in authors.split(',') if a.strip()]

    # Journal/venue
    journal = (p.get('journal') or p.get('venue') or '').strip()

    # Citations
    citations = p.get('citations')
    if citations is None:
        citations = p.get('cited_by') or 0

    return {
        'title': (p.get('title') or '').strip(),
        'authors': authors[:8],  # max 8 nomi (rendering mostra primi 3+et al.)
        'year': p.get('year') or '',
        'journal': journal,
        'doi': doi,
        'url': url,
        'open_access': open_access,
        'citations': int(citations) if citations else 0,
        'abstract': abstract,
        'themes': p.get('themes') or [],
        'study_type': p.get('study_type') or '',
        'setting': p.get('setting') or p.get('methods_setting') or '',
        'recording_type': p.get('recording_type') or p.get('methods_recording_type') or '',
        'sample_size': p.get('sample_size') or p.get('methods_sample_size') or '',
        'relevance': p.get('relevance') or '',
    }


# ── SORT KEY (high first, then year desc, then citations desc) ──────────────
def paper_sort_key(p):
    rel = RELEVANCE_ORDER.get(p.get('relevance'), 3)
    year_neg = -(int(p.get('year') or 0))
    cites_neg = -(int(p.get('citations') or 0))
    return (rel, year_neg, cites_neg)


# ── BUILD MINIMAL RECORD FOR NEW SPECIES ────────────────────────────────────
def build_new_species_record(sci, meta, new_papers):
    """Crea un record minimo per una specie nuova (senza voc/ctx/fn/audio)."""
    common = meta.get('common') or ''
    return {
        'sci': sci,
        'en': common.lower() if common else '',
        'it': '',
        'es': '',
        'fr': '',
        'de': '',
        'class_': meta.get('class_') or '',
        'order_': meta.get('order_') or '',
        'family': meta.get('family') or '',
        'wiki': sci.replace(' ', '_'),
        'xc': '',  # Nessun Xeno-Canto fetch automatico per nuove specie
        'voc': [],
        'ctx': [],
        'fn': [],
        'themes': sorted({t for p in new_papers for t in (p.get('themes') or [])}),
        'freq': '',
        'learning': 'unknown',
        'semiotic': 'index',
        'papers': sorted([build_new_paper(p) for p in new_papers], key=paper_sort_key),
    }


# ── PATCH EVIDENCE RENDERER ─────────────────────────────────────────────────
# Sostituisce il blocco JavaScript della tab "evidence" con uno schema esteso.

OLD_EVIDENCE_RENDER = '''  } else if (name === 'evidence') {
    let html = '';
    if (!sp.papers?.length) {
      html += `<div class="nop">No curated papers for <em>${sp.common_name_en}</em>.<br>Run <code>python scripts/08_fetch_pubmed.py --only "${sp.scientific_name}"</code> to add PubMed results.</div>`;
    } else {
      html += `<div style="font-size:12px;color:var(--muted);margin-bottom:1rem">${sp.papers.length} paper${sp.papers.length!==1?'s':''} · curated open-access literature 🔓</div>`;
      html += `<div class="cs"><div>` + sp.papers.map(p => {
        const gs = `https://scholar.google.com/scholar?q=${encodeURIComponent(p.title)}`;
        return `<div class="pc">
          <div class="pt" onclick="window.open('${gs}','_blank')">${p.title}</div>
          <div class="pau">${sp.common_name_en} · animal communication study</div>
          <div class="pm">${p.year||'—'} · stage: ${p.stage||'—'} · ${p.id}</div>
          ${p.outcome?`<div class="po">"${p.outcome}"</div>`:''}
          <div class="pacts">
            <a class="pact" href="${gs}" target="_blank">Google Scholar ↗</a>
            <button class="pact" onclick='showExport(${JSON.stringify(p)},${JSON.stringify(sp.scientific_name)})'>Cite</button>
            <button class="pact" onclick='dlBib(${JSON.stringify(p)},${JSON.stringify(sp.scientific_name)})'>BibTeX ↓</button>
            <button class="pact" onclick='dlRIS(${JSON.stringify(p)},${JSON.stringify(sp.scientific_name)})'>RIS ↓</button>
          </div>
        </div>`;
      }).join('') + `</div></div>`;
    }
    tc.innerHTML = html;
'''

# NUOVO renderer Elicit-style: themes come pill, OA/relevance badge, authors,
# citations, abstract troncato, study_type+setting+sample_size linea info,
# sorted: high relevance first
NEW_EVIDENCE_RENDER = '''  } else if (name === 'evidence') {
    let html = '';
    if (!sp.papers?.length) {
      html += `<div class="nop">No peer-reviewed papers indexed for <em>${sp.common_name_en}</em> yet.</div>`;
    } else {
      // Stats line
      const nOA = sp.papers.filter(p=>p.open_access===1 || p.open_access===true).length;
      const nHigh = sp.papers.filter(p=>p.relevance==='high').length;
      html += `<div style="font-size:12px;color:var(--muted);margin-bottom:1rem">${sp.papers.length} peer-reviewed paper${sp.papers.length!==1?'s':''} · ${nOA} open access 🔓 · ${nHigh} high-relevance</div>`;
      // Sort: high first, then medium, then low; within each, year desc
      const relRank = {high:0, medium:1, low:2};
      const sorted = [...sp.papers].sort((a,b) => {
        const ra = relRank[a.relevance] ?? 3, rb = relRank[b.relevance] ?? 3;
        if (ra !== rb) return ra - rb;
        return (b.year||0) - (a.year||0);
      });
      html += `<div class="cs"><div>` + sorted.map(p => {
        const linkUrl = p.url || (p.doi ? 'https://doi.org/'+p.doi : `https://scholar.google.com/scholar?q=${encodeURIComponent(p.title)}`);
        const gs = `https://scholar.google.com/scholar?q=${encodeURIComponent(p.title)}`;
        // Authors: first 3 + et al
        const auths = (p.authors||[]);
        const authStr = auths.length === 0 ? '' :
                        auths.length <= 3 ? auths.join(', ') :
                        auths.slice(0,3).join(', ') + ' et al.';
        // Badges
        const badges = [];
        if (p.open_access===1 || p.open_access===true) badges.push('<span class="pill" style="background:#e0f2e9;color:#1a6b3a;border-color:#a8d8bc">🔓 OA</span>');
        if (p.relevance==='high') badges.push('<span class="pill" style="background:#fef3c7;color:#92400e;border-color:#fcd34d">★ high</span>');
        else if (p.relevance==='medium') badges.push('<span class="pill" style="background:#e0e7ff;color:#3730a3;border-color:#c7d2fe">medium</span>');
        // Themes as pills
        const themePills = (p.themes||[]).slice(0,5).map(t=>`<span class="pill" style="font-size:10px;background:#f1f5f9;color:#475569">${t.replace(/_/g,' ')}</span>`).join('');
        // Methods line
        const methParts = [];
        if (p.study_type) methParts.push(p.study_type);
        if (p.setting) methParts.push(p.setting);
        if (p.sample_size) methParts.push(p.sample_size);
        const methLine = methParts.length ? `<div style="font-size:11px;color:var(--muted);margin-top:.3rem">${methParts.join(' · ')}</div>` : '';
        // Citations
        const citeStr = p.citations ? ` · ${p.citations} citations` : '';
        return `<div class="pc">
          <div class="pt" onclick="window.open('${linkUrl}','_blank')">${p.title}</div>
          ${authStr ? `<div class="pau">${authStr}</div>` : ''}
          <div class="pm">${p.journal||'—'} · ${p.year||'—'}${citeStr}${p.doi?` · <span style="font-family:monospace;font-size:10px">${p.doi}</span>`:''}</div>
          ${badges.length ? `<div style="margin-top:.4rem">${badges.join(' ')}</div>` : ''}
          ${p.abstract ? `<div class="po" style="font-style:normal;color:#334155;line-height:1.5">${p.abstract}</div>` : ''}
          ${themePills ? `<div style="margin-top:.4rem;display:flex;gap:.3rem;flex-wrap:wrap">${themePills}</div>` : ''}
          ${methLine}
          <div class="pacts">
            <a class="pact" href="${linkUrl}" target="_blank">Read ↗</a>
            <a class="pact" href="${gs}" target="_blank">Google Scholar</a>
            <button class="pact" onclick='showExport(${JSON.stringify(p)},${JSON.stringify(sp.scientific_name)})'>Cite</button>
            <button class="pact" onclick='dlBib(${JSON.stringify(p)},${JSON.stringify(sp.scientific_name)})'>BibTeX ↓</button>
          </div>
        </div>`;
      }).join('') + `</div></div>`;
    }
    tc.innerHTML = html;
'''


def patch_evidence_render(html):
    """Sostituisce il renderer della tab evidence."""
    if OLD_EVIDENCE_RENDER in html:
        html = html.replace(OLD_EVIDENCE_RENDER, NEW_EVIDENCE_RENDER)
        log("[OK] Renderer evidence aggiornato (schema Elicit-style)")
    else:
        log("[WARN] Renderer evidence non trovato — il blocco potrebbe essere già aggiornato o modificato.")
        log("       I dati nuovi saranno comunque inseriti nel DB.")
    return html


# ── MAIN MERGE LOGIC ────────────────────────────────────────────────────────
def main():
    log(f"=== merge_approved_papers.py · {datetime.now().isoformat(timespec='seconds')} ===")

    # 1) Carica HTML
    if not HTML_IN.exists():
        log(f"[FATAL] HTML input non trovato: {HTML_IN}")
        sys.exit(1)
    html = HTML_IN.read_text(encoding='utf-8')
    log(f"[OK] Letto {HTML_IN} ({len(html)} caratteri)")

    # 2) Carica papers
    papers_by_sci = load_papers()
    log(f"[OK] Caricati paper per {len(papers_by_sci)} specie da approved_papers.json")

    # 3) Estrai EMBEDDED_DB
    prefix, db, suffix = extract_db(html)
    log(f"[OK] Estratto EMBEDDED_DB con {len(db)} specie esistenti")

    existing_sci = {sp['sci'] for sp in db}

    # 4) Merge per specie esistenti
    updated_count = 0
    paper_count_before = sum(len(sp.get('papers', [])) for sp in db)
    for sp in db:
        sci = sp['sci']
        if sci in papers_by_sci:
            entry = papers_by_sci[sci]
            new_papers = entry.get('papers') if isinstance(entry, dict) else entry
            if new_papers:
                sp['papers'] = sorted(
                    [build_new_paper(p) for p in new_papers],
                    key=paper_sort_key
                )
                updated_count += 1
    log(f"[OK] Specie aggiornate (paper sostituiti): {updated_count}/{len(db)}")

    # 5) Aggiungi specie nuove
    new_species_count = 0
    new_papers_count = 0
    for sci, entry in papers_by_sci.items():
        if sci in existing_sci:
            continue
        new_papers_list = entry.get('papers') if isinstance(entry, dict) else entry
        meta = entry if isinstance(entry, dict) else {}
        if not new_papers_list:
            continue
        db.append(build_new_species_record(sci, meta, new_papers_list))
        new_species_count += 1
        new_papers_count += len(new_papers_list)
    log(f"[OK] Specie nuove aggiunte: {new_species_count} ({new_papers_count} paper)")

    # 6) Ordina DB per class_ poi sci (mantiene struttura logica esistente)
    db.sort(key=lambda x: (x.get('class_') or 'zzz', x.get('sci') or ''))

    # 7) Statistiche finali
    paper_count_after = sum(len(sp.get('papers', [])) for sp in db)
    log(f"[STATS] Paper totali prima: {paper_count_before} → dopo: {paper_count_after}")
    log(f"[STATS] Specie totali nel DB: {len(db)}")

    # 8) Serializza nuovo DB
    new_db_json = json.dumps(db, ensure_ascii=False, separators=(',', ':'))

    # 9) Patch JavaScript renderer
    html_new = prefix + new_db_json + suffix
    html_new = patch_evidence_render(html_new)

    # 10) Scrivi output
    HTML_OUT.write_text(html_new, encoding='utf-8')
    log(f"[OK] Scritto {HTML_OUT} ({len(html_new)} caratteri, ~{len(html_new)//1024} KB)")

    # 11) Scrivi log
    LOG_FILE.write_text('\n'.join(log_lines), encoding='utf-8')

    print()
    print("=" * 60)
    print("DONE.")
    print(f"  Input:  {HTML_IN}")
    print(f"  Output: {HTML_OUT}")
    print(f"  Log:    {LOG_FILE}")
    print()
    print("Apri species_explorer_NEW.html nel browser per verificare.")
    print("Se tutto OK, rinomina manualmente:")
    print(f"  Windows: ren \"{HTML_OUT.name}\" species_explorer.html")
    print(f"  Linux:   mv {HTML_OUT.name} species_explorer.html")
    print()
    print("NOTA: l'audio Xeno-Canto del file originale è preservato perché")
    print("abbiamo solo modificato il campo `papers` di ogni specie.")
    print("=" * 60)


if __name__ == '__main__':
    main()