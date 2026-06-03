"""Generates an Elicit-style HTML page for reviewing extracted papers."""
from __future__ import annotations
import json
from pathlib import Path


def write_review_html(species_records: dict, out_path: Path) -> None:
    """species_records: {species_sci: {meta, papers: [extracted_paper, ...]}}
    """
    payload = json.dumps(species_records, ensure_ascii=False)
    html = (HTML_TEMPLATE.replace('__DATA__', payload))
    out_path.write_text(html, encoding='utf-8')


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Paper extraction — Review</title>
<style>
:root{--bg:#0e0f11;--panel:#16181c;--text:#e8eaed;--hint:#9aa0a6;
      --amber:#e8a427;--border:#2a2d33;--ok:#00b894;--no:#ff6b6b;
      --hi:rgba(232,164,39,0.15);--lo:rgba(255,107,107,0.1)}
*{box-sizing:border-box;font-family:-apple-system,"DM Sans",sans-serif}
body{background:var(--bg);color:var(--text);margin:0;line-height:1.5}
.hdr{position:sticky;top:0;background:var(--panel);
     border-bottom:1px solid var(--border);padding:1rem 1.5rem;z-index:50;
     display:flex;gap:1rem;align-items:center;flex-wrap:wrap}
h1{margin:0;font-size:18px;font-weight:500}
.stats{color:var(--hint);font-size:13px}
.btn{background:var(--amber);color:#000;border:none;padding:.5rem 1rem;
     border-radius:6px;cursor:pointer;font-weight:600;font-size:13px}
.btn:hover{filter:brightness(1.1)}
.filt{background:var(--bg);color:var(--text);border:1px solid var(--border);
      padding:.4rem .7rem;border-radius:6px;font-size:13px}
.mini{background:transparent;color:var(--hint);border:1px solid var(--border);
      padding:.2rem .5rem;border-radius:4px;font-size:11px;cursor:pointer}
.mini:hover{color:var(--text);border-color:var(--text)}

.sp-block{margin:1.2rem 1.5rem;background:var(--panel);
          border:1px solid var(--border);border-radius:10px;overflow:hidden}
.sp-head{padding:.8rem 1.2rem;background:rgba(0,0,0,0.2);
         display:flex;gap:1rem;align-items:center;cursor:pointer;
         border-bottom:1px solid var(--border)}
.sp-sci{font-family:'DM Serif Display',serif;font-size:18px;font-style:italic;
        color:var(--amber)}
.sp-common{color:var(--text);font-size:14px}
.sp-meta{color:var(--hint);font-size:12px;margin-left:auto}
.sp-toggle{color:var(--hint);font-size:14px;margin-left:.5rem}

.pap{padding:1rem 1.2rem;border-top:1px solid var(--border);
     display:grid;grid-template-columns:auto 1fr;gap:1rem}
.pap:first-of-type{border-top:none}
.pap.kept{background:rgba(0,184,148,0.05)}
.pap.dropped{opacity:0.45}
.pap-chk{width:22px;height:22px;cursor:pointer;margin-top:4px}
.pap-title{font-size:15px;color:var(--text);margin-bottom:.3rem;
           line-height:1.4;font-weight:500}
