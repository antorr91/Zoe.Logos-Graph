# Zoe.Logos-Graph

**A comparative atlas of animal communication.**
879 species · peer-reviewed papers updated every two weeks · an interactive knowledge graph.

**The live site is available at:** https://antorr91.github.io/Zoe.Logos-Graph/outputs/index.html

---

## What this is

Zoe.Logos-Graph links species to the vocalisations they produce, the contexts in which those occur, the communicative functions they serve, and the peer-reviewed studies that document them. In the graph explorer, the literature on animal communication is presented as an explorable, comparable, and citable network.

As a researcher passionate about animal communication, I built this as a personal project, a way to share with colleagues and friends a tool for studying the field. I am open to suggestions for improvements (feel free to email me at the address below).

---

## What the current repository covers so far

- **879 species** across 9 zoological classes (Aves 359, Mammalia 219, Amphibia 122, Insecta 105, Actinopterygii 35, Reptilia 22, Cephalopoda 7, Malacostraca 6, Arachnida 4).
- **Peer-reviewed papers**, each with a DOI and an open-access flag. Only journal articles are included; preprints are excluded. The current number is on the home page of the site.
- **16 research themes** (vocal learning, referential signalling, syntax, dialects, echolocation, infrasound, alarm, cooperation, deception, multimodal signalling, parent-offspring communication, individual recognition, turn-taking, cultural transmission, emotion, and honest signalling).
- **Recordings** from Xeno-Canto, iNaturalist and GBIF, with their original licences.

---

## Features

- **Species Explorer**: search all species, with per-species vocalisations, contexts, functions, frequency ranges, vocal-learning status, supporting papers (with a filter for methods papers) and recordings shown as spectrograms. Each species links to the species studied together with it and to those of the same family.
- **Taxonomy**: the atlas as a tree (class, order, family, species), sized by the number of papers; click a group to zoom in, click a species to open it.
- **Knowledge Graph**: an interactive D3 graph that can be grouped by species, order, family, communicative theme, communicative function, or by species studied in the same papers.
- **Literature view**: papers organised by research theme, with search, filtering, pagination and a separate filter for methods papers (machine learning, automatic detection, classification).
- **Species comparator**: side-by-side comparison across any of the species, with suggestions from the same family.
- **Data**: a map of research gaps (themes per zoological class) and the atlas as plain files (`papers.csv`, `species.csv`, `recordings.csv`, GraphML) for R, Python or Gephi.

---

## How the atlas stays up to date

On the 1st and 15th of every month a GitHub Action (`.github/workflows/update.yml`) runs `update_atlas.py` and publishes the result:

| step | script | what it does |
|---|---|---|
| 1 | `fetch_papers.py` | new journal articles from OpenAlex that name an atlas species and are about communication; full abstracts (OpenAlex, Europe PMC, Crossref); citation counts; GBIF synonyms |
| 2 | `assign_species.py` | decides which species each paper belongs to |
| 3 | `fetch_recordings.py` | checks the recordings and adds new ones from Xeno-Canto, iNaturalist and GBIF |
| 4 | `build_site.py` | home page numbers, compare, literature, graph, taxonomy and data pages, CSV exports |

A paper is shown under a species only if its title or abstract **names that species** (scientific name, synonym or specific English name) and it is about communication. Papers that name no atlas species stay in the Literature view. Every paper is in `data/archive/` (16 files, so that none gets too large); its `status` says where it is shown (`species`, `general`, `pending` while the full abstract is missing, `offtopic`).

If something looks wrong during an update (for example a service is down and many papers would be lost), nothing is published and GitHub sends an e-mail about the failed run.

**Manual decisions** go in `data/curation.csv` and always win:

```
doi,species,decision,note
10.1242/jeb.030270,Amphiprion ocellaris,keep,checked by hand
10.1186/s13293-024-00632-0,*,remove,not about communication
```

`*` as species removes the paper from the whole atlas. Other names for a species (old scientific names, English names) go in `data/synonyms.json`.

---

## Author

**Antonella Torrisi**
Centre for Digital Music · Queen Mary University of London
a.m.c.torrisi@qmul.ac.uk

## License

- **Code**: MIT License
- **Curated annotations and graph structure**: CC BY 4.0
- **Audio recordings**: retain the original licenses of their source archives (Xeno-Canto, iNaturalist, GBIF and others).
