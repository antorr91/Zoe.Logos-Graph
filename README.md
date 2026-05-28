# Zoe.Logos-Graph

**A comparative atlas of animal vocal communication.**
An open, interactive knowledge resource integrating 184 species, 232 peer-reviewed studies, and curated bioacoustic recordings into a navigable knowledge graph.

🔗 **Live site:** https://antorr91.github.io/Zoe.Logos-Graph/
📁 **Repository:** https://github.com/antorr91/Zoe.Logos-Graph

---

## What this is

Zoe.Logos-Graph is a structured atlas of animal vocal communication built to be **explorable, comparable, and citable**. It links species to the vocalisations they produce, the behavioural contexts in which they occur, the communicative functions they serve, and the peer-reviewed studies that document them — and presents this network as an interactive resource rather than a flat catalogue.

It is designed for:

- **Researchers** in bioacoustics, animal cognition, and comparative communication, who need rapid cross-species comparisons grounded in primary literature.
- **Educators and students**, who benefit from an integrated view of how vocal behaviour is studied across taxa.
- **Anyone curious** about how a humpback whale, a túngara frog, and a Japanese tit can be meaningfully compared on the same map.

---

## Coverage at a glance

| | |
|---|---|
| **Species** | 184 across 7 zoological classes |
| **Peer-reviewed papers** | 232 with verified DOIs and open-access flags |
| **Research themes** | 16 (vocal learning, referential signalling, syntax, dialects, echolocation, infrasound, alarm, cooperation, deception, multimodal signalling, parent–offspring communication, individual recognition, turn-taking, cultural transmission, emotion, honest signalling) |
| **Taxonomic breadth** | Mammalia (82), Aves (59), Amphibia (13), Actinopterygii (11), Insecta (11), Reptilia (6), Cephalopoda (2) |
| **Audio recordings** | 600+ from Xeno-Canto v3, with external links to Macaulay Library, DOSITS, and FishBase for taxa not covered there |

---

## Features

- **Species Explorer** — a searchable browser of all 184 species, with detail pages presenting vocalisations, contexts, functions, frequency ranges, vocal-learning status, semiotic class, supporting papers, and embedded recordings where available.
- **Knowledge Graph** — an interactive D3 force-directed graph supporting four grouping modes: full bipartite view, species–species projection, grouping by vocal behaviour theme, and grouping by communicative function. Community detection via the Louvain algorithm reveals emergent clusters of functionally similar species.
- **Literature view** — 232 papers organised by the 16 research themes, with DOI links and one-line outcome summaries.
- **Species comparator** — side-by-side comparison of vocal repertoires, contexts, learning modes, and semiotic classification across selected species.

---

## Methods

**Species selection.** Species were curated to span the principal taxonomic groups in which vocal communication has been substantively studied. Within each group, selection prioritised species with at least one peer-reviewed bioacoustic or comparative-communication study published in a recognised venue.

**Paper selection.** For each species, between one and several papers were included, drawn from journals such as *Science*, *Nature*, *Current Biology*, *PNAS*, *Proceedings of the Royal Society B*, *Animal Behaviour*, *Behavioral Ecology*, *PLOS Biology*, *Bioacoustics*, and *Journal of Experimental Biology*. Every paper is referenced by DOI; open-access status is flagged.

**Knowledge graph construction.** Each species is represented as a node, linked to its vocalisations, contexts, and functions. A species–species projection weights pairwise edges by the count of shared traits. Community detection is performed with the Louvain algorithm on the weighted projection (python-louvain, seed=42). Communities are summarised by their dominant shared traits.

**Bioacoustic integration.** Audio is fetched from Xeno-Canto via its v3 API (free API key required since October 2025). For taxa underrepresented in Xeno-Canto — cetaceans, most fish, reptiles — the atlas links out to authoritative external archives.

---

## Project structure

```
zoe-logos-graph/
├── outputs/                    # The live website (served by GitHub Pages)
│   ├── index.html              # Landing page
│   ├── species_explorer.html   # Browse and search species (data embedded)
│   ├── graph_explorer.html     # Interactive knowledge graph
│   ├── literature.html         # Papers by research theme
│   ├── compare.html            # Species comparator
│   └── data/built/
│       └── graph_communities.json   # Pre-computed graph data
│
├── expand_curated.py           # Add or update species and papers
├── fetch_audio.py              # Fetch Xeno-Canto recordings
├── build_graph_data.py         # Regenerate the knowledge graph data
├── SETUP.md                    # Reproduction and rebuild instructions
└── README.md                   # This file
```

The website is fully static: open `outputs/index.html` or serve the `outputs/` folder with any HTTP server. No backend or build step is required to view it.

---

## Reproducing the build

```bash
# 1. Expand the curated species list and regenerate literature.html
python expand_curated.py

# 2. Fetch Xeno-Canto recordings (free API key required)
#    Register at https://xeno-canto.org/, then:
export XC_API_KEY=your-key-here
python fetch_audio.py --per-species 8

# 3. Regenerate the graph data from the species records
python build_graph_data.py
cp data/built/graph_communities.json outputs/data/built/

# 4. Serve locally
cd outputs
python -m http.server 8000
# then open http://localhost:8000
```

Full instructions, including dependencies and the rebuild order, are in [`SETUP.md`](SETUP.md).

---

## What this is *not*

Being explicit about scope avoids overstating claims:

- **Not a systematic review.** Inclusion is curated, not protocol-driven. The atlas is a navigation layer over the literature, not a substitute for PRISMA-style synthesis.
- **Not a complete bibliography.** 232 papers represent landmark and illustrative studies; many additional works exist for each species.
- **Not a substitute for primary sources.** Every claim links back to a DOI. Read the paper.
- **Not a model of biological truth.** Functions, contexts, and learning categories are coded as reported by the source literature; disagreements between sources are not yet harmonised.

---

## Author

**Antonio Maria Claudio Torrisi**
Centre for Digital Music · Queen Mary University of London
a.m.c.torrisi@qmul.ac.uk

---

## Cite this work

If you use Zoe.Logos-Graph in research or teaching, please cite it as:

> Torrisi, A. M. C. (2026). *Zoe.Logos-Graph: A comparative atlas of animal vocal communication* [Software]. https://github.com/antorr91/Zoe.Logos-Graph

A machine-readable `CITATION.cff` file is provided in this repository.

---

## License

- **Code** — MIT License
- **Curated annotations and graph structure** — CC BY 4.0
- **Audio recordings** — retain the original licenses of their source archives (Xeno-Canto, Macaulay Library, etc.)

---

## Acknowledgements

This atlas builds on the openly shared work of the bioacoustics and animal communication research community, the Xeno-Canto contributors, and the maintainers of the open-access journals from which the included literature is drawn.
