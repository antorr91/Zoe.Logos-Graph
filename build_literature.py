#!/usr/bin/env python3
"""build_literature.py - Zoe.Logos-Graph
Build paginated literature.html by theme from data/archive/ (the species of each
paper come from assign_species.py). Papers without an atlas species still appear,
listed under their theme. Stdlib only.

  python build_literature.py
"""
import argparse, json, re, html as H
from atlas import METHODS_RX, load_papers
from urllib.parse import quote as urlquote

THEMES = [
 ("vocal_learning","#4ecdc4","Vocal Learning"),("referential","#ff6b6b","Referential Communication"),
 ("syntax","#ffd93d","Syntax & Combinatoriality"),("individual_recognition","#6c5ce7","Individual Recognition"),
 ("cultural_transmission","#a29bfe","Cultural Transmission"),("turn_taking","#fd79a8","Turn-taking & Duetting"),
 ("honest_signalling","#00b894","Honest Signalling"),("echolocation","#0984e3","Echolocation / Biosonar"),
 ("infrasound","#e17055","Infrasound Communication"),("dialects","#fdcb6e","Vocal Dialects"),
 ("emotion","#e84393","Emotional Signalling"),("multimodal","#00cec9","Multimodal Communication"),
 ("deception","#636e72","Deceptive Signalling"),("parent_offspring","#fab1a0","Parent-Offspring Communication"),
 ("alarm","#ff7675","Alarm & Predator Response"),("cooperation","#74b9ff","Cooperative Communication"),
]
KW = {
 "vocal_learning":[r"vocal learning",r"vocal production learning",r"song learning",r"vocal imitation",r"vocal plasticity",r"vocal convergence",r"babbling",r"imitat",r"learned vocal"],
 "referential":[r"referential",r"functionally referential",r"food[- ]associated call",r"food call",r"semantic"],
 "syntax":[r"syntax",r"syntactic",r"compositional",r"combinatorial",r"call combination",r"word[- ]order",r"proto[- ]syntax"],
 "individual_recognition":[r"individual recognition",r"signature whistle",r"individual identity",r"individual signature",r"caller identity",r"vocal signature",r"individually distinct",r"voice recognition"],
 "cultural_transmission":[r"cultural transmission",r"cultural evolution",r"vocal tradition",r"social learning of",r"culturally"],
 "turn_taking":[r"turn[- ]taking",r"duet",r"antiphonal",r"counter[- ]singing",r"vocal exchange",r"coordinated song"],
 "honest_signalling":[r"honest signal",r"size exaggeration",r"formant",r"body size",r"male quality",r"mate quality",r"condition[- ]depend"],
 "echolocation":[r"echolocat",r"biosonar",r"\bsonar\b",r"click train"],
 "infrasound":[r"infrasound",r"infrasonic",r"20[- ]?hz",r"below 20 hz"],
 "dialects":[r"dialect",r"geographic variation",r"regional variation",r"population[- ]specific song"],
 "emotion":[r"\bemotion",r"affective",r"\barousal",r"\bvalence",r"distress call",r"emotional state"],
 "multimodal":[r"multimodal",r"multi[- ]modal",r"visual display",r"gestur",r"cross[- ]modal",r"audio[- ]visual"],
 "deception":[r"decept",r"mimic",r"deceiv",r"false alarm",r"brood parasit"],
 "parent_offspring":[r"mother[- ]offspring",r"parent[- ]offspring",r"mother[- ]pup",r"begging call",r"isolation call",r"maternal",r"prenatal",r"offspring recognition"],
 "alarm":[r"alarm call",r"anti[- ]predator",r"\bmobbing\b",r"predator[- ]specific",r"warning call",r"predator type"],
 "cooperation":[r"cooperat",r"recruitment",r"collective",r"quorum",r"food[- ]sharing",r"group coordination",r"pack coordination",r"flock cohesion"],
}
KWc = {t:[re.compile(p, re.I) for p in pats] for t,pats in KW.items()}
def auto_themes(text):
    out=set()
    for t,pats in KWc.items():
        for p in pats:
            if p.search(text): out.add(t); break
    return out

