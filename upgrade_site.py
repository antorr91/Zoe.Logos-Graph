#!/usr/bin/env python3
"""
upgrade_site.py - Zoe.Logos-Graph

One-off: brings the pages in outputs/ to version 1.1. Only page code changes,
the data inside the pages stay as they are. Safe to run twice (what is already
there is skipped). Run from the PROJECT ROOT, then build_site.py, then you can
delete this file.

  - all pages:        taxonomy and data in the menu, v1.1
  - home:             text and pipeline as the atlas works now, cards for the new pages
  - species explorer: class / order / family link to the taxonomy, related species,
                      Methods filter in the papers, spectrograms in the recordings,
                      species_explorer.html#parus_major opens a species
  - graph explorer:   group species by order or family, or link species studied together
  - compare:          suggests species of the same family

  python upgrade_site.py
  python build_site.py

The visit counter (GoatCounter, code zoelogo) is added to every page.
"""
import re
import atlas
from pathlib import Path

OUT = Path(__file__).parent / 'outputs'
done, skipped = [], []


def patch(page, marker, pairs):
    path = OUT / page
    h = path.read_text(encoding='utf-8')
    if marker in h:
        skipped.append('%s (%s)' % (page, marker[:30]))
        return
    for old, new in pairs:
        if h.count(old) != 1:
            raise SystemExit('%s: cannot find the place to change:\n  %s' % (page, old[:90]))
        h = h.replace(old, new)
    path.write_text(h, encoding='utf-8')
    done.append('%s (%s)' % (page, marker[:30]))


def menu(page):
    """taxonomy after species, data after compare"""
    path = OUT / page
    h = path.read_text(encoding='utf-8')
    if 'href="taxonomy.html"' in h:
        return
    h = re.sub(r'(\n(\s*)<a href="literature\.html")', r'\n\2<a href="taxonomy.html">taxonomy</a>\1', h, count=1)
    h = re.sub(r'(<a href="compare\.html"[^>]*>compare</a>)', r'\1\n    <a href="data.html">data</a>', h, count=1)
    h = h.replace('<span class="logo-sub">v1.0</span>', '<span class="logo-sub">v1.1</span>')
    path.write_text(h, encoding='utf-8')
    done.append(page + ' (menu)')


METHODS_JS = (r"const METHODS_RX = /deep learning|machine learning|neural network|convolutional|\bCNNs?\b|classifier|random forest|"
              r"support vector|automat\w* (?:detection|classification|recogni\w*|identification|annotation)|"
              r"passive acoustic monitoring|\bMFCCs?\b|signal processing|acoustic indices|unsupervised|"
              r"clustering algorithm|BirdNET|hidden markov|dynamic time warping|feature extraction|"
              r"sound event detection|transfer learning|annotated dataset|public dataset|open dataset|"
              r"spectro-?temporal modulation|self-supervised|embedding/i;")


