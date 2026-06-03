#!/usr/bin/env python3
"""
discover_species_v2.py — Curated discovery of candidate species.

Instead of extracting binomials from paper text (which produced false
positives like "Python language"), this version starts from a CURATED
list of species known to be important in the bioacoustics / animal
communication literature, then validates each one by:
  1. Looking it up in GBIF for accurate taxonomy
  2. Checking OpenAlex that >=3 bioacoustic papers exist
  3. Pulling 3-5 exemplary papers for the review UI

Species already in your local database are filtered out automatically.

The curated list (~155 candidates) covers:
  Primates · Cetaceans · Pinnipeds · Bats · Rodents · Carnivores
  Ungulates · Marsupials · Elephants · Birds (songbirds, corvids,
  parrots, others) · Reptiles · Amphibians · Insects · Fish · Cephalopods
  · Homo sapiens (reference species)

USAGE:
  set OPENALEX_EMAIL=a.m.c.torrisi@qmul.ac.uk
  python discover_species_v2.py
  python discover_species_v2.py --min-papers 5   # stricter filter
"""
from __future__ import annotations
import os, re, json, time, argparse, sys, urllib.parse, urllib.request
from pathlib import Path
from datetime import datetime

PROJ = Path(__file__).parent
SPECIES_HTML = PROJ / 'outputs' / 'species_explorer.html'
OUT_DIR = PROJ / 'data' / 'discovery'
OUT_DIR.mkdir(parents=True, exist_ok=True)

EMAIL = os.environ.get('OPENALEX_EMAIL', '')

