#!/usr/bin/env python3
"""
build_graph_data.py - Generates data/built/graph_communities.json for the
graph explorer, reading directly from species_explorer.html (the 184-species
source of truth). No SQLite dependency.

Produces the SAME json structure the original web/graph_explorer.html expects:
  nodes, edges, sp_edges, communities, stats

USAGE:
  python build_graph_data.py
"""
from __future__ import annotations
import re, json
from pathlib import Path
from collections import defaultdict
from itertools import combinations

try:
    import networkx as nx
except ImportError:
    print("pip install networkx --break-system-packages"); raise SystemExit(1)
try:
    import community as community_louvain
    HAS_LOUVAIN = True
except ImportError:
    HAS_LOUVAIN = False

PROJ = Path(__file__).parent
OUT = PROJ / 'outputs'
BUILT = PROJ / 'outputs' / 'data' / 'built'
BUILT.mkdir(parents=True, exist_ok=True)

CLASS_COLORS = {'Aves':'#4ecdc4','Mammalia':'#ff6b6b','Amphibia':'#ffd93d',
    'Actinopterygii':'#6c5ce7','Insecta':'#a29bfe','Reptilia':'#e17055','Cephalopoda':'#fd79a8'}
VOC_TYPE_COLORS = {'vocalisation':'#e8a427','function':'#9b8ef0','context':'#2cb88a'}
COMMUNITY_COLORS = ['#4ecdc4','#ff6b6b','#ffd93d','#6c5ce7','#a29bfe','#fd79a8',
    '#00b894','#0984e3','#e17055','#fdcb6e','#e84393','#00cec9','#74b9ff','#fab1a0','#ff7675']

# ── Load species from species_explorer.html ──
print("Loading species from species_explorer.html...")
html = (OUT / 'species_explorer.html').read_text(encoding='utf-8')
m = re.search(r'const EMBEDDED_DB = (\[.*?\]);', html, re.DOTALL)
SPECIES = json.loads(m.group(1))
print(f"  {len(SPECIES)} species")

# ── Build bipartite graph: species <-> voc/function/context ──
G = nx.Graph()
for sp in SPECIES:
    sid = 'sp:' + sp['sci']
    G.add_node(sid, node_type='species', label=sp['en'],
               scientific_name=sp['sci'], class_=sp.get('class_',''),
               order_=sp.get('order_',''), family=sp.get('family',''),
               themes=sp.get('themes',[]), learning=sp.get('learning',''),
               image_url=sp.get('image',{}).get('url','') if isinstance(sp.get('image'),dict) else '')
    for v in sp.get('voc',[]):
        if not v or v == '—': continue
        nid = 'voc:' + v.lower()
        if not G.has_node(nid): G.add_node(nid, node_type='vocalisation', label=v)
        G.add_edge(sid, nid, weight=1)
    for f in sp.get('fn',[]):
        if not f: continue
        nid = 'fn:' + f.lower()
        if not G.has_node(nid): G.add_node(nid, node_type='function', label=f)
        G.add_edge(sid, nid, weight=1)
    for c in sp.get('ctx',[]):
        if not c: continue
        nid = 'ctx:' + c.lower()
        if not G.has_node(nid): G.add_node(nid, node_type='context', label=c)
        G.add_edge(sid, nid, weight=1)

# ── Species-species projection: shared traits ──
Gsp = nx.Graph()
sp_nodes = [n for n,d in G.nodes(data=True) if d['node_type']=='species']
for s in sp_nodes: Gsp.add_node(s)
trait_to_species = defaultdict(list)
for s in sp_nodes:
    for nb in G.neighbors(s):
        trait_to_species[nb].append(s)
for trait, sps in trait_to_species.items():
    for a, b in combinations(sps, 2):
        if Gsp.has_edge(a,b):
            Gsp[a][b]['weight'] += 1
            Gsp[a][b]['shared'].append(G.nodes[trait]['label'])
        else:
            Gsp.add_edge(a,b,weight=1,shared=[G.nodes[trait]['label']])

# ── Community detection (Louvain on species projection) ──
print("Detecting communities...")
if HAS_LOUVAIN and Gsp.number_of_edges() > 0:
    part = community_louvain.best_partition(Gsp, weight='weight', random_state=42)
else:
    # fallback: greedy modularity
    from networkx.algorithms.community import greedy_modularity_communities
    comms = greedy_modularity_communities(Gsp, weight='weight')
    part = {}
    for i, c in enumerate(comms):
        for n in c: part[n] = i
# propagate species community to whole bipartite graph
communities_bip = dict(part)
n_comm = len(set(part.values())) if part else 0
print(f"  {n_comm} communities")

# ── Build JSON payload ──
nodes = []
for nid, data in G.nodes(data=True):
    nt = data['node_type']
    comm = communities_bip.get(nid, 0)
    if nt == 'species':
        color = CLASS_COLORS.get(data.get('class_',''), COMMUNITY_COLORS[comm % len(COMMUNITY_COLORS)])
    else:
        color = VOC_TYPE_COLORS.get(nt, '#454854')
    degree = G.degree(nid, weight='weight')
    nodes.append({
        'id': nid, 'label': data.get('label', nid), 'type': nt,
        'community': comm, 'color': color,
        'size': max(6, min(28, 8 + degree * 1.2)) if nt=='species' else max(5, min(18, 5+degree)),
        'data': {
            'scientific_name': data.get('scientific_name',''),
            'class_': data.get('class_',''), 'order_': data.get('order_',''),
            'family': data.get('family',''), 'image_url': data.get('image_url',''),
            'themes': data.get('themes',[]), 'learning': data.get('learning',''),
        } if nt=='species' else {},
    })

edges = [{'source':a,'target':b,'weight':d.get('weight',1)} for a,b,d in G.edges(data=True)]
sp_edges = [{'source':a,'target':b,'weight':d['weight'],'shared':d['shared'][:6]}
            for a,b,d in Gsp.edges(data=True)]

comm_members = defaultdict(list); comm_traits = defaultdict(list)
for nid, comm in communities_bip.items():
    if G.nodes[nid].get('node_type')=='species':
        comm_members[comm].append(G.nodes[nid].get('label',''))
# traits per community = most common traits among member species
for comm, members in comm_members.items():
    member_ids = ['sp:'+s['sci'] for s in SPECIES if s['en'] in members]
    tc = defaultdict(int)
    for mid in member_ids:
        if G.has_node(mid):
            for nb in G.neighbors(mid):
                tc[G.nodes[nb]['label']] += 1
    comm_traits[comm] = [t for t,_ in sorted(tc.items(), key=lambda x:-x[1])]

communities_summary = []
for cid in sorted(comm_members.keys()):
    communities_summary.append({
        'id': cid, 'color': COMMUNITY_COLORS[cid % len(COMMUNITY_COLORS)],
        'species': sorted(comm_members[cid])[:12],
        'traits': comm_traits[cid][:8],
        'size': len(comm_members[cid]),
    })

payload = {
    'nodes': nodes, 'edges': edges, 'sp_edges': sp_edges,
    'communities': communities_summary,
    'stats': {
        'n_species': sum(1 for n in nodes if n['type']=='species'),
        'n_claims': sum(1 for n in nodes if n['type']!='species'),
        'n_edges': len(edges),
        'n_communities': len(communities_summary),
    },
}

out = BUILT / 'graph_communities.json'
out.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
print(f"DONE: wrote {out}")
print(f"  {payload['stats']['n_species']} species, {payload['stats']['n_claims']} trait nodes,")
print(f"  {payload['stats']['n_edges']} edges, {payload['stats']['n_communities']} communities")