SPECTROGRAM = [
(""".sono{width:100%;border-radius:8px;margin-bottom:10px;display:block;border:1px solid var(--border)}""",
""".sono{width:100%;border-radius:8px;margin-bottom:10px;display:block;border:1px solid var(--border)}
.specwrap{position:relative;height:160px;margin-bottom:10px;cursor:pointer;border-radius:8px;border:1px solid var(--border);background:#07161a;overflow:hidden}
.spec-scroll{position:absolute;inset:0;overflow:hidden}
.spec-scroll canvas{display:block;height:160px}
.spec-head{position:absolute;top:0;bottom:0;left:0;width:2px;background:#f2c14e;box-shadow:0 0 6px rgba(242,193,78,.6);pointer-events:none}
.spec-f{position:absolute;left:6px;top:4px;bottom:16px;display:flex;flex-direction:column;justify-content:space-between;font:10px 'DM Mono',monospace;color:rgba(255,255,255,.85);text-shadow:0 0 3px #000;pointer-events:none}
.spec-note{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:11px;color:var(--hint);pointer-events:none}
.specwrap img.sono{width:100%;height:100%;margin:0;border:0;border-radius:0;object-fit:fill;filter:invert(.92) hue-rotate(180deg)}"""),

("""          ${r.sono?`<img class="sono" src="${r.sono}" alt="spectrogram" onerror="this.style.display='none'">`:''}""",
"""          ${r.audio?`<div class="specwrap"${isXC&&r.sono?` data-sono="${r.sono.replace(/grey-(small|medium)\\.png$/,'grey-large.png')}"`:''}><div class="spec-scroll"><canvas class="spec" data-src="${r.audio}"></canvas></div><div class="spec-f"></div><div class="spec-head"></div><div class="spec-note">loading spectrogram…</div></div>`:
            r.sono?`<img class="sono" src="${r.sono}" alt="spectrogram" onerror="this.style.display='none'">`:''}"""),

("""  html += `</div>`;
  tc.innerHTML = html;
}

// ── EXPORT""", """  html += `</div>`;
  tc.innerHTML = html;
  initSpectrograms(tc);
}

// ── SPECTROGRAMS ───────────────────────────────────────────────────────
// The spectrogram is drawn here from the audio file (first 60 s), zoomed on the
// frequencies that carry sound, and scrolls under the yellow line while the
// recording plays; click on it to play from that point. Archives that do not let
// a web page read their files keep the player only (Xeno-Canto shows its own image).
const PX_PER_SEC = 80, MAX_SECS = 60, HEAD_AT = 0.25, SPEC_H = 160;
const SPEC_COLORS = [[7,22,26],[20,60,80],[40,120,130],[90,180,140],[240,200,90],[255,250,220]];

function specColor(v) {
  v = Math.max(0, Math.min(1, v)) * (SPEC_COLORS.length - 1);
  const i = Math.min(SPEC_COLORS.length - 2, Math.floor(v)), f = v - i, a = SPEC_COLORS[i], b = SPEC_COLORS[i + 1];
  return [0, 1, 2].map(j => Math.round(a[j] + (b[j] - a[j]) * f));
}

function initSpectrograms(root) {
  const io = new IntersectionObserver(es => es.forEach(e => {
    if (e.isIntersecting) { io.unobserve(e.target); drawSpectrogram(e.target); }
  }), {rootMargin: '200px'});
  root.querySelectorAll('canvas.spec').forEach(c => io.observe(c));
  root.querySelectorAll('.ac').forEach(card => {
    const a = card.querySelector('audio'), w = card.querySelector('.specwrap');
    if (!a || !w) return;
    const place = () => {
      const secs = +w.dataset.secs, head = w.querySelector('.spec-head'), sc = w.querySelector('.spec-scroll');
      if (!secs || !head) return;
      const t = Math.min(a.currentTime, secs);
      if (sc && w.classList.contains('ready')) {
        const px = +w.dataset.pxps;
        sc.scrollLeft = Math.max(0, t * px - sc.clientWidth * HEAD_AT);
        head.style.left = (t * px - sc.scrollLeft) + 'px';
      } else head.style.left = (t / secs * 100) + '%';
      head.style.opacity = a.currentTime > secs ? 0 : 1;
    };
    const loop = () => { place(); if (!a.paused) requestAnimationFrame(loop); };
    a.addEventListener('play', loop);
    a.addEventListener('seeked', place);
    w.addEventListener('click', ev => {
      const secs = +w.dataset.secs, sc = w.querySelector('.spec-scroll');
      if (!secs) return;
      const r = w.getBoundingClientRect(), x = ev.clientX - r.left;
      a.currentTime = (sc && w.classList.contains('ready')) ? (sc.scrollLeft + x) / +w.dataset.pxps : x / r.width * secs;
      a.play();
    });
  });
}

function fft(re, im) {
  const n = re.length;
  for (let i = 1, j = 0; i < n; i++) {
    let bit = n >> 1;
    for (; j & bit; bit >>= 1) j ^= bit;
    j ^= bit;
    if (i < j) { [re[i], re[j]] = [re[j], re[i]]; [im[i], im[j]] = [im[j], im[i]]; }
  }
  for (let len = 2; len <= n; len <<= 1) {
    const ang = -2 * Math.PI / len, wr = Math.cos(ang), wi = Math.sin(ang);
    for (let i = 0; i < n; i += len) {
      let cr = 1, ci = 0;
      for (let k = 0; k < len / 2; k++) {
        const a = i + k, b = a + len / 2;
        const tr = re[b] * cr - im[b] * ci, ti = re[b] * ci + im[b] * cr;
        re[b] = re[a] - tr; im[b] = im[a] - ti; re[a] += tr; im[a] += ti;
        const t = cr * wr - ci * wi; ci = cr * wi + ci * wr; cr = t;
      }
    }
  }
}

async function drawSpectrogram(c) {
  const w = c.closest('.specwrap'), note = w.querySelector('.spec-note');
  try {
    const res = await fetch(c.dataset.src);
    if (!res.ok) throw new Error(res.status);
    const ac = new OfflineAudioContext(1, 1, 96000);
    const audio = await ac.decodeAudioData(await res.arrayBuffer());
    const sr = audio.sampleRate, secs = Math.min(audio.duration, MAX_SECS);
    const x = audio.getChannelData(0).subarray(0, Math.floor(secs * sr));
    const px = Math.max(PX_PER_SEC, w.clientWidth / secs), N = 1024, H = SPEC_H;
    const W = Math.max(1, Math.round(secs * px)), hop = Math.max(1, (x.length - N) / W);
    const win = new Float32Array(N);
    for (let i = 0; i < N; i++) win[i] = 0.5 - 0.5 * Math.cos(2 * Math.PI * i / (N - 1));
    const cols = [], mean = new Float32Array(N / 2);
    let top = -Infinity;
    for (let col = 0; col < W; col++) {
      const s = Math.floor(col * hop), re = new Float32Array(N), im = new Float32Array(N);
      for (let i = 0; i < N; i++) re[i] = (x[s + i] || 0) * win[i];
      fft(re, im);
      const db = new Float32Array(N / 2);
      for (let k = 0; k < N / 2; k++) {
        db[k] = 10 * Math.log10(re[k] * re[k] + im[k] * im[k] + 1e-12);
        mean[k] += db[k] / W;
        if (db[k] > top) top = db[k];
      }
      cols.push(db);
    }
    // only the frequency band that carries sound, with a margin (at least 1 kHz)
    const peak = Math.max(...mean);
    let lo = 0, hi = N / 2 - 1;
    while (hi > 0 && mean[hi] < peak - 30) hi--;
    while (lo < hi && mean[lo] < peak - 30) lo++;
    const minSpan = 1000 / (sr / 2) * (N / 2), pad = Math.max(minSpan / 2, (hi - lo) * 0.2);
    lo = Math.max(0, Math.round(lo - pad)); hi = Math.min(N / 2 - 1, Math.round(hi + pad));
    c.width = W; c.height = H; c.style.width = W + 'px';
    const ctx = c.getContext('2d'), img = ctx.createImageData(W, H), range = 70;
    for (let col = 0; col < W; col++) {
      const db = cols[col];
      for (let y = 0; y < H; y++) {
        const k = Math.round(hi - y / (H - 1) * (hi - lo));
        const [r, g, b] = specColor((db[k] - (top - range)) / range);
        const o = (y * W + col) * 4;
        img.data[o] = r; img.data[o + 1] = g; img.data[o + 2] = b; img.data[o + 3] = 255;
      }
    }
    ctx.putImageData(img, 0, 0);
    ctx.font = '10px sans-serif'; ctx.fillStyle = 'rgba(255,255,255,.65)';
    for (let t = 1; t < secs; t++) {                    // a tick every second, a label every 5
      ctx.fillRect(Math.round(t * px), H - (t % 5 ? 4 : 8), 1, t % 5 ? 4 : 8);
      if (t % 5 === 0) ctx.fillText(t + ' s', Math.round(t * px) + 3, H - 3);
    }
    const kHz = k => { const f = k / (N / 2) * sr / 2 / 1000; return f.toFixed(f < 10 ? 1 : 0) + ' kHz'; };
    w.querySelector('.spec-f').innerHTML = `<span>${kHz(hi)}</span><span>${kHz(lo)}</span>`;
    w.dataset.secs = secs; w.dataset.pxps = px;
    w.classList.add('ready');
    note.remove();
  } catch (e) {
    if (w.dataset.sono) {        // the archive keeps its file to itself: Xeno-Canto's own image (first 10 s)
      w.innerHTML = `<img class="sono" src="${w.dataset.sono}" alt="spectrogram, first 10 s" onerror="this.parentElement.style.display='none'"><div class="spec-head"></div>`;
      w.dataset.secs = 10;
    } else w.style.display = 'none';
  }
}

// ── EXPORT"""),
]