.pap-title a{color:var(--text);text-decoration:none}
.pap-title a:hover{color:var(--amber)}
.pap-meta{color:var(--hint);font-size:11px;margin-bottom:.6rem}
.pap-meta .sep{margin:0 .4rem;color:#3a3d44}
.pill{display:inline-block;font-size:10px;padding:1px 6px;border-radius:3px;
      margin-right:.3rem;text-transform:uppercase;letter-spacing:.04em}
.pill.q1{background:var(--amber);color:#000;font-weight:600}
.pill.q2{background:#74b9ff;color:#000}
.pill.q3{background:#636e72;color:#fff}
.pill.oa{background:var(--ok);color:#000;font-weight:600}
.pill.r-high{background:var(--ok);color:#000;font-weight:600}
.pill.r-med{background:#fdcb6e;color:#000}
.pill.r-low{background:var(--no);color:#fff}
.pill.t{background:#2a2d33;color:var(--hint)}
.pill.st{background:#6c5ce7;color:#fff}

.extr{margin-top:.4rem;padding:.7rem .9rem;background:rgba(255,255,255,0.02);
      border-left:2px solid var(--border);border-radius:0 4px 4px 0;
      font-size:13px}
.extr-row{margin-bottom:.5rem;display:grid;grid-template-columns:130px 1fr;
          gap:.6rem}
.extr-row:last-child{margin-bottom:0}
.extr-label{font-size:10px;color:var(--hint);text-transform:uppercase;
            letter-spacing:.05em;padding-top:2px;font-weight:600}
.extr-val{color:#d4d7de}
.extr-val.findings{color:var(--text);font-weight:500}
.conf-bar{height:3px;background:var(--border);border-radius:2px;
          margin-top:4px;overflow:hidden}
.conf-fill{height:100%;background:var(--amber)}
.pap-themes{margin-top:.5rem}
</style></head>
<body>
<div class="hdr">
  <h1>📑 Paper extraction — Review</h1>
  <span class="stats" id="stats"></span>
  <input id="filt-q" class="filt" placeholder="search title/species..." style="width:200px">
  <select id="filt-rel" class="filt">
    <option value="">All relevance</option>
    <option value="high">High only</option>
    <option value="high,medium">High + Medium</option>
  </select>
  <select id="filt-type" class="filt"><option value="">All study types</option></select>
  <button class="mini" onclick="keepAll(true)">Keep all hi+med</button>
  <button class="mini" onclick="keepAll(false)">Drop all</button>
  <button class="btn" onclick="exportSelection()">⬇ Export approved</button>
</div>
<div id="list"></div>
<script>
const DATA = __DATA__;
// Build flat paper index and selection state
const PAPERS = [];
Object.entries(DATA).forEach(([sci, sp]) => {
  (sp.papers || []).forEach((p, idx) => {
    PAPERS.push({...p, _sci: sci, _common: sp.common, _idx: idx,
                 _class: sp.class_, _order: sp.order_, _family: sp.family});
  });
});
let state = {};
PAPERS.forEach((p, i) => {
  state[i] = (p.relevance === 'high' || p.relevance === 'medium')
             && (p.confidence || 0) >= 0.5;
});

const $ = s => document.querySelector(s);
const list = $('#list');

// Populate study type filter
(function(){
  const types = new Set(PAPERS.map(p => p.study_type).filter(Boolean));
  const sel = $('#filt-type');
  [...types].sort().forEach(t => {
    const o = document.createElement('option');
    o.value = t; o.textContent = t; sel.appendChild(o);
  });
})();

function venueQuality(p){
  const v = (p.venue||'').toLowerCase();
  const top = ['nature','science','pnas','current biology','proceedings of the royal',
               'nature communications','plos biology','elife','cell ','annual review'];
  const good = ['animal behaviour','behavioral ecology','animal cognition',
                'journal of experimental biology','biology letters','bioacoustics',
                'frontiers in','plos one','scientific reports','journal of the acoustical'];
  for(const s of top) if(v.includes(s)) return 'q1';
  for(const s of good) if(v.includes(s)) return 'q2';
  return 'q3';
}

function render() {
  const fq = $('#filt-q').value.toLowerCase();
  const fr = $('#filt-rel').value;
  const ft = $('#filt-type').value;
  list.innerHTML = '';
  let kept = 0;

  // Group by species, in insertion order
  const grouped = {};
  PAPERS.forEach((p, i) => {
    if (state[i]) kept++;
    if (fq && !((p.title||'').toLowerCase().includes(fq) ||
                (p._sci||'').toLowerCase().includes(fq) ||
                (p._common||'').toLowerCase().includes(fq))) return;
    if (fr) {
      const allowed = fr.split(',');
      if (!allowed.includes(p.relevance)) return;
    }
    if (ft && p.study_type !== ft) return;
    if (!grouped[p._sci]) grouped[p._sci] = [];
    grouped[p._sci].push([p, i]);
  });

  Object.entries(grouped).forEach(([sci, items]) => {
    const sp = DATA[sci];
    const block = document.createElement('div');
    block.className = 'sp-block';
    const hd = document.createElement('div');
    hd.className = 'sp-head';
    hd.innerHTML = `<span class="sp-sci">${sci}</span>
      <span class="sp-common">${sp.common||''}</span>
      <span class="sp-meta">${sp.class_||''} · ${sp.order_||''} · ${sp.family||''}
        · ${items.length} papers</span>`;
    block.appendChild(hd);

    items.forEach(([p, i]) => {
      const pap = document.createElement('div');
      pap.className = 'pap' + (state[i] ? ' kept' : ' dropped');
      const themes = (p.themes||[]).map(t =>
        `<span class="pill t">${t.replace(/_/g,' ')}</span>`).join(' ');
      const studyType = p.study_type ?
        `<span class="pill st">${p.study_type}</span>` : '';
      const oaPill = p.is_oa ? '<span class="pill oa">OA</span>' : '';
      const qPill = `<span class="pill ${venueQuality(p)}">${venueQuality(p).toUpperCase()}</span>`;
      const relPill = `<span class="pill r-${p.relevance==='high'?'high':p.relevance==='medium'?'med':'low'}">${p.relevance||'?'}</span>`;
      const link = p.doi ? `https://doi.org/${p.doi}` :
                   (p.pmid ? `https://pubmed.ncbi.nlm.nih.gov/${p.pmid}` : '#');
      pap.innerHTML = `
        <input type="checkbox" class="pap-chk" ${state[i]?'checked':''}
               onchange="toggle(${i})">
        <div>
          <div class="pap-title"><a href="${link}" target="_blank">${p.title||'(no title)'}</a></div>
          <div class="pap-meta">
            ${(p.authors||[]).slice(0,3).join(', ')}${(p.authors||[]).length>3?' et al.':''}
            <span class="sep">·</span> ${p.year||''}
            <span class="sep">·</span> <em>${p.venue||''}</em>
            <span class="sep">·</span> ${p.cited_by||0} cites
            ${p.influential ? ` · ${p.influential} influential` : ''}
            <span style="margin-left:.6rem">${qPill} ${oaPill} ${relPill} ${studyType}</span>
          </div>
          <div class="extr">
            ${p.research_question ? `<div class="extr-row"><div class="extr-label">Question</div>
              <div class="extr-val">${p.research_question}</div></div>` : ''}
            ${p.methods_analysis || p.methods_setting || p.methods_sample_size ?
              `<div class="extr-row"><div class="extr-label">Methods</div>
              <div class="extr-val">
                ${p.methods_recording_type||''}
                ${p.methods_setting ? ` · ${p.methods_setting}` : ''}
                ${p.methods_sample_size ? ` · ${p.methods_sample_size}` : ''}
                ${p.methods_analysis ? ` · ${p.methods_analysis}` : ''}
              </div></div>` : ''}
            ${p.key_findings ? `<div class="extr-row"><div class="extr-label">Findings</div>
              <div class="extr-val findings">${p.key_findings}</div></div>` : ''}
            ${p.implications ? `<div class="extr-row"><div class="extr-label">Implications</div>
              <div class="extr-val">${p.implications}</div></div>` : ''}
            ${p.limitations ? `<div class="extr-row"><div class="extr-label">Limitations</div>
              <div class="extr-val">${p.limitations}</div></div>` : ''}
            ${themes ? `<div class="extr-row"><div class="extr-label">Themes</div>
              <div class="extr-val">${themes}</div></div>` : ''}
            <div class="extr-row"><div class="extr-label">Confidence</div>
              <div class="extr-val">${(p.confidence||0).toFixed(2)}
                <div class="conf-bar"><div class="conf-fill"
                     style="width:${(p.confidence||0)*100}%"></div></div></div></div>
          </div>
        </div>
      `;
      block.appendChild(pap);
    });
    list.appendChild(block);
  });

  $('#stats').textContent = `${kept}/${PAPERS.length} kept`;
}

function toggle(i){ state[i] = !state[i]; render(); }

function keepAll(only_high_med){
  Object.keys(state).forEach(k => {
    const p = PAPERS[+k];
    state[k] = only_high_med ? (p.relevance==='high'||p.relevance==='medium') : false;
  });
  render();
}

function exportSelection(){
  // Re-group approved papers by species, preserving full extraction
  const out = {};
  PAPERS.forEach((p, i) => {
    if (!state[i]) return;
    const k = p._sci;
    if (!out[k]) out[k] = {sci:k, common:p._common, class_:p._class,
                           order_:p._order, family:p._family, papers:[]};
    const {_sci,_common,_class,_order,_family,_idx, ...keep} = p;
    out[k].papers.push(keep);
  });
  const payload = {generated:new Date().toISOString(),
                   approved_papers:Object.values(out).reduce((s,sp)=>s+sp.papers.length,0),
                   species:Object.values(out)};
  const blob = new Blob([JSON.stringify(payload,null,2)],{type:'application/json'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'approved_papers.json';
  a.click();
}

$('#filt-q').addEventListener('input', render);
$('#filt-rel').addEventListener('change', render);
$('#filt-type').addEventListener('change', render);
render();
</script>
</body></html>
"""
