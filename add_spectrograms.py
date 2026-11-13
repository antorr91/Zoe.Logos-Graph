#!/usr/bin/env python3
"""
add_spectrograms.py - Zoe.Logos-Graph

One-off: adds spectrograms to the Media tab of outputs/species_explorer.html
(Xeno-Canto keeps its own image; iNaturalist and GBIF recordings get one drawn in
the browser from the audio file). Only the page code changes, the data stay as they are.
Safe to run twice. Run from the PROJECT ROOT, then you can delete this file.

  python add_spectrograms.py
"""
import sys
p = 'outputs/species_explorer.html'
h = open(p, encoding='utf-8').read()
if 'function drawSpectrogram' in h:
    sys.exit('spectrograms already in the page')
def rep(a, b):
    global h
    assert h.count(a) == 1, a[:60]
    h = h.replace(a, b)

rep(""".sono{width:100%;border-radius:8px;margin-bottom:10px;display:block;border:1px solid var(--border)}""",
""".sono{width:100%;border-radius:8px;margin-bottom:10px;display:block;border:1px solid var(--border)}
.specwrap{position:relative;margin-bottom:10px;cursor:pointer}
.specwrap canvas{width:100%;height:150px;display:block;border-radius:8px;border:1px solid var(--border);background:#07161a}
.spec-head{position:absolute;top:1px;bottom:1px;left:0;width:2px;background:#f2c14e;opacity:0;pointer-events:none}
.spec-note{position:absolute;left:10px;top:8px;font-size:11px;color:var(--hint);pointer-events:none}""")

rep("""          ${r.sono?`<img class="sono" src="${r.sono}" alt="spectrogram" onerror="this.style.display='none'">`:''}""",
"""          ${r.sono?`<img class="sono" src="${r.sono}" alt="spectrogram" onerror="this.style.display='none'">`:
            r.audio?`<div class="specwrap"><canvas class="spec" data-src="${r.audio}"></canvas><div class="spec-head"></div><div class="spec-note">loading spectrogram…</div></div>`:''}""")

rep("""  html += `</div>`;
  tc.innerHTML = html;
}

// ── EXPORT""", """  html += `</div>`;
  tc.innerHTML = html;
  initSpectrograms(tc);
}

// ── SPECTROGRAMS ───────────────────────────────────────────────────────
// Xeno-Canto gives its own spectrogram image; for iNaturalist and GBIF the
// spectrogram is computed here from the audio file (first 30 s), only when the
// card is on screen. Click on it to play from that point.
function initSpectrograms(root) {
  const io = new IntersectionObserver(es => es.forEach(e => {
    if (e.isIntersecting) { io.unobserve(e.target); drawSpectrogram(e.target); }
  }), {rootMargin: '200px'});
  root.querySelectorAll('canvas.spec').forEach(c => io.observe(c));
  root.querySelectorAll('.ac').forEach(card => {
    const a = card.querySelector('audio'), w = card.querySelector('.specwrap');
    if (!a || !w) return;
    const head = w.querySelector('.spec-head');
    a.addEventListener('timeupdate', () => {
      const secs = +w.dataset.secs || a.duration;
      if (!secs) return;
      head.style.opacity = a.currentTime > secs ? 0 : 1;
      head.style.left = (Math.min(a.currentTime, secs) / secs * 100) + '%';
    });
    w.addEventListener('click', ev => {
      const secs = +w.dataset.secs; if (!secs) return;
      const r = w.getBoundingClientRect();
      a.currentTime = (ev.clientX - r.left) / r.width * secs;
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

const SPEC_COLORS = [[7,22,26],[20,60,80],[40,120,130],[90,180,140],[240,200,90],[255,250,220]];
function specColor(v) {
  v = Math.max(0, Math.min(1, v)) * (SPEC_COLORS.length - 1);
  const i = Math.min(SPEC_COLORS.length - 2, Math.floor(v)), f = v - i, a = SPEC_COLORS[i], b = SPEC_COLORS[i + 1];
  return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f];
}

async function drawSpectrogram(c) {
  const w = c.parentElement, note = w.querySelector('.spec-note');
  try {
    const res = await fetch(c.dataset.src);
    if (!res.ok) throw new Error(res.status);
    const ac = new OfflineAudioContext(1, 1, 96000);
    const audio = await ac.decodeAudioData(await res.arrayBuffer());
    const sr = audio.sampleRate, secs = Math.min(audio.duration, 30);
    const x = audio.getChannelData(0).subarray(0, Math.floor(secs * sr));
    const N = 1024, W = c.width = Math.max(300, Math.min(1400, Math.round(c.clientWidth * (window.devicePixelRatio || 1))));
    const H = c.height = Math.round(150 * (window.devicePixelRatio || 1));
    const hop = Math.max(1, (x.length - N) / W), win = new Float32Array(N);
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
    // show up to the highest frequency that carries sound (birds ~10 kHz, bats higher)
    const peak = Math.max(...mean);
    let kMax = N / 2 - 1;
    while (kMax > 0 && mean[kMax] < peak - 35) kMax--;
    kMax = Math.max(Math.round((4000 / (sr / 2)) * (N / 2)), Math.min(N / 2 - 1, Math.round(kMax * 1.15)));
    const ctx = c.getContext('2d'), img = ctx.createImageData(W, H), range = 70;
    for (let col = 0; col < W; col++) {
      const db = cols[col];
      for (let y = 0; y < H; y++) {
        const k = Math.round((1 - y / (H - 1)) * kMax);
        const [r, g, b] = specColor((db[k] - (top - range)) / range);
        const o = (y * W + col) * 4;
        img.data[o] = r; img.data[o + 1] = g; img.data[o + 2] = b; img.data[o + 3] = 255;
      }
    }
    ctx.putImageData(img, 0, 0);
    const fmax = kMax / (N / 2) * sr / 2 / 1000, dpr = window.devicePixelRatio || 1;
    ctx.font = (10 * dpr) + 'px sans-serif'; ctx.fillStyle = 'rgba(255,255,255,.75)';
    ctx.fillText(fmax.toFixed(0) + ' kHz', 6 * dpr, 13 * dpr);
    ctx.fillText((fmax / 2).toFixed(0) + ' kHz', 6 * dpr, H / 2 + 4 * dpr);
    const tl = secs.toFixed(0) + ' s' + (audio.duration > 30 ? ' of ' + audio.duration.toFixed(0) : '');
    ctx.fillText(tl, W - ctx.measureText(tl).width - 6 * dpr, H - 6 * dpr);
    w.dataset.secs = secs;
    note.remove();
  } catch (e) {
    note.textContent = 'spectrogram not available for this archive';
    c.style.height = '34px';
  }
}

// ── EXPORT""")
open(p, 'w', encoding='utf-8').write(h)
print('spectrograms added to outputs/species_explorer.html')