def first_spectrogram_out(h):
    """pages upgraded with the first spectrogram (fixed image of the first 30 s):
    take it out, so that the scrolling one goes in the same places"""
    if 'function drawSpectrogram' not in h or 'PX_PER_SEC' in h:
        return h
    i, j = h.index('\n// ── SPECTROGRAMS'), h.index('\n// ── EXPORT')
    h = h[:i] + h[j:]
    h = h.replace('  initSpectrograms(tc);\n', '', 1)
    h = re.sub(r'(\.sono\{[^\n]*\})\n\.specwrap\{.*?\n\.spec-note\{[^\n]*\}', r'\1', h, count=1, flags=re.S)
    h = re.sub(r'          \$\{r\.sono.*?(?=\n          \$\{r\.audio\?`<audio)',
               lambda m: """          ${r.sono?`<img class="sono" src="${r.sono}" alt="spectrogram" onerror="this.style.display='none'">`:''}""",
               h, count=1, flags=re.S)
    return h


def species_page():
    page = 'species_explorer.html'
    path = OUT / page
    h = path.read_text(encoding='utf-8')
    if first_spectrogram_out(h) != h:
        path.write_text(first_spectrogram_out(h), encoding='utf-8')
    # spectrograms that scroll with the recording (Xeno-Canto's own image when the file cannot be read)
    patch(page, 'PX_PER_SEC', SPECTROGRAM)
    css = (".audio-mark{margin-left:6px;",
           "a.bdg{text-decoration:none}a.bdg:hover{filter:brightness(1.25)}\n"
           ".rels{display:flex;flex-wrap:wrap;gap:6px;margin-top:.4rem}\n"
           ".rel{font-family:'DM Sans',sans-serif;font-size:12px;padding:4px 11px;border-radius:99px;border:1px solid var(--border2);"
           "background:none;color:var(--text);cursor:pointer;text-decoration:none}\n"
           ".rel:hover{border-color:rgba(72,168,154,.5);color:var(--amber)}.rel span{color:var(--hint);font-size:11px}\n"
           ".ev-chips{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:1rem}\n"
           ".ev-chip{font-family:'DM Sans',sans-serif;font-size:11px;padding:4px 12px;border-radius:99px;border:1px solid var(--border);"
           "background:none;color:var(--muted);cursor:pointer}\n"
           ".ev-chip.on{color:var(--amber);border-color:rgba(72,168,154,.5);background:rgba(72,168,154,.12)}\n"
           ".audio-mark{margin-left:6px;")
    patch(page, 'function relatedHTML', [
        css,
        ("""          <span class="bdg bn">${tax.class_||'—'}</span>
          <span class="bdg bt">${tax.order_||'—'}</span>
          <span class="bdg bv">${tax.family||'—'}</span>""",
         """          <a class="bdg bn" href="taxonomy.html#${encodeURIComponent(tax.class_||'')}" title="see in the taxonomy">${tax.class_||'—'}</a>
          <a class="bdg bt" href="taxonomy.html#${encodeURIComponent(tax.order_||'')}" title="see in the taxonomy">${tax.order_||'—'}</a>
          <a class="bdg bv" href="taxonomy.html#${encodeURIComponent(tax.family||'')}" title="see in the taxonomy">${tax.family||'—'}</a>"""),
        ("""      ${sp.summary?`<p class="wb">${sp.summary}</p>`:''}
      <p class="ws">Sources: GBIF · iNaturalist · Wikipedia · Zoe.Logos-Graph v1.0</p>`;""",
         """      ${sp.summary?`<p class="wb">${sp.summary}</p>`:''}
      ${relatedHTML(sp)}
      <p class="ws">Sources: GBIF · iNaturalist · Wikipedia · Zoe.Logos-Graph v1.1</p>`;"""),
        ("""  activeMediaFilter = null;  // reset media filter on new species""",
         """  activeMediaFilter = null;  // reset media filter on new species
  evFilter = 'all';"""),
        ("""      SHOWN_PAPERS = sorted;
      html += `<div class="cs"><div>` + sorted.map((p, i) => {""",
         """      const nM = sorted.filter(isMethods).length;
      if (nM) html += `<div class="ev-chips">${[['all','All',sorted.length],['comm','Communication',sorted.length-nM],['methods','Methods',nM]]
        .map(([k,l,n]) => `<button class="ev-chip ${evFilter===k?'on':''}" onclick="evFilter='${k}';rtab('evidence')">${l} (${n})</button>`).join('')}</div>`;
      const shown = (!nM || evFilter === 'all') ? sorted : sorted.filter(p => (evFilter === 'methods') === isMethods(p));
      SHOWN_PAPERS = shown;
      html += `<div class="cs"><div>` + shown.map((p, i) => {"""),
        ("""        // Themes as pills""",
         """        if (isMethods(p)) badges.push('<span class="pill" style="background:rgba(233,185,73,.12);color:#e9b949;border-color:rgba(233,185,73,.45)">methods</span>');
        // Themes as pills"""),
        ("""let SHOWN_PAPERS = [];""", METHODS_JS + """
// methods papers on animal signals: machine learning, signal processing, automatic detection, datasets
function isMethods(p) { return METHODS_RX.test((p.title||'') + ' ' + (p.abstract||'')); }
let evFilter = 'all';

// species studied in the same papers, and species of the same family
let DOI_INDEX = null;
function relatedHTML(sp) {
  const me = sp.scientific_name, raw = EMBEDDED_DB.find(s => s.sci === me);
  if (!raw) return '';
  if (!DOI_INDEX) {
    DOI_INDEX = {};
    EMBEDDED_DB.forEach(s => (s.papers||[]).forEach(p => { const d = (p.doi||'').toLowerCase(); if (d) (DOI_INDEX[d] = DOI_INDEX[d] || []).push(s.sci); }));
  }
  const together = {};
  (raw.papers||[]).forEach(p => (DOI_INDEX[(p.doi||'').toLowerCase()]||[]).forEach(o => { if (o !== me) together[o] = (together[o]||0) + 1; }));
  const fam = EMBEDDED_DB.filter(s => raw.family && s.family === raw.family && s.sci !== me).sort((a,b) => b.papers.length - a.papers.length);
  const chip = (s, extra) => `<button class="rel" title="${esc(s.sci)}" onclick="openSp('${s.sci.toLowerCase().replace(/ /g,'_')}')">${esc(s.en||s.sci)}${extra?` <span>${extra}</span>`:''}</button>`;
  const tog = Object.entries(together).sort((a,b) => b[1]-a[1]).slice(0, 10)
    .map(([sci, n]) => chip(EMBEDDED_DB.find(s => s.sci === sci), n + (n > 1 ? ' papers' : ' paper')));
  const fm = fam.slice(0, 12).map(s => chip(s, ''));
  if (!tog.length && !fm.length) return '';
  return `<div class="cs" style="margin-top:1.4rem">
    ${tog.length ? `<div class="cl">studied together with</div><div class="rels">${tog.join('')}</div>` : ''}
    ${fm.length ? `<div class="cl" style="margin-top:.9rem">same family · ${esc(raw.family)}</div><div class="rels">${fm.join('')}${fam.length > 12 ? `<a class="rel" href="taxonomy.html#${encodeURIComponent(raw.family)}">all ${fam.length} →</a>` : ''}</div>` : ''}
  </div>`;
}

let SHOWN_PAPERS = [];"""),
        ("""    const want = sessionStorage.getItem('open_species');""",
         """    const want = sessionStorage.getItem('open_species') || decodeURIComponent(location.hash.slice(1));"""),
    ])