# ── Curated candidate species ─────────────────────────────────────────────────
# Selected from review papers and reference works in bioacoustics and animal
# communication research. Format: (scientific_name, common_name, group_tag)
# group_tag is used for filter UI and balanced display, not stored downstream.
CURATED = [
    # ── PRIMATES (apes, monkeys, lemurs, tarsiers) ────────────────────────────
    ('Pongo abelii',             'Sumatran orangutan',        'primates'),
    ('Pongo pygmaeus',           'Bornean orangutan',         'primates'),
    ('Hylobates lar',            'White-handed gibbon',       'primates'),
    ('Nomascus concolor',        'Black crested gibbon',      'primates'),
    ('Symphalangus syndactylus', 'Siamang',                   'primates'),
    ('Macaca fuscata',           'Japanese macaque',          'primates'),
    ('Macaca fascicularis',      'Long-tailed macaque',       'primates'),
    ('Papio anubis',             'Olive baboon',              'primates'),
    ('Papio ursinus',            'Chacma baboon',             'primates'),
    ('Cercopithecus diana',      'Diana monkey',              'primates'),
    ('Cercopithecus nictitans',  'Putty-nosed monkey',        'primates'),
    ('Cercocebus atys',          'Sooty mangabey',            'primates'),
    ('Saguinus oedipus',         'Cotton-top tamarin',        'primates'),
    ('Saimiri sciureus',         'Common squirrel monkey',    'primates'),
    ('Alouatta caraya',          'Black howler monkey',       'primates'),
    ('Alouatta palliata',        'Mantled howler monkey',     'primates'),
    ('Lemur catta',              'Ring-tailed lemur',         'primates'),
    ('Microcebus murinus',       'Gray mouse lemur',          'primates'),
    ('Propithecus coquereli',    "Coquerel's sifaka",         'primates'),
    ('Eulemur fulvus',           'Common brown lemur',        'primates'),
    ('Indri indri',              'Indri',                     'primates'),
    ('Tarsius syrichta',         'Philippine tarsier',        'primates'),
    ('Galago senegalensis',      'Senegal bushbaby',          'primates'),

    # ── CETACEANS (whales, dolphins, porpoises) ───────────────────────────────
    ('Tursiops aduncus',         'Indo-Pacific bottlenose dolphin', 'cetaceans'),
    ('Stenella frontalis',       'Atlantic spotted dolphin',  'cetaceans'),
    ('Stenella longirostris',    'Spinner dolphin',           'cetaceans'),
    ('Lagenorhynchus obliquidens','Pacific white-sided dolphin','cetaceans'),
    ('Sousa chinensis',          'Indo-Pacific humpback dolphin','cetaceans'),
    ('Globicephala macrorhynchus','Short-finned pilot whale', 'cetaceans'),
    ('Globicephala melas',       'Long-finned pilot whale',   'cetaceans'),
    ('Balaenoptera musculus',    'Blue whale',                'cetaceans'),
    ('Balaenoptera physalus',    'Fin whale',                 'cetaceans'),
    ('Eubalaena glacialis',      'North Atlantic right whale','cetaceans'),
    ('Eschrichtius robustus',    'Gray whale',                'cetaceans'),
    ('Balaena mysticetus',       'Bowhead whale',             'cetaceans'),

    # ── PINNIPEDS (seals, sea lions, walrus) ──────────────────────────────────
    ('Mirounga angustirostris',  'Northern elephant seal',    'pinnipeds'),
    ('Mirounga leonina',         'Southern elephant seal',    'pinnipeds'),
    ('Halichoerus grypus',       'Grey seal',                 'pinnipeds'),
    ('Phoca vitulina',           'Harbour seal',              'pinnipeds'),
    ('Pagophilus groenlandicus', 'Harp seal',                 'pinnipeds'),
    ('Zalophus californianus',   'California sea lion',       'pinnipeds'),
    ('Eumetopias jubatus',       'Steller sea lion',          'pinnipeds'),
    ('Arctocephalus tropicalis', 'Subantarctic fur seal',     'pinnipeds'),
    ('Odobenus rosmarus',        'Walrus',                    'pinnipeds'),

    # ── BATS ──────────────────────────────────────────────────────────────────
    ('Phyllostomus discolor',    'Pale spear-nosed bat',      'bats'),
    ('Carollia perspicillata',   "Seba's short-tailed bat",   'bats'),
    ('Saccopteryx bilineata',    'Greater sac-winged bat',    'bats'),
    ('Rousettus aegyptiacus',    'Egyptian fruit bat',        'bats'),
    ('Pteropus poliocephalus',   'Grey-headed flying fox',    'bats'),
    ('Myotis lucifugus',         'Little brown bat',          'bats'),
    ('Myotis daubentonii',       "Daubenton's bat",           'bats'),
    ('Pipistrellus pipistrellus','Common pipistrelle',        'bats'),
    ('Rhinolophus ferrumequinum','Greater horseshoe bat',     'bats'),
    ('Noctilio leporinus',       'Greater bulldog bat',       'bats'),

    # ── RODENTS ───────────────────────────────────────────────────────────────
    ('Marmota marmota',          'Alpine marmot',             'rodents'),
    ('Marmota flaviventris',     'Yellow-bellied marmot',     'rodents'),
    ('Heterocephalus glaber',    'Naked mole-rat',            'rodents'),
    ('Cavia porcellus',          'Guinea pig',                'rodents'),
    ('Octodon degus',            'Common degu',               'rodents'),
    ('Cynomys ludovicianus',     'Black-tailed prairie dog',  'rodents'),
    ('Urocitellus beldingi',     "Belding's ground squirrel", 'rodents'),
    ('Meriones unguiculatus',    'Mongolian gerbil',          'rodents'),
    ('Sciurus carolinensis',     'Eastern gray squirrel',     'rodents'),

    # ── CARNIVORES (other) ────────────────────────────────────────────────────
    ('Suricata suricatta',       'Meerkat',                   'carnivores'),
    ('Lycaon pictus',            'African wild dog',          'carnivores'),
    ('Panthera leo',             'Lion',                      'carnivores'),
    ('Panthera tigris',          'Tiger',                     'carnivores'),
    ('Acinonyx jubatus',         'Cheetah',                   'carnivores'),
    ('Ursus americanus',         'American black bear',       'carnivores'),
    ('Ursus arctos',             'Brown bear',                'carnivores'),
    ('Mephitis mephitis',        'Striped skunk',             'carnivores'),
    ('Helogale parvula',         'Common dwarf mongoose',     'carnivores'),

    # ── UNGULATES & TAPIRS ────────────────────────────────────────────────────
    ('Capreolus capreolus',      'Roe deer',                  'ungulates'),
    ('Dama dama',                'Fallow deer',               'ungulates'),
    ('Alces alces',              'Moose',                     'ungulates'),
    ('Bison bison',              'American bison',            'ungulates'),
    ('Giraffa camelopardalis',   'Giraffe',                   'ungulates'),
    ('Hippopotamus amphibius',   'Common hippopotamus',       'ungulates'),
    ('Tapirus indicus',          'Malayan tapir',             'ungulates'),
    ('Tapirus terrestris',       'Lowland tapir',             'ungulates'),
    ('Equus zebra',              'Mountain zebra',            'ungulates'),

    # ── ELEPHANTS ─────────────────────────────────────────────────────────────
    ('Loxodonta cyclotis',       'African forest elephant',   'elephants'),

    # ── MARSUPIALS ────────────────────────────────────────────────────────────
    ('Macropus rufus',           'Red kangaroo',              'marsupials'),
    ('Sarcophilus harrisii',     'Tasmanian devil',           'marsupials'),
    ('Petaurus breviceps',       'Sugar glider',              'marsupials'),
    ('Trichosurus vulpecula',    'Common brushtail possum',   'marsupials'),

    # ── BIRDS - SONGBIRDS ─────────────────────────────────────────────────────
    ('Sturnus vulgaris',         'European starling',         'songbirds'),
    ('Sturnus unicolor',         'Spotless starling',         'songbirds'),
    ('Turdus merula',            'Common blackbird',          'songbirds'),
    ('Turdus migratorius',       'American robin',            'songbirds'),
    ('Erithacus rubecula',       'European robin',            'songbirds'),
    ('Luscinia megarhynchos',    'Common nightingale',        'songbirds'),
    ('Acrocephalus arundinaceus','Great reed warbler',        'songbirds'),
    ('Acrocephalus palustris',   'Marsh warbler',             'songbirds'),
    ('Sylvia atricapilla',       'Eurasian blackcap',         'songbirds'),
    ('Phylloscopus collybita',   'Common chiffchaff',         'songbirds'),
    ('Hirundo rustica',          'Barn swallow',              'songbirds'),
    ('Cyanistes caeruleus',      'Eurasian blue tit',         'songbirds'),
    ('Poecile atricapillus',     'Black-capped chickadee',    'songbirds'),
    ('Geothlypis trichas',       'Common yellowthroat',       'songbirds'),
    ('Cardinalis cardinalis',    'Northern cardinal',         'songbirds'),
    ('Junco hyemalis',           'Dark-eyed junco',           'songbirds'),
    ('Agelaius phoeniceus',      'Red-winged blackbird',      'songbirds'),
    ('Vidua chalybeata',         'Village indigobird',        'songbirds'),
    ('Pycnonotus xanthopygos',   'White-spectacled bulbul',   'songbirds'),
    ('Turdoides bicolor',        'Southern pied babbler',     'songbirds'),

    # ── BIRDS - CORVIDS ───────────────────────────────────────────────────────
    ('Corvus monedula',          'Western jackdaw',           'corvids'),
    ('Corvus moneduloides',      'New Caledonian crow',       'corvids'),
    ('Corvus frugilegus',        'Rook',                      'corvids'),
    ('Corvus brachyrhynchos',    'American crow',             'corvids'),
    ('Garrulus glandarius',      'Eurasian jay',              'corvids'),
    ('Pica pica',                'Eurasian magpie',           'corvids'),
    ('Cyanocitta stelleri',      "Steller's jay",             'corvids'),
    ('Nucifraga columbiana',     "Clark's nutcracker",        'corvids'),

    # ── BIRDS - PARROTS ───────────────────────────────────────────────────────
    ('Amazona amazonica',        'Orange-winged amazon',      'parrots'),
    ('Cacatua galerita',         'Sulphur-crested cockatoo',  'parrots'),
    ('Nestor notabilis',         'Kea',                       'parrots'),
    ('Forpus passerinus',        'Green-rumped parrotlet',    'parrots'),
    ('Eolophus roseicapilla',    'Galah',                     'parrots'),

    # ── BIRDS - OTHER ─────────────────────────────────────────────────────────
    ('Gallus gallus',            'Red junglefowl / chicken',  'birds-other'),
    ('Anas platyrhynchos',       'Mallard duck',              'birds-other'),
    ('Aptenodytes patagonicus',  'King penguin',              'birds-other'),
    ('Pygoscelis adeliae',       'Adélie penguin',            'birds-other'),
    ('Spheniscus humboldti',     'Humboldt penguin',          'birds-other'),
    ('Spheniscus demersus',      'African penguin',           'birds-other'),
    ('Tyto alba',                'Barn owl',                  'birds-other'),
    ('Strix occidentalis',       'Spotted owl',               'birds-other'),
    ('Bubo bubo',                'Eurasian eagle-owl',        'birds-other'),
    ('Manacus vitellinus',       'Golden-collared manakin',   'birds-other'),
    ('Tympanuchus cupido',       'Greater prairie chicken',   'birds-other'),
    ('Calidris pugnax',          'Ruff',                      'birds-other'),

    # ── REPTILES ──────────────────────────────────────────────────────────────
    ('Crocodylus niloticus',     'Nile crocodile',            'reptiles'),
    ('Crocodylus porosus',       'Saltwater crocodile',       'reptiles'),
    ('Gekko gecko',              'Tokay gecko',               'reptiles'),
    ('Chelonia mydas',           'Green sea turtle',          'reptiles'),
    ('Caretta caretta',          'Loggerhead sea turtle',     'reptiles'),

    # ── AMPHIBIANS ────────────────────────────────────────────────────────────
    ('Hyla arborea',             'European tree frog',        'amphibians'),
    ('Bombina bombina',          'European fire-bellied toad','amphibians'),
    ('Allobates femoralis',      'Brilliant-thighed poison frog','amphibians'),
    ('Dendropsophus ebraccatus', 'Hourglass treefrog',        'amphibians'),
    ('Eleutherodactylus coqui',  'Common coqui',              'amphibians'),
    ('Hyperolius marmoratus',    'Painted reed frog',         'amphibians'),
    ('Pelophylax ridibundus',    'Marsh frog',                'amphibians'),

    # ── INSECTS ───────────────────────────────────────────────────────────────
    ('Schistocerca gregaria',    'Desert locust',             'insects'),
    ('Acheta domesticus',        'House cricket',             'insects'),
    ('Magicicada septendecim',   'Pharaoh periodical cicada', 'insects'),
    ('Anopheles gambiae',        'African malaria mosquito',  'insects'),
    ('Ephippiger ephippiger',    'Saddle-bearing bushcricket','insects'),
    ('Bombus terrestris',        'Buff-tailed bumblebee',     'insects'),
    ('Cicada orni',              'Manna ash cicada',          'insects'),
    ('Oecanthus pellucens',      'Italian tree cricket',      'insects'),

    # ── FISH ──────────────────────────────────────────────────────────────────
    ('Carassius auratus',        'Goldfish',                  'fish'),
    ('Pomacentrus partitus',     'Bicolor damselfish',        'fish'),
    ('Halobatrachus didactylus', 'Lusitanian toadfish',       'fish'),
    ('Opsanus tau',              'Oyster toadfish',           'fish'),
    ('Lutjanus erythropterus',   'Crimson snapper',           'fish'),
    ('Cyprinodon variegatus',    'Sheepshead minnow',         'fish'),
    ('Salaria pavo',             'Peacock blenny',            'fish'),
    ('Amphiprion clarkii',       "Clark's anemonefish",       'fish'),

    # ── CEPHALOPODS ───────────────────────────────────────────────────────────
    ('Octopus vulgaris',         'Common octopus',            'cephalopods'),
    ('Loligo vulgaris',          'European squid',            'cephalopods'),
    ('Sepioteuthis lessoniana',  'Bigfin reef squid',         'cephalopods'),

    # ── REFERENCE SPECIES (humans) ────────────────────────────────────────────
    ('Homo sapiens',             'Human',                     'reference'),
]
print(f'Curated list size: {len(CURATED)}')

