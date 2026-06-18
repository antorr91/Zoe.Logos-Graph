# Zoe.Logos-Graph — Setup & Build Guide

A standalone HTML atlas of animal vocal communication: 184 species, 232 papers,
16 research themes, interactive knowledge graph, species comparator, and audio.

## Quick start (just view the site)

```bash
cd outputs
python -m http.server 8000
# open http://localhost:8000/index.html
```

That's it — all data is embedded in the HTML. No build step needed to view.

## Project layout

```
zoe-logos-graph/
├── outputs/                  ← the website (serve from here)
│   ├── index.html            landing page
│   ├── species_explorer.html main species browser (embeds all data + audio)
│   ├── literature.html       papers by research theme
│   ├── graph_explorer.html   interactive D3 knowledge graph
│   ├── compare.html          species comparator
│   ├── tree.jpg              hero background
│   └── data/built/
│       └── graph_communities.json   ← graph data (generated, see below)
├── build_graph_data.py       regenerates graph_communities.json
├── expand_curated.py         adds species + papers, regenerates literature.html
├── fetch_audio.py            fetches Xeno-Canto recordings into species_explorer
└── SETUP.md                  this file
```

## Rebuilding data (only if you change the species list)

The order matters. expand_curated rewrites species_explorer.html (wiping audio),
so always run it BEFORE fetch_audio.

```bash
# 1. expand species + papers (regenerates literature.html, species_explorer.html)
python expand_curated.py

# 2. fetch audio (needs a free Xeno-Canto API key — see below)
set XC_API_KEY=your-key-here          # Windows
export XC_API_KEY=your-key-here       # Mac/Linux
python fetch_audio.py --per-species 8

# 3. regenerate the graph data
python build_graph_data.py
mkdir -p outputs/data/built
cp data/built/graph_communities.json outputs/data/built/

# 4. serve
cd outputs && python -m http.server 8000
```

## Xeno-Canto API key (for audio)

Since Oct 2025 Xeno-Canto requires a free key:
1. Register at https://xeno-canto.org/ and verify your email
2. Copy your key from your Account page
3. Set XC_API_KEY as shown above

Birds, amphibians, insects and many mammals have recordings. Fish, reptiles and
cetaceans mostly don't — they show curated external links instead (Macaulay
Library, FishBase, DOSITS).

## Graph explorer controls

- **search** — find a species by name
- **group species by** — none (bipartite) / theme / function / species
- **node types** — toggle species / vocalisation / function / context
- **link strength** — filter weak connections
- **node size** — scale nodes
- **communities** — auto-detected clusters (click to highlight)
- **export** — SVG / JSON / GraphML

## Publishing to GitHub Pages

1. Push the whole repo to GitHub
2. Settings → Pages → deploy from branch, folder `/outputs`
   (or move outputs/ contents to repo root and deploy from there)
3. Your site will be at https://<username>.github.io/<repo>/