def graph_page():
    page = 'graph_explorer.html'
    patch(page, "id=\"grp-fam\"", [
        ("""      <button class="mode-btn" id="grp-theme" onclick="setGroupBy('theme',this)">communicative theme</button>
      <button class="mode-btn" id="grp-fn" onclick="setGroupBy('function',this)">communicative function</button>""",
         """      <button class="mode-btn" id="grp-ord" onclick="setGroupBy('order',this)">order</button>
      <button class="mode-btn" id="grp-fam" onclick="setGroupBy('family',this)">family</button>
      <button class="mode-btn" id="grp-theme" onclick="setGroupBy('theme',this)">communicative theme</button>
      <button class="mode-btn" id="grp-fn" onclick="setGroupBy('function',this)">communicative function</button>
      <button class="mode-btn" id="grp-pap" onclick="setGroupBy('papers',this)">studied together</button>"""),
        ("""'#grp-none,#grp-theme,#grp-fn,#grp-sp'""", """'#grp-none,#grp-theme,#grp-fn,#grp-sp,#grp-ord,#grp-fam,#grp-pap'"""),
        ("""  if (groupBy === 'theme' || groupBy === 'function') {
    return getGroupedData(groupBy);
  }""",
         """  if (['theme','function','order','family'].includes(groupBy)) {
    return getGroupedData(groupBy);
  }
  // species studied in the same paper, line thickness = number of shared papers
  if (groupBy === 'papers') {
    const pe = (RAW_DATA.paper_edges || []).filter(e => e.weight >= minWeight);
    const ids = new Set(); pe.forEach(e => { ids.add(e.source); ids.add(e.target); });
    const nodes = RAW_DATA.nodes.filter(n => n.type === 'species' && ids.has(n.id) && speciesPasses(n));
    const vis = new Set(nodes.map(n => n.id));
    return { nodes, edges: pe.filter(e => vis.has(e.source) && vis.has(e.target)) };
  }"""),
        ("""    if (kind === 'theme') {
      keys = sp.data?.themes || [];
    } else { // function""",
         """    if (kind === 'theme') {
      keys = sp.data?.themes || [];
    } else if (kind === 'order' || kind === 'family') {
      keys = [kind === 'order' ? sp.data?.order_ : sp.data?.family].filter(Boolean);
    } else { // function"""),
        ("""      const hubId = (kind==='theme'?'hub-theme:':'hub-fn:') + k;""", """      const hubId = 'hub-' + kind + ':' + k;"""),
        ("""        if (kind==='theme') { colour = THEME_COLORS[k] || '#888'; label = k.replace(/_/g,' '); htype='theme'; }""",
         """        if (kind==='theme') { colour = THEME_COLORS[k] || '#888'; label = k.replace(/_/g,' '); htype='theme'; }
        else if (kind==='order' || kind==='family') { colour = kind==='order' ? '#9b8ef0' : '#e9b949'; label = k; htype = kind; }"""),
        ("""  if (kind === 'function') {
    const keepIds""", """  if (kind !== 'theme') {   // a group of one species says nothing
    const keepIds"""),
        # big views (all species by order or family) used to fly off screen: weaker push, pull to the
        # centre, and zoom to fit once the layout settles
        ("""    .force('charge', d3.forceManyBody().strength(d => d.type==='species' ? -180 : -80))""",
         """    .force('charge', d3.forceManyBody().strength(d => (d.type==='species' ? -180 : -80) * Math.min(1, 260 / nodes.length)))
    .force('x', d3.forceX(W/2).strength(nodes.length > 300 ? 0.06 : 0))
    .force('y', d3.forceY(H/2).strength(nodes.length > 300 ? 0.06 : 0))"""),
        ("""  simulation.on('tick', () => {""",
         """  simulation.on('end', () => {
    if (nodes.length < 2) return;
    const xs = nodes.map(n => n.x), ys = nodes.map(n => n.y), pad = 40;
    const x0 = Math.min(...xs) - pad, x1 = Math.max(...xs) + pad, y0 = Math.min(...ys) - pad, y1 = Math.max(...ys) + pad;
    const k = Math.min(1.5, W / (x1 - x0), H / (y1 - y0));
    svg.transition().duration(600).call(zoom.transform, d3.zoomIdentity.translate(W/2 - k * (x0 + x1) / 2, H/2 - k * (y0 + y1) / 2).scale(k));
  });
  simulation.on('tick', () => {"""),
    ])
    # species with no shared vocalisation or function float alone around the graph: leave them out
    patch(page, 'no link, left out', [
        ("""    return nodeIds.has(n.id) || (n.type === 'species');""",
         """    return nodeIds.has(n.id);    // species with no link, left out"""),
        ("""      g.append('text').text(d.label.split(' ')[0])""",
         """      g.append('text').text(d.label.length <= 14 ? d.label : d.label.split(/[\\s-]/).pop())"""),
    ])


