#!/usr/bin/env python3
"""
make_review.py - Zoe.Logos-Graph

A page to check by hand the papers 'to check' (the species or the topic appears only
in the abstract). For each one: correct, wrong species, or not about communication.

  python make_review.py

It opens the page in the browser (http://localhost:8001). Every click is saved at once
in data/curation.csv, so you can stop when you want and go on another day.
Leave this window open while you check; close it with Ctrl+C when you have finished.
Then: python update_atlas.py --offline
"""
import csv, json, re, threading, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import atlas

FIELDS = ['doi', 'species', 'decision', 'note']
NOTES = {'keep': 'checked by hand', 'rm': 'checked by hand: not this species',
         'rmall': 'checked by hand: not about communication'}
lock = threading.Lock()


def read_rows():
    rows = {}
    if atlas.CURATION.exists():
        with open(atlas.CURATION, encoding='utf-8-sig', newline='') as f:
            for r in csv.DictReader(f):
                doi = atlas.norm_doi(r.get('doi'))
                if doi:
                    sp = (r.get('species') or '*').strip() or '*'
                    rows[(doi, sp)] = dict({k: (r.get(k) or '').strip() for k in FIELDS}, doi=doi, species=sp)
    return rows


def write_rows(rows):
    tmp = atlas.CURATION.with_suffix('.tmp')
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows.values())
    tmp.replace(atlas.CURATION)


def decide(doi, sci, prev, new):
    """one click: take away the previous decision for this paper, write the new one"""
    doi = atlas.norm_doi(doi)
    with lock:
        rows = read_rows()
        if prev == 'rmall':
            rows.pop((doi, '*'), None)
        elif prev:
            rows.pop((doi, sci), None)
        if new == 'rmall':
            rows[(doi, '*')] = {'doi': doi, 'species': '*', 'decision': 'remove', 'note': NOTES[new]}
        elif new:
            rows[(doi, sci)] = {'doi': doi, 'species': sci, 'decision': 'keep' if new == 'keep' else 'remove',
                                'note': NOTES[new]}
        write_rows(rows)
        return len(rows)


def make_page():
    html, species, eq, end = atlas.load_species()
    syn = atlas.read_json(atlas.SYNONYMS, {})
    papers = atlas.load_papers()
    by_sci = {s['sci']: s for s in species}

    items = []
    for p in papers.values():
        if p.get('status') != 'species':
            continue
        for sci in p.get('species') or []:
            if sci in (p.get('sure') or []) or sci not in by_sci:
                continue
            items.append({'doi': p['doi'], 'sci': sci, 'en': by_sci[sci].get('en') or '',
                          'title': p['title'], 'journal': p.get('journal') or '', 'year': p.get('year') or '',
                          'abstract': p.get('abstract') or '', 'why': p.get('why') or ''})
    items.sort(key=lambda i: (i['sci'], -(i['year'] or 0)))

    # what to highlight: scientific name, "G. species", synonyms, English names
    terms = {}
    for sci in {i['sci'] for i in items}:
        g, *rest = sci.split()
        t = [sci, '%s. %s' % (g[0], ' '.join(rest))] + (syn.get('manual') or {}).get(sci, [])
        t += [e.strip() for e in re.split(r'[,/;]', by_sci[sci].get('en') or '') if len(e.strip()) > 3]
        terms[sci] = sorted(set(t), key=len, reverse=True)

    page = PAGE.replace('/*ITEMS*/[]', json.dumps(items, ensure_ascii=False)) \
               .replace('/*TERMS*/{}', json.dumps(terms, ensure_ascii=False))
    print('%d papers to check for %d species, %d already decided' % (len(items), len(terms), len(decisions(items))))
    return page, items


def decisions(items):
    """the decisions already in data/curation.csv, read again each time the page opens"""
    rows, dec = read_rows(), {}
    for i in items:
        doi = atlas.norm_doi(i['doi'])
        if (doi, '*') in rows and rows[(doi, '*')]['decision'] == 'remove':
            dec[i['doi'] + '|' + i['sci']] = 'rmall'
        elif (doi, i['sci']) in rows:
            dec[i['doi'] + '|' + i['sci']] = 'keep' if rows[(doi, i['sci'])]['decision'] == 'keep' else 'rm'
    return dec