# ── HTTP helper ───────────────────────────────────────────────────────────────
def http_get(url: str, max_retries: int = 3) -> dict:
    headers = {'User-Agent': f'Zoe.Logos-Graph/2.0 ({EMAIL or "no-email"})'}
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode('utf-8'))
        except Exception as e:
            if attempt == max_retries - 1:
                return {}
            time.sleep(2 ** attempt)
    return {}


# ── Load existing species ─────────────────────────────────────────────────────
def load_existing() -> set:
    if not SPECIES_HTML.exists():
        return set()
    html = SPECIES_HTML.read_text(encoding='utf-8')
    m = re.search(r'const EMBEDDED_DB = (\[.*?\]);', html, re.DOTALL)
    if not m:
        return set()
    db = json.loads(m.group(1))
    return {sp['sci'].lower() for sp in db}


# ── GBIF taxonomy lookup ──────────────────────────────────────────────────────
def gbif_taxonomy(sci: str) -> dict:
    url = ('https://api.gbif.org/v1/species/match?name=' +
           urllib.parse.quote(sci) + '&strict=false')
    d = http_get(url)
    if not d or d.get('matchType') == 'NONE':
        return {}
    if d.get('rank') not in ('SPECIES', 'SUBSPECIES'):
        return {}
    return {
        'class_':       d.get('class', ''),
        'order_':       d.get('order', ''),
        'family':       d.get('family', ''),
        'gbif_key':     d.get('usageKey', 0),
        'confidence':   d.get('confidence', 0),
        'matched_name': d.get('canonicalName', sci),
    }