def compare_page():
    page = 'compare.html'
    patch(page, 'function suggest()', [
        (""".cmp-empty{""", """.cmp-sugg{display:flex;flex-wrap:wrap;gap:6px;align-items:center;justify-content:center;margin:1.2rem auto 0;max-width:900px}
.sugg-l{width:100%;text-align:center;font-size:11px;color:var(--hint);text-transform:uppercase;letter-spacing:.06em;margin-bottom:2px}
.sugg{font-family:'DM Sans',sans-serif;font-size:12px;padding:4px 11px;border-radius:99px;border:1px solid var(--border2);background:none;color:var(--text);cursor:pointer}
.sugg:hover{border-color:rgba(72,168,154,.5);color:var(--amber)}.sugg span{color:var(--hint);font-size:11px}
.cmp-empty{"""),
        ("""    <div class="cmp-empty" id="cmpEmpty">No species selected yet, search above to add up to 6.</div>""",
         """    <div class="cmp-empty" id="cmpEmpty">No species selected yet, search above to add up to 6.</div>
    <div class="cmp-sugg" id="cmpSugg"></div>"""),
        ("""  picked.forEach(sci=>loadImg(byEn[sci]));
}""", """  picked.forEach(sci=>loadImg(byEn[sci]));
  suggest();
}
// related species to add: same family first, then same order
function suggest(){
  const box=document.getElementById('cmpSugg'); if(!box) return;
  if(!picked.length || picked.length>=MAX){ box.innerHTML=''; return; }
  const seen=new Set(picked), out=[];
  const near=(key,n)=>picked.forEach(sci=>{ const s=byEn[sci];
    DB.filter(o=>!seen.has(o.sci) && o[key] && o[key]===s[key]).sort((a,b)=>(b.np||0)-(a.np||0)).slice(0,n)
      .forEach(o=>{ seen.add(o.sci); out.push([o, s[key]]); }); });
  near('family',4); if(out.length<4) near('order_',3);
  box.innerHTML = out.length ? `<div class="sugg-l">compare with related species</div>` + out.slice(0,10).map(([o,why]) =>
    `<button class="sugg" onclick="addSp('${o.sci.replace(/'/g,"\\\\'")}')">+ ${esc(o.en||o.sci)} <span>${esc(why)}</span></button>`).join('') : '';
}"""),
    ])