def clean(s):
    if not s: return ""
    s=s.replace('&amp;lt;','<').replace('&amp;gt;','>').replace('&lt;','<').replace('&gt;','>')
    s=re.sub(r'</?i>','',s); s=re.sub(r'<[^>]+>','',s); return H.unescape(s).strip()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--template", default="outputs/literature.html", help="page to reuse head/nav/CSS from")
    ap.add_argument("--out", default="outputs/literature.html")
    ap.add_argument("--page", type=int, default=20)
    ap.add_argument("--abstract-chars", type=int, default=500, help="cap abstract length shown (0 = full)")
    args=ap.parse_args()

    # papers on a species page + communication papers that name no atlas species;
    # pending (not checked yet) and off-topic papers are left out
    papers={}
    for pr in load_papers().values():
        if pr.get("status") not in ("species","general"): continue
        papers[pr["doi"]]={"title":pr.get("title",""),"journal":pr.get("journal",""),"year":pr.get("year") or 0,
                           "doi":pr["doi"],"url":pr.get("url",""),"open_access":pr.get("open_access") or 0,
                           "citations":pr.get("citations") or 0,"abstract":pr.get("abstract",""),
                           "themes":set(pr.get("themes") or []),"species":pr.get("species") or []}
    total_species=len({s for p in papers.values() for s in p["species"]})

    # keyword densify every paper
    for p in papers.values():
        p["themes"] |= auto_themes((p["title"]+" "+p["abstract"]).lower())

    # build themed item list
    items=[]
    for p in papers.values():
        th=sorted(p["themes"])
        m=1 if METHODS_RX.search(p["title"]+" "+p["abstract"]) else 0
        if not th and not m: continue
        doi=p["doi"]
        url=p["url"] or (("https://doi.org/"+doi) if doi else "https://scholar.google.com/scholar?q="+urlquote(clean(p["title"])))
        ab=clean(p["abstract"])
        if args.abstract_chars and len(ab)>args.abstract_chars:
            ab=ab[:args.abstract_chars].rsplit(" ",1)[0]+"…"
        items.append({"t":th,"ti":clean(p["title"]) or "(untitled)","j":clean(p["journal"]) or "—",
                      "y":p["year"] or 0,"s":", ".join(p["species"][:3])+(" …" if len(p["species"])>3 else ""),
                      "d":doi,"u":url,"o":p["open_access"],"c":p["citations"],"a":ab,"m":m})
    total_tagged=len(items)

    tpl=open(args.template,encoding="utf-8",errors="replace").read()
    head=tpl[:tpl.find("</nav>")+len("</nav>")]

    extra_css = """
<style>
.lit-controls{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:1rem}
.lit-controls input[type=text]{flex:1;min-width:220px;margin-bottom:0}
.lit-controls select{width:auto;margin-bottom:0}
.theme-filters{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:1.25rem}
.tf{font-size:11px;padding:4px 11px;border-radius:99px;border:1px solid var(--border);background:none;color:var(--muted);cursor:pointer;font-family:'DM Sans',sans-serif;transition:.15s;white-space:nowrap}
.tf:hover{color:var(--text)}
.tf.on{font-weight:500}
.res-count{font-size:12px;color:var(--hint);margin-bottom:1rem}
.pager{display:flex;gap:4px;flex-wrap:wrap;align-items:center;justify-content:center;margin:2rem 0 1rem}
.pager button{font-size:12px;min-width:30px;padding:5px 9px;border:1px solid var(--border);background:var(--surface);color:var(--muted);border-radius:6px;cursor:pointer;font-family:'DM Sans',sans-serif}
.pager button:hover:not(:disabled){color:var(--amber);border-color:rgba(232,164,39,.4)}
.pager button.on{background:var(--amber);color:#0e0f11;border-color:var(--amber)}
.pager button:disabled{opacity:.35;cursor:default}
.pager .gap{color:var(--hint);padding:0 2px}
.pc .pc-theme{font-size:10px;padding:2px 8px;border-radius:99px;margin-right:5px;display:inline-block}
</style>
"""

    body = f"""
<div class="main">
  <div style="padding:2rem 0 1.25rem;border-bottom:1px solid var(--border);margin-bottom:1.5rem">
    <h1 style="font-family:'DM Serif Display',serif;font-size:28px;font-weight:400;color:var(--text)">Literature by <em style="color:var(--text);font-style:normal">research theme</em></h1>
    <div class="stat-row" style="margin-top:1.25rem">
      <div class="stat"><span class="stat-n">{total_species}</span><span class="stat-l">species</span></div>
      <div class="stat"><span class="stat-n">{total_tagged}</span><span class="stat-l">tagged papers</span></div>
      <div class="stat"><span class="stat-n">16</span><span class="stat-l">themes</span></div>
    </div>
  </div>
  <div class="lit-controls">
    <input type="text" id="q" placeholder="Search title, species, journal…" oninput="onSearch()">
    <select id="sort" onchange="onSort()">
      <option value="year">Newest first</option>
      <option value="cited">Most cited</option>
      <option value="title">Title A–Z</option>
    </select>
  </div>
  <div class="theme-filters" id="filters"></div>
  <div class="res-count" id="count"></div>
  <div class="paper-list" id="list"></div>
  <div class="pager" id="pager"></div>
</div>
<script>
const THEMES = {json.dumps({t:{ "label":l, "color":c } for t,c,l in THEMES}, ensure_ascii=False)};
const PAPERS = {json.dumps(items, ensure_ascii=False, separators=(',',':'))};
const PAGE = {args.page};
let state = {{ theme:'all', q:'', sort:'year', page:1 }};
function buildFilters(){{
  const counts = {{all: PAPERS.length}};
  for(const id in THEMES) counts[id] = PAPERS.filter(p=>p.t.includes(id)).length;
  const el = document.getElementById('filters');
  let html = `<button class="tf on" data-id="all" onclick="setTheme('all')" style="border-color:rgba(72,168,154,.5);color:var(--amber);background:var(--amber-dim)">All themes (${{counts.all}})</button>`;
  for(const [id,meta] of Object.entries(THEMES)){{
    html += `<button class="tf" data-id="${{id}}" onclick="setTheme('${{id}}')">${{meta.label}} (${{counts[id]}})</button>`;
  }}
  html += `<button class="tf" data-id="methods" onclick="setTheme('methods')" title="machine learning, signal processing, automatic detection, datasets">Methods (${{PAPERS.filter(p=>p.m).length}})</button>`;
  html += `<a class=\"tf\" href=\"giants.html\" style=\"border-color:#c9a86a99;color:#d9c08a;background:rgba(201,168,106,.12);text-decoration:none;font-weight:500\">Books</a>`;
  el.innerHTML = html;
}}
function setTheme(id){{
  state.theme=id; state.page=1;
  document.querySelectorAll('.tf').forEach(b=>{{
    const on=b.dataset.id===id; b.classList.toggle('on',on);
    if(on && id!=='all'){{const c=(THEMES[id]||{{color:'#e9b949'}}).color; b.style.borderColor=c+'99'; b.style.color=c; b.style.background=c+'1f';}}
    else if(id==='all' && b.dataset.id==='all'){{b.style.borderColor='rgba(232,164,39,.5)'; b.style.color='var(--amber)'; b.style.background='var(--amber-dim)';}}
    else {{b.style.borderColor=''; b.style.color=''; b.style.background='';}}
  }});
  render();
}}
function onSearch(){{ state.q=document.getElementById('q').value.toLowerCase().trim(); state.page=1; render(); }}
function onSort(){{ state.sort=document.getElementById('sort').value; state.page=1; render(); }}
function filtered(){{
  let rows=PAPERS;
  if(state.theme==='methods') rows=rows.filter(p=>p.m);
  else if(state.theme!=='all') rows=rows.filter(p=>p.t.includes(state.theme));
  if(state.q){{const q=state.q; rows=rows.filter(p=>(p.ti+' '+p.s+' '+p.j+' '+p.a).toLowerCase().includes(q));}}
  rows=rows.slice();
  if(state.sort==='year') rows.sort((a,b)=>b.y-a.y||b.c-a.c);
  else if(state.sort==='cited') rows.sort((a,b)=>b.c-a.c||b.y-a.y);
  else rows.sort((a,b)=>a.ti.localeCompare(b.ti));
  return rows;
}}
function esc(s){{return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}}
function card(p){{
  const badges=p.t.map(id=>{{const m=THEMES[id]; if(!m) return ''; return `<span class="pc-theme" style="background:${{m.color}}1f;color:${{m.color}};border:1px solid ${{m.color}}55">${{m.label}}</span>`;}}).join('')
    +(p.m?`<span class="pc-theme" style="background:#e9b9491f;color:#e9b949;border:1px solid #e9b94966">Methods</span>`:'');
  const oa=p.o? ' <span class="oa-badge">🔓 OA</span>':'';
  const cites=p.c? ` · ${{p.c}} citations`:'';
  const sp=p.s? `<span style="color:var(--teal);font-style:italic;margin-left:8px">${{esc(p.s)}}</span>`:'';
  const act=p.d? `<a class="pact" href="${{p.u}}" target="_blank">DOI: ${{p.d}}</a>`:`<a class="pact" href="${{p.u}}" target="_blank">Read ↗</a>`;
  return `<div class="pc">
    <a class="pc-title" href="${{p.u}}" target="_blank">${{esc(p.ti)}}</a>
    <div class="pc-meta"><span class="pc-journal">${{esc(p.j)}}</span> <span>(${{p.y||'—'}})</span>${{sp}}${{oa}}<span style="color:var(--hint)">${{cites}}</span></div>
    <div style="margin:.35rem 0">${{badges}}</div>
    ${{p.a? `<div class="pc-outcome">${{esc(p.a)}}</div>`:''}}
    <div class="pc-actions">${{act}}</div>
  </div>`;
}}
function pager(total){{
  const pages=Math.max(1,Math.ceil(total/PAGE)); if(state.page>pages) state.page=pages;
  const cur=state.page; let btns=[];
  const add=(n)=>btns.push(`<button class="${{n===cur?'on':''}}" onclick="goto(${{n}})">${{n}}</button>`);
  btns.push(`<button onclick="goto(${{cur-1}})" ${{cur===1?'disabled':''}}>‹ Prev</button>`);
  const win=2; const show=new Set([1,pages]);
  for(let n=cur-win;n<=cur+win;n++) if(n>=1&&n<=pages) show.add(n);
  let prev=0;
  [...show].sort((a,b)=>a-b).forEach(n=>{{ if(prev && n-prev>1) btns.push('<span class="gap">…</span>'); add(n); prev=n; }});
  btns.push(`<button onclick="goto(${{cur+1}})" ${{cur===pages?'disabled':''}}>Next ›</button>`);
  return btns.join('');
}}
function goto(n){{ state.page=n; render(); window.scrollTo({{top:0,behavior:'smooth'}}); }}
function render(){{
  const rows=filtered(); const total=rows.length;
  const start=(state.page-1)*PAGE; const slice=rows.slice(start,start+PAGE);
  document.getElementById('list').innerHTML=slice.length? slice.map(card).join('') : '<div class="empty">No papers match your filters.</div>';
  document.getElementById('pager').innerHTML=total>PAGE? pager(total):'';
  const from=total? start+1:0, to=Math.min(start+PAGE,total);
  const tlabel=state.theme==='all'?'all themes':state.theme==='methods'?'methods':THEMES[state.theme].label;
  document.getElementById('count').textContent=`${{from}}–${{to}} of ${{total}} papers · ${{tlabel}}`;
}}
buildFilters(); render();
</script>
</body>
</html>"""

    open(args.out,"w",encoding="utf-8").write(head+extra_css+body)
    no_sci=sum(1 for it in items if not it["s"])
    print(f"corpus species : {total_species}")
    print(f"themed papers  : {total_tagged}  (of which {no_sci} without a species)")
    print("per theme:")
    for t,_,lab in THEMES:
        print(f"  {lab:32s} {sum(1 for it in items if t in it['t'])}")
    print(f"wrote {args.out}")

if __name__=="__main__":
    main()