# ── OpenAlex paper search for a species ───────────────────────────────────────
def openalex_papers(sci: str, per_page: int = 5) -> list:
    """Search OpenAlex for bioacoustic papers about this species."""
    # Use both common search and exact title/abstract match
    params = {
        'search': f'"{sci}" vocal communication',
        'filter': 'has_abstract:true,type:article,cited_by_count:>10',
        'sort':   'cited_by_count:desc',
        'per-page': str(per_page),
    }
    if EMAIL: params['mailto'] = EMAIL
    url = 'https://api.openalex.org/works?' + urllib.parse.urlencode(params)
    d = http_get(url)
    out = []
    for w in d.get('results', []):
        title = w.get('title') or ''
        doi   = (w.get('doi') or '').replace('https://doi.org/', '')
        out.append({
            'title': title[:200],
            'doi': doi,
            'year': w.get('publication_year'),
            'cited_by': w.get('cited_by_count', 0),
            'venue': (w.get('primary_location', {}) or {})
                     .get('source', {} or {}).get('display_name', '') if w.get('primary_location') else '',
        })
    return out


# ── Main processing loop ──────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--min-papers', type=int, default=3,
                    help='Min bioacoustic papers required to keep a candidate')
    args = ap.parse_args()

    print(f'Zoe.Logos-Graph — Curated Species Discovery v2')
    print(f'Started: {datetime.now().isoformat()}')
    if EMAIL: print(f'OpenAlex email: {EMAIL}')
    else: print('! No OPENALEX_EMAIL set — slower rate limit')
    print()

    existing = load_existing()
    print(f'Existing species in database: {len(existing)}')

    # Filter out species already in DB
    candidates = [(sci, common, group) for sci, common, group in CURATED
                  if sci.lower() not in existing]
    print(f'New candidates to validate: {len(candidates)}\n')

    cache_path = OUT_DIR / 'curated_validation_cache.json'
    cache = {}
    if cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text(encoding='utf-8'))
            print(f'Loaded cache: {len(cache)} validated entries\n')
        except Exception:
            cache = {}

    results = []
    skipped = 0
    for i, (sci, common, group) in enumerate(candidates):
        if i % 10 == 0:
            print(f'[{i}/{len(candidates)}] validating...')
            # Periodic cache flush
            cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2),
                                  encoding='utf-8')

        if sci in cache:
            entry = cache[sci]
        else:
            tax = gbif_taxonomy(sci)
            time.sleep(0.4)
            if not tax:
                print(f'  ✗ GBIF rejected: {sci}')
                cache[sci] = None
                continue
            papers = openalex_papers(sci, per_page=5)
            time.sleep(1.1)
            entry = {
                'sci': sci, 'common': common, 'group': group,
                **tax, 'papers': papers, 'paper_count': len(papers),
            }
            cache[sci] = entry

        if entry is None:
            skipped += 1
            continue
        if entry.get('paper_count', 0) < args.min_papers:
            skipped += 1
            continue
        results.append(entry)

    # Final cache flush
    cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2),
                          encoding='utf-8')

    print(f'\n{"="*60}')
    print(f'Validated: {len(results)} | Skipped: {skipped}')

    # Group breakdown
    from collections import Counter
    grp_count = Counter(r['group'] for r in results)
    for g, n in sorted(grp_count.items(), key=lambda x: -x[1]):
        print(f'  {g:15} {n}')

    # Save JSON
    out_json = OUT_DIR / 'discovered_species.json'
    out_json.write_text(json.dumps(
        {'generated': datetime.now().isoformat(),
         'existing_count': len(existing),
         'candidates': results},
        ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'\nWrote {out_json}')

    # Write HTML review page
    write_review_html(results, OUT_DIR / 'review_species.html')

def write_review_html(candidates, out_path):
    data = json.dumps(candidates, ensure_ascii=False)
    html = '''<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Species Discovery v2 — Review</title>
<style>
:root{--bg:#0e0f11;--panel:#16181c;--text:#e8eaed;--hint:#9aa0a6;
      --amber:#e8a427;--border:#2a2d33;--ok:#00b894;--no:#ff6b6b}
*{box-sizing:border-box;font-family:-apple-system,BlinkMacSystemFont,"DM Sans",sans-serif}
body{background:var(--bg);color:var(--text);margin:0;padding:0;line-height:1.5}
.hdr{position:sticky;top:0;background:var(--panel);border-bottom:1px solid var(--border);
     padding:1rem 1.5rem;z-index:10;display:flex;gap:1rem;align-items:center;flex-wrap:wrap}
h1{margin:0;font-size:18px;font-weight:500}
.stats{color:var(--hint);font-size:13px}
.btn{background:var(--amber);color:#000;border:none;padding:.5rem 1rem;
     border-radius:6px;cursor:pointer;font-weight:600;font-size:13px}
.btn:hover{filter:brightness(1.1)}
.filt{background:var(--bg);color:var(--text);border:1px solid var(--border);
      padding:.4rem .7rem;border-radius:6px;font-size:13px}
.cand{background:var(--panel);border:1px solid var(--border);border-radius:8px;
      padding:1rem 1.2rem;margin:.8rem 1.5rem;display:grid;
      grid-template-columns:auto 1fr;gap:1rem;align-items:start}
.cand.kept{border-color:var(--ok);background:rgba(0,184,148,0.05)}
.chk{width:24px;height:24px;cursor:pointer}
.sci{font-family:'DM Serif Display',serif;font-size:18px;font-style:italic;color:var(--amber)}
.common{color:var(--text);font-size:14px;margin-top:.2rem}
.tax{color:var(--hint);font-size:12px;margin-top:.3rem}
.score{font-size:13px;color:var(--hint);margin-top:.3rem}
.evid{margin-top:.7rem;border-top:1px dashed var(--border);padding-top:.6rem}
.evid-title{font-size:11px;color:var(--hint);text-transform:uppercase;
            letter-spacing:.05em;margin-bottom:.3rem}
.paper{font-size:12px;color:#d4d7de;margin-bottom:.3rem;line-height:1.4}
.paper a{color:var(--amber);text-decoration:none}
.paper a:hover{text-decoration:underline}
.meta{color:var(--hint);font-size:11px;margin-left:.4rem}
.mini{background:transparent;color:var(--hint);border:1px solid var(--border);
      padding:.2rem .5rem;border-radius:4px;font-size:11px;cursor:pointer}
.mini:hover{color:var(--text);border-color:var(--text)}
</style></head>
<body>
<div class="hdr">
  <h1>🔍 Species Discovery v2 — Curated candidates</h1>
  <span class="stats" id="stats"></span>
  <select id="filt-grp" class="filt"><option value="">All groups</option></select>
  <input id="filt-q" class="filt" placeholder="search name..." style="width:160px">
  <button class="mini" onclick="selectAll(true)">Keep all</button>
  <button class="mini" onclick="selectAll(false)">Drop all</button>
  <button class="btn" onclick="exportSelection()">⬇ Export selection</button>
</div>
<div id="list"></div>
<script>
const CANDIDATES = __DATA__;
let state = {};
CANDIDATES.forEach((c, i) => state[i] = true);  // all kept by default

const $ = sel => document.querySelector(sel);
const list = $('#list');

function render() {
  const grp = $('#filt-grp');
  if (grp.children.length === 1) {
    const seen = new Set(CANDIDATES.map(c => c.group));
    [...seen].sort().forEach(g => {
      const o = document.createElement('option');
      o.value = g; o.textContent = g; grp.appendChild(o);
    });
  }
  const fg = grp.value;
  const fq = $('#filt-q').value.toLowerCase();
  list.innerHTML = '';
  let kept = 0;
  CANDIDATES.forEach((c, i) => {
    if (state[i]) kept++;
    if (fg && c.group !== fg) return;
    if (fq && !(c.sci.toLowerCase().includes(fq) || (c.common||'').toLowerCase().includes(fq))) return;
    const el = document.createElement('div');
    el.className = 'cand' + (state[i] ? ' kept' : '');
    el.innerHTML = `
      <input type="checkbox" class="chk" ${state[i] ? 'checked' : ''}
             onchange="toggle(${i})">
      <div>
        <div class="sci">${c.sci}</div>
        <div class="common">${c.common||''}</div>
        <div class="tax">${c.class_||'?'} · ${c.order_||'?'} · ${c.family||'?'} · group: ${c.group}</div>
        <div class="score">${c.paper_count||0} supporting papers</div>
        <div class="evid">
          <div class="evid-title">supporting papers</div>
          ${(c.papers||[]).slice(0,4).map(p =>
            `<div class="paper">${p.doi ?
                `<a href="https://doi.org/${p.doi}" target="_blank">${p.title}</a>` :
                p.title}<span class="meta">${p.year||''} · ${p.cited_by||0} cites · ${p.venue||''}</span></div>`
          ).join('')}
        </div>
      </div>
    `;
    list.appendChild(el);
  });
  $('#stats').textContent = `${kept}/${CANDIDATES.length} kept · target ~66`;
}

function toggle(i){ state[i] = !state[i]; render(); }
function selectAll(v){ Object.keys(state).forEach(k => state[k]=v); render(); }

function exportSelection() {
  const picked = CANDIDATES.filter((c,i)=>state[i]);
  const out = { generated: new Date().toISOString(),
                count: picked.length, species: picked };
  const blob = new Blob([JSON.stringify(out,null,2)], {type:'application/json'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'approved_species.json';
  a.click();
}

$('#filt-grp').addEventListener('change', render);
$('#filt-q').addEventListener('input', render);
render();
</script>
</body></html>
'''.replace('__DATA__', data)
    out_path.write_text(html, encoding='utf-8')
    print(f'Wrote {out_path}')


if __name__ == '__main__':
    main()
    