def home_page():
    page = 'index.html'
    patch(page, 'href="taxonomy.html"><span class="tool-tag', [
        ("""    Zoe.Logos-Graph reads scientific abstracts on animal communication,
    extracts structured knowledge using an LLM, and builds an explorable graph
    linking species, vocalisations, contexts, functions, and papers.""",
         """    Zoe.Logos-Graph collects peer-reviewed studies on animal communication,
    links each one to the species it is about, and builds an explorable atlas of
    species, signals, papers and recordings, updated every two weeks."""),
        ("""      <div class="tool-desc">757 species · search in 6 languages · thematic tagging · communication profiles · curated papers with DOI · species comparison.</div>""",
         """      <div class="tool-desc">757 species · search in 6 languages · communication profiles · peer-reviewed papers with DOI · methods papers · recordings with spectrograms.</div>"""),
        ("""      <div class="tool-desc">Interactive force graph with 3 modes: by theme, by class, by function. Drag nodes, zoom, double-click for species details.</div>
    </a>""",
         """      <div class="tool-desc">Interactive force graph: species grouped by order, family, communicative theme or function, or linked when studied in the same paper.</div>
    </a>
    <a class="tool-card" href="taxonomy.html"><span class="tool-tag live">new</span>
      <span class="tool-icon">⋔</span>
      <div class="tool-title">Taxonomy</div>
      <div class="tool-desc">Every species from class to order, family and species, sized by the number of papers.</div>
    </a>
    <a class="tool-card" href="data.html"><span class="tool-tag live">new</span>
      <span class="tool-icon">▦</span>
      <div class="tool-title">Data and research gaps</div>
      <div class="tool-desc">Which themes are studied in which classes, and the atlas as open files to download and cite.</div>
    </a>"""),
        ("""      <div class="tool-desc">Python pipeline: schema · validation · LLM extraction · embedded JSON · community detection · systematic review generator.</div>""",
         """      <div class="tool-desc">Python scripts that update the atlas every two weeks: OpenAlex search · full abstracts · species attribution · recordings · community detection.</div>"""),
        ("""    <div class="pipe-step"><span class="pipe-n">01</span><span class="pipe-label">abstracts</span></div>
    <div class="pipe-arr">→</div>
    <div class="pipe-step"><span class="pipe-n">02</span><span class="pipe-label">annotation</span></div>
    <div class="pipe-arr">→</div>
    <div class="pipe-step"><span class="pipe-n">03</span><span class="pipe-label">LLM extraction</span></div>
    <div class="pipe-arr">→</div>
    <div class="pipe-step"><span class="pipe-n">04</span><span class="pipe-label">validation</span></div>
    <div class="pipe-arr">→</div>
    <div class="pipe-step"><span class="pipe-n">05</span><span class="pipe-label">normalisation</span></div>""",
         """    <div class="pipe-step"><span class="pipe-n">01</span><span class="pipe-label">new papers</span></div>
    <div class="pipe-arr">→</div>
    <div class="pipe-step"><span class="pipe-n">02</span><span class="pipe-label">full abstracts</span></div>
    <div class="pipe-arr">→</div>
    <div class="pipe-step"><span class="pipe-n">03</span><span class="pipe-label">species attribution</span></div>
    <div class="pipe-arr">→</div>
    <div class="pipe-step"><span class="pipe-n">04</span><span class="pipe-label">topic check</span></div>
    <div class="pipe-arr">→</div>
    <div class="pipe-step"><span class="pipe-n">05</span><span class="pipe-label">recordings</span></div>"""),
        ("""Zoe.Logos-Graph · pilot v1.0 · computational ethology""", """Zoe.Logos-Graph · v1.1 · computational ethology"""),
    ])