class Review(BaseHTTPRequestHandler):
    page, items = '', []

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(self.page.replace('/*DEC*/{}', json.dumps(decisions(self.items))).encode('utf-8'))

    def do_POST(self):
        try:
            d = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            n = decide(d['doi'], d['sci'], d.get('prev') or '', d.get('new') or '')
            body, code = json.dumps({'rows': n}).encode(), 200
        except Exception as e:
            body, code = json.dumps({'error': str(e)}).encode(), 500
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def main():
    Review.page, Review.items = make_page()
    old = atlas.PROJ / 'review' / 'review.html'          # the old page, saved only in the browser
    if old.exists():
        old.unlink()
    for port in range(8001, 8011):
        try:
            server = ThreadingHTTPServer(('127.0.0.1', port), Review)
            break
        except OSError:
            continue
    url = 'http://localhost:%d' % port
    print('review page: %s   (every click is saved in data/curation.csv)' % url)
    print('leave this window open while you check, close it with Ctrl+C')
    print('then: python update_atlas.py --offline')
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nstopped. Decisions in data/curation.csv: %d' % len(read_rows()))


PAGE = r'''<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Zoe.Logos-Graph, papers to check</title>
<style>
:root{--bg:#072928;--surface:#0c332f;--border:rgba(255,255,255,.1);--text:#eaf3ef;--muted:#7fa39c;--hint:#4f756e;--ok:#48a89a;--bad:#e07a5f;--gold:#e9b949}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px/1.5 system-ui,sans-serif}
header{position:sticky;top:0;background:rgba(7,41,40,.95);border-bottom:1px solid var(--border);padding:12px 20px;display:flex;gap:12px;flex-wrap:wrap;align-items:center;z-index:2}
h1{font-size:17px;margin:0 12px 0 0;font-weight:500}
select,input,button{font:inherit;color:var(--text);background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:5px 9px}
button{cursor:pointer}button:hover{border-color:var(--muted)}
.bar{flex:1;min-width:120px;height:6px;background:var(--surface);border-radius:3px;overflow:hidden}.bar i{display:block;height:100%;background:var(--ok)}
main{max-width:980px;margin:0 auto;padding:16px 20px 60px}
.it{background:var(--surface);border:1px solid var(--border);border-left:4px solid var(--border);border-radius:8px;padding:12px 14px;margin:10px 0}
.it.keep{border-left-color:var(--ok)}.it.rm,.it.rmall{border-left-color:var(--bad);opacity:.6}
.sp{font-size:12px;color:var(--gold)}.t{font-weight:600;margin:3px 0}.t a{color:var(--text)}.m{font-size:12px;color:var(--muted)}
.ab{font-size:13px;color:#c5d8d2;margin:6px 0}mark{background:rgba(233,185,73,.35);color:inherit;padding:0 2px;border-radius:2px}
.acts{display:flex;gap:8px;flex-wrap:wrap;margin-top:6px}.acts button.on{border-color:var(--text);background:#164a44}
.pg{display:flex;gap:8px;justify-content:center;margin-top:16px;align-items:center;color:var(--muted)}
</style></head><body>
<header>
  <h1>Papers to check</h1>
  <select id="sp"></select>
  <label><input type="checkbox" id="todo" checked> only undecided</label>
  <input id="q" placeholder="search in titles" size="18">
  <div class="bar"><i id="bar"></i></div><span id="count" class="m"></span>
  <span id="saved" class="m"></span>
</header>
<main><div id="list"></div><div class="pg" id="pg"></div></main>
<script>
const ITEMS = /*ITEMS*/[];
const TERMS = /*TERMS*/{};
let dec = /*DEC*/{};
const id = i => i.doi + '|' + i.sci;
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const reEsc = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
function mark(text, sci) {
  let h = esc(text);
  const t = (TERMS[sci] || []).filter(Boolean);
  if (!t.length) return h;
  return h.replace(new RegExp('(' + t.map(x => reEsc(esc(x))).join('|') + ')', 'gi'), '<mark>$1</mark>');
}
const counts = {};
ITEMS.forEach(i => counts[i.sci] = (counts[i.sci] || 0) + 1);
const sel = document.getElementById('sp');
sel.innerHTML = `<option value="">all species (${ITEMS.length})</option>` +
  Object.keys(counts).sort().map(s => `<option value="${esc(s)}">${esc(s)} (${counts[s]})</option>`).join('');
let page = 0;
const PER = 40;
function filtered() {
  const s = sel.value, q = document.getElementById('q').value.toLowerCase(), todo = document.getElementById('todo').checked;
  return ITEMS.filter(i => (!s || i.sci === s) && (!q || i.title.toLowerCase().includes(q)) && (!todo || !dec[id(i)]));
}
function render() {
  const f = filtered();
  counter();
  page = Math.min(page, Math.max(0, Math.ceil(f.length / PER) - 1));
  document.getElementById('list').innerHTML = f.slice(page * PER, page * PER + PER).map(i => {
    const d = dec[id(i)] || '';
    return `<div class="it ${d}" data-id="${esc(id(i))}">
      <div class="sp">${esc(i.sci)}${i.en ? ' · ' + esc(i.en) : ''}</div>
      <div class="t"><a href="https://doi.org/${esc(i.doi)}" target="_blank">${mark(i.title, i.sci)}</a></div>
      <div class="m">${esc(i.journal)} · ${esc(i.year)} · ${esc(i.why)}</div>
      ${i.abstract ? `<div class="ab">${mark(i.abstract, i.sci)}</div>` : '<div class="m">no abstract</div>'}
      <div class="acts">
        <button data-d="keep" class="${d === 'keep' ? 'on' : ''}">✓ correct</button>
        <button data-d="rm" class="${d === 'rm' ? 'on' : ''}">✗ not this species</button>
        <button data-d="rmall" class="${d === 'rmall' ? 'on' : ''}">✗ not about communication</button>
      </div></div>`;
  }).join('') || '<p class="m">Nothing left to check here.</p>';
  const pages = Math.ceil(f.length / PER);
  document.getElementById('pg').innerHTML = pages > 1 ?
    `<button ${page ? '' : 'disabled'} id="prev">←</button> page ${page + 1} of ${pages} <button ${page < pages - 1 ? '' : 'disabled'} id="next">→</button>` : '';
  const pr = document.getElementById('prev'), nx = document.getElementById('next');
  if (pr) pr.onclick = () => { page--; render(); scrollTo(0, 0); };
  if (nx) nx.onclick = () => { page++; render(); scrollTo(0, 0); };
}
function counter() {
  const n = Object.keys(dec).length;
  document.getElementById('bar').style.width = (100 * n / ITEMS.length) + '%';
  document.getElementById('count').textContent = `${n} of ${ITEMS.length} checked`;
}
document.getElementById('list').addEventListener('click', async e => {
  const b = e.target.closest('button[data-d]');
  if (!b) return;
  const k = b.closest('.it').dataset.id;
  const i = ITEMS.find(x => id(x) === k);
  const prev = dec[k] || '', next = prev === b.dataset.d ? '' : b.dataset.d;
  const msg = document.getElementById('saved');
  try {
    const r = await fetch('/decide', {method: 'POST', body: JSON.stringify({doi: i.doi, sci: i.sci, prev, new: next})});
    if (!r.ok) throw new Error((await r.json()).error);
    msg.textContent = 'saved in data/curation.csv';
    msg.style.color = 'var(--ok)';
  } catch (err) {
    msg.textContent = 'NOT saved: is make_review.py still running?';
    msg.style.color = 'var(--bad)';
    return;
  }
  // 'not about communication' is about the paper, so it holds for every species of that paper
  const same = (prev === 'rmall' || next === 'rmall') ? ITEMS.filter(x => x.doi === i.doi) : [i];
  same.forEach(x => { if (next) dec[id(x)] = next; else delete dec[id(x)]; });
  same.forEach(x => {
    const el = document.querySelector(`.it[data-id="${CSS.escape(id(x))}"]`);
    if (!el) return;
    el.className = 'it ' + (dec[id(x)] || '');
    el.querySelectorAll('button[data-d]').forEach(y => y.classList.toggle('on', y.dataset.d === dec[id(x)]));
  });
  counter();
});
[sel, document.getElementById('todo')].forEach(x => x.onchange = () => { page = 0; render(); });
document.getElementById('q').oninput = () => { page = 0; render(); };
render();
</script></body></html>
'''

if __name__ == '__main__':
    main()
    