def recordings_page():
    """quality grade on each recording, a 'best quality only' filter, other species
    audible in the background, and a link to download the file"""
    page = 'species_explorer.html'
    patch(page, 'let bestOnly', [
        ("""let activeMediaFilter = null;""",
         """let activeMediaFilter = null;
let bestOnly = false;     // Xeno-Canto quality A and iNaturalist research grade only
const isBest = r => r.q === 'A' || r.q === 'research';
const qualityLabel = q => q === 'research' ? 'research grade' : q === 'needs_id' ? 'needs ID' : q ? 'quality ' + q : '';"""),
        ("""    html += `<p style="font-size:11px;color:var(--hint);margin-bottom:.8rem">${recs.length} recordings · ${providerLabel}</p>`;""",
         """    html += `<p style="font-size:11px;color:var(--hint);margin-bottom:.8rem">${recs.length} recordings · ${providerLabel}</p>`;
    const nBest = recs.filter(isBest).length;
    if (nBest && nBest < recs.length)
      html += `<div class="media-filters"><button class="mf-chip ${bestOnly ? 'on' : ''}" onclick="bestOnly=!bestOnly;rtab('media')" title="Xeno-Canto quality A, iNaturalist research grade">best quality only <span style="opacity:.55">${nBest}</span></button></div>`;"""),
        ("""    const visible = recs.filter(r => {
      if (!activeMediaFilter) return true;""",
         """    const visible = recs.filter(r => {
      if (bestOnly && !isBest(r)) return false;
      if (!activeMediaFilter) return true;"""),
        ("""'GBIF ')+r.id:''}${r.duration?' · '+r.duration+(String(r.duration).includes(':')?'':'s'):''}</span>""",
         """'GBIF ')+r.id:''}${r.duration?' · '+r.duration+(String(r.duration).includes(':')?'':'s'):''}${r.q?' · '+qualityLabel(r.q):''}</span>"""),
    ])
    patch(page, 'class="rec-links"', [
        (""".ac .rec-id{""", """.rec-links{display:flex;gap:16px;flex-wrap:wrap;align-items:baseline}
.ac .rec-id{"""),
        ("""${r.date?' · '+r.date:''}</div>""",
         """${r.date?' · '+r.date:''}${r.also?'<br>also audible: '+r.also:''}</div>"""),
        ("""          ${r.url?`<a class="xcl" href="${r.url}" target="_blank">${isXC?'XC'+r.id+' on Xeno-Canto':src==='inat'?'Observation on iNaturalist':src==='gbif'?'Record on GBIF':'view source'} →</a>`:''}""",
         """          <div class="rec-links">${r.url?`<a class="xcl" href="${r.url}" target="_blank">${isXC?'XC'+r.id+' on Xeno-Canto':src==='inat'?'Observation on iNaturalist':src==='gbif'?'Record on GBIF':'view source'} →</a>`:''}${r.audio?`<a class="xcl" href="${r.audio}" download target="_blank" rel="noopener">download ↓</a>`:''}</div>"""),
    ])


def taxonomy_page():
    # the browser's own suggestions (things typed on other sites) are not species
    patch('taxonomy.html', 'autocomplete="off"', [
        ("""list="names">""", """list="names" autocomplete="off">"""),
    ])


def tidy_taxonomy():
    """one name per order: the same family appeared under two orders in the taxonomy"""
    html, species, eq, end = atlas.load_species()
    fixed = 0
    for sp in species:
        if sp.get('order_') == 'Crocodylia':
            sp['order_'] = 'Crocodilia'; fixed += 1
        if sp.get('family') == 'Cichlidae' and sp.get('order_') != 'Cichliformes':
            sp['order_'] = 'Cichliformes'; fixed += 1
    if fixed:
        atlas.save_species(html, species, eq, end)
        done.append('species_explorer.html (taxonomy, %d orders renamed)' % fixed)


def new_classes():
    """crustaceans and spiders: a filter on the species page and a colour in the taxonomy"""
    patch('species_explorer.html', 'data-f="Malacostraca"', [
        ("""    <button class="fchip" data-f="Cephalopoda">cephalopods</button>""",
         """    <button class="fchip" data-f="Cephalopoda">cephalopods</button>
    <button class="fchip" data-f="Malacostraca">crustaceans</button>
    <button class="fchip" data-f="Arachnida">spiders</button>"""),
    ])
    patch('taxonomy.html', "Malacostraca:'", [
        ("""Cephalopoda:'#d88fc4'}""", """Cephalopoda:'#d88fc4',Malacostraca:'#6cc4d8',Arachnida:'#c9a27a'}"""),
    ])


def visit_counter(code):
    """GoatCounter on every page (no cookies, no personal data), and every species
    opened counted as its own page, species/<id>, to see which ones people look at"""
    tag = ('<script data-goatcounter="https://%s.goatcounter.com/count" async '
           'src="//gc.zgo.at/count.js"></script>\n</head>' % code)
    for p in sorted(OUT.glob('*.html')):
        patch(p.name, 'data-goatcounter', [('</head>', tag)])
    patch('species_explorer.html', 'goatcounter.count', [
        ("""async function openSp(sid) {""",
         """async function openSp(sid) {
  if (window.goatcounter && window.goatcounter.count)
    window.goatcounter.count({path: 'species/' + sid, title: sid, event: false});"""),
    ])


if __name__ == '__main__':
    visit_counter('zoelogo')                     # GoatCounter: https://zoelogo.goatcounter.com
    for p in ('index.html', 'species_explorer.html', 'literature.html', 'graph_explorer.html', 'compare.html', 'giants.html'):
        if (OUT / p).exists():
            menu(p)
    species_page()
    recordings_page()
    tidy_taxonomy()
    new_classes()
    taxonomy_page()
    graph_page()
    compare_page()
    home_page()
    for d in done:
        print('updated  ' + d)
    for s in skipped:
        print('already  ' + s)
    print('Now run: python build_site.py')
