#!/usr/bin/env python3
"""
atlas.py - Zoe.Logos-Graph

Shared helpers for the update scripts: paths, the paper store, species names,
communication keywords, themes and small HTTP helpers. Stdlib only.

    import atlas
    papers = atlas.load_papers()
    names = atlas.SpeciesNames(species)
    names.find('Song learning in the zebra finch (Taeniopygia guttata)')
"""
import json, re, os, sys, time, html as H
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError

import embedded_db as edb

try:                                   # Windows console and accented names
    sys.stdout.reconfigure(errors='replace')
except Exception:
    pass

PROJ = Path(__file__).parent
SPECIES_HTML = PROJ / 'outputs' / 'species_explorer.html'
PAPERS = PROJ / 'data' / 'papers.json'
SYNONYMS = PROJ / 'data' / 'synonyms.json'
CURATION = PROJ / 'data' / 'curation.csv'
STATE = PROJ / 'data' / 'state.json'
REPORTS = PROJ / 'reports'

ABSTRACT_CHARS = 500      # abstract length shown on the species page
EMAIL = os.environ.get('OPENALEX_EMAIL', '')          # for Crossref (polite pool)
OPENALEX_KEY = os.environ.get('OPENALEX_API_KEY', '')  # free key: openalex.org/settings/api-key
UA = 'ZoeLogosGraph/1.1 (https://github.com/antorr91/Zoe.Logos-Graph)'


def load_species():
    html = SPECIES_HTML.read_text(encoding='utf-8')
    species, eq, end = edb.load(html)
    return html, species, eq, end


def save_species(html, species, eq, end):
    SPECIES_HTML.write_text(edb.write(html, species, eq, end), encoding='utf-8')


# data/papers.json: one record per DOI, species decided by assign_species.py

def norm_doi(d):
    d = (d or '').strip().lower()
    return re.sub(r'^(https?://(dx\.)?doi\.org/|doi:)', '', d)


def load_papers():
    if not PAPERS.exists():
        return {}
    return {p['doi']: p for p in json.loads(PAPERS.read_text(encoding='utf-8'))}


def save_papers(papers):
    # one paper per line -> readable diffs
    rows = sorted(papers.values(), key=lambda p: (-(p.get('year') or 0), p['doi']))
    PAPERS.write_text('[\n' + ',\n'.join(json.dumps(p, ensure_ascii=False, sort_keys=True) for p in rows)
                      + '\n]\n', encoding='utf-8')


def read_json(path, default):
    path = Path(path)
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def write_json(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def today():
    return time.strftime('%Y-%m-%d')


def clean(s):
    if not s:
        return ''
    s = s.replace('&amp;lt;', '<').replace('&amp;gt;', '>')
    s = re.sub(r'<[^>]+>', ' ', s)
    s = H.unescape(s)
    return re.sub(r'\s+', ' ', s).strip()


def shorten(s, n=ABSTRACT_CHARS):
    s = clean(s)
    return s if len(s) <= n else s[:n].rsplit(' ', 1)[0].rstrip('.,;:') + '…'


def norm(s):
    """unicode hyphens and quotes -> plain ones, so names match however they are typed"""
    s = re.sub('[\u2010-\u2015\u2212]', '-', s or '')
    return s.replace('\u2019', "'").replace('\u2018', "'")


def from_inverted(ix):
    """OpenAlex stores abstracts as {word: [positions]}"""
    if not ix:
        return ''
    pos = [(i, w) for w, idx in ix.items() for i in idx]
    return ' '.join(w for _, w in sorted(pos))


# too generic (sea lion, leopard frog...); dog/rat/lion are in synonyms.json plain_names
GENERIC = {'common', 'banded', 'northern', 'southern', 'eastern', 'western', 'greater', 'lesser',
           'little', 'giant', 'human', 'dog', 'cat', 'horse', 'cattle', 'sheep', 'goat', 'pig',
           'chicken', 'mouse', 'rat', 'lion', 'tiger', 'leopard', 'puma', 'orca', 'moose', 'redeye',
           'yellowbelly', 'swordbearer', 'rifleman', 'veery', 'field cricket', 'house mouse',
           'honey bee', 'gray treefrog', 'tree frog', 'treefrog'}


def _variants(name):
    """spelling variants of a common name: plural, grey/gray, tree frog/treefrog, hyphens"""
    n = re.sub(r'\s+', ' ', norm(name).lower()).strip()
    out = {n, n.replace('-', ' ')}
    for a, b in (('grey', 'gray'), ('gray', 'grey'), ('tree frog', 'treefrog'), ('treefrog', 'tree frog')):
        out |= {v.replace(a, b) for v in out}
    if n.startswith('common ') and n.count(' ') >= 2:
        out.add(n[7:])                                # "common bottlenose dolphin" -> "bottlenose dolphin"
    out |= {v + 'es' if v.endswith(('ch', 'sh', 'x')) else v + 's' for v in list(out) if not v.endswith('s')}
    return out


def good_synonym(name):
    """GBIF lists placeholders like "Motacilla spec" or "? palustris": they are not names"""
    parts = name.split()
    return (len(parts) >= 2 and '?' not in name and parts[0][:1].isupper()
            and parts[-1].lower() not in ('spec', 'sp', 'sp.', 'spp', 'spp.', 'indet'))


class SpeciesNames:
    def __init__(self, species, synonyms=None):
        syn = synonyms if synonyms is not None else read_json(SYNONYMS, {})
        extra = {}
        for part in ('manual', 'gbif'):
            for acc, lst in (syn.get(part) or {}).items():
                extra.setdefault(acc, set()).update(n for n in lst if good_synonym(n))
        common_extra = syn.get('common_names') or {}
        self.sci = {s['sci'] for s in species}

        abbrev = {}
        for s in species:
            g, *rest = s['sci'].split()
            if rest:
                k = ('%s. %s' % (g[0], ' '.join(rest))).lower()
                abbrev[k] = abbrev.get(k, 0) + 1

        term, clash, self.common = {}, set(), set()

        def add(t, sci, common=False):
            t = re.sub(r'\s+', ' ', t.lower()).strip()
            if len(t) < 4:
                return
            if t in term and term[t] != sci:
                clash.add(t); return
            term[t] = sci
            if common:
                self.common.add(t)

        for s in species:
            sci = s['sci']
            own = [sci] + sorted(extra.get(sci, ()))
            w = sci.split()
            if len(w) == 3 and ' '.join(w[:2]) not in self.sci:
                own.append(' '.join(w[:2]))      # "Lonchura striata" for Lonchura striata domestica
            for n in own:
                add(n, sci)
                g, *rest = n.split()
                if rest:
                    ab = '%s. %s' % (g[0], ' '.join(rest))
                    if abbrev.get(ab.lower(), 0) <= 1:
                        add(ab, sci)
            for c in re.split(r'[,/;]', s.get('en') or '') + common_extra.get(sci, []):
                c = c.strip()
                if not c or c.lower() in GENERIC:
                    continue
                if ' ' not in c and len(c) < 6:
                    continue
                for v in _variants(c):
                    add(v, sci, common=True)
        for t in clash:
            term.pop(t, None)
        self.term = term

        # also "Papio cynocephalus ursinus", "Gorilla g. gorilla"
        pats = []
        for t in sorted(term, key=len, reverse=True):
            w = t.split()
            if t not in self.common and len(w) == 2 and not w[0].endswith('.'):
                pats.append(r'%s\s+(?:[a-z]+\.?\s+)?%s' % (re.escape(w[0]), re.escape(w[1])))
            else:
                pats.append(re.escape(t).replace(r'\ ', r'[\s-]+'))
        self.rx = re.compile(r'(?<![a-z])(?:%s)(?![a-z])' % '|'.join(pats))

        self.domestic = {w: d for w, d in (syn.get('domestic_forms') or {}).items()
                         if w in self.sci and d['to'] in self.sci}

        # dogs, rats... only if nothing more precise is named
        self.plain = {}
        for sci, lst in (syn.get('plain_names') or {}).items():
            if sci in self.sci:
                for n in lst:
                    self.plain[n.lower()] = sci
        self.plain_rx = re.compile(r'(?<![a-z-])(?:%s)(?![a-z-])' % '|'.join(
            re.escape(n) for n in sorted(self.plain, key=len, reverse=True))) if self.plain else None

    def _who(self, m):
        k = re.sub(r'[\s-]+', ' ', m)
        if k in self.term:
            return self.term[k], k in self.common
        w = k.split()
        k = w[0] + ' ' + w[-1]
        return self.term.get(k), False

    def find(self, text, plain=True):
        """{sci: number of mentions} of the atlas species named in a text.
        When the text gives the scientific name of a species that is not in the atlas,
        English names are not trusted: "spotted dolphins (Stenella attenuata)" is not
        the atlas spotted dolphin"""
        raw = norm(text)
        text = raw.lower()
        found, by_common, sci_named = {}, set(), set()
        for m in self.rx.finditer(text):
            who, is_common = self._who(m.group(0))
            if who and re.match(r'[a-z]\. ', m.group(0)) and self._other_genus(who, raw):
                continue                    # "S. chinensis" after "Streptopelia chinensis" is not Sousa
            if who:
                found[who] = found.get(who, 0) + 1
                (by_common if is_common else sci_named).add(who)
        by_common -= sci_named
        if by_common and self.other_species(raw):
            for w in by_common:
                found.pop(w)
        for wild, d in self.domestic.items():
            if wild in found and re.search(d['if'], text) and not re.search(d['unless'], text):
                found[d['to']] = found.get(d['to'], 0) + found.pop(wild)
        if found or not plain or not self.plain_rx:
            return found
        for m in self.plain_rx.finditer(text):
            before = re.findall(r'[a-z]+', text[max(0, m.start() - 20):m.start()])
            after = re.findall(r'[a-z]+', text[m.end():m.end() + 20])
            if (before and before[-1] in NOT_BEFORE) or (after and after[0] in NOT_AFTER):
                continue
            who = self.plain[m.group(0)]
            found[who] = found.get(who, 0) + 1
        return found

    @staticmethod
    def _other_genus(sci, raw):
        """True if the text writes out another genus with the same initial and not this one"""
        genus = sci.split()[0]
        if genus in raw:
            return False
        return any(g != genus and g[0] == genus[0] and e not in NOT_EPITHET and LATIN_END.search(e)
                   for g, e in BINOMIAL.findall(raw))

    def strip(self, text):
        """text without species names ("song sparrow", "chorus frog" are not about song)"""
        return self.rx.sub(' ', norm(text).lower())

    def other_species(self, text):
        """scientific names in a text that are NOT atlas species, e.g. (Steno bredanensis)"""
        out = []
        for m in BINOMIAL.finditer(norm(text)):
            g, e = m.group(1), m.group(2)
            if m.start(1) == 0 or g in NOT_GENUS or e in NOT_EPITHET:
                continue
            if not (m.group(0)[0] in '(,' or LATIN_END.search(e)):
                continue
            if not self.find('%s %s' % (g, e), plain=False):
                out.append('%s %s' % (g, e))
        return out


BINOMIAL = re.compile(r'(?:^|\(\s*|,\s*|\s)([A-Z][a-z]{2,})\s+([a-z]{4,})\b')
NOT_EPITHET = {'with', 'from', 'under', 'over', 'into', 'than', 'between', 'among', 'during', 'across',
               'and', 'virus', 'spp', 'signatures', 'species', 'calls', 'birds', 'frogs', 'bats'}
LATIN_END = re.compile(r'(?:us|a|um|is|i|ae|es|ns|ix|ax|ex|or|er|os|ys)$')
NOT_GENUS = {'Atlantic', 'Pacific', 'North', 'South', 'East', 'West', 'American', 'European', 'African',
             'Asian', 'Australian', 'Arctic', 'Antarctic', 'Mediterranean', 'Caribbean', 'Indian', 'New',
             'Great', 'Little', 'Common', 'Northern', 'Southern', 'Eastern', 'Western', 'Central', 'The',
             'From', 'With', 'And', 'For', 'How', 'Why', 'What', 'When', 'Does', 'Are', 'Can', 'Not',
             'Japanese', 'Chinese', 'Brazilian', 'Iberian', 'British', 'Darwin', 'Gulf', 'Lake', 'River',
             'Sea', 'Bay', 'Island', 'Islands', 'Mount', 'Cape', 'Puerto', 'San', 'Santa', 'Costa', 'Sri',
             'Hong', 'Middle', 'Late', 'Early', 'Upper', 'Lower', 'Part', 'Aves', 'Mammalia', 'Amphibia',
             'Anura', 'Insecta', 'Orthoptera', 'Hemiptera', 'Primates', 'Chiroptera', 'Cetacea', 'Passeriformes'}


# prairie dogs, mole-rats, tiger moths, rat brain...
NOT_BEFORE = {'maned', 'ethiopian', 'red', 'sea', 'prairie', 'wild', 'mole', 'naked', 'kangaroo',
              'guinea', 'singing', 'mountain', 'snow', 'clouded', 'deer', 'spiny', 'pocket',
              'grasshopper', 'harvest', 'cotton', 'wood', 'water', 'bush', 'raccoon', 'hunting',
              'painted', 'cane', 'pouched', 'dormouse', 'tree', 'feral', 'robot', 'robotic', 'toy', 'model'}
NOT_AFTER = {'spider', 'spiders', 'eel', 'eels', 'frog', 'frogs', 'lemur', 'lemurs', 'bat', 'bats',
             'seal', 'seals', 'shark', 'sharks', 'moth', 'moths', 'snake', 'snakes', 'fish', 'flea',
             'fleas', 'tick', 'ticks', 'salamander', 'salamanders', 'beetle', 'beetles', 'whelk',
             'tailed', 'like', 'cicada', 'cicadas', 'eared', 'lizard', 'lizards', 'egret', 'egrets',
             'tamarin', 'tamarins', 'mosquito', 'mosquitoes', 'fly', 'flies', 'cell', 'cells', 'model',
             'models', 'serum', 'brain', 'brains', 'liver', 'cortex', 'neurons', 'embryo', 'embryos',
             'oocytes', 'genome', 'lice', 'louse'}


CORE = [r'vocal\w*', r'calls?', r'calling', r'songs?', r'singing', r'singers?', r'acoustic\w*',
        r'communicat\w*', r'echolocat\w*', r'ultrasonic\w*', r'infrasonic\w*', r'infrasound\w*',
        r'duet\w*', r'syntax', r'syntactic', r'referential', r'bioacoustic\w*', r'chorus\w*',
        r'whistl\w*', r'clicks?', r'barks?', r'barking', r'roar\w*', r'stridulat\w*', r'chirp\w*',
        r'rumbles?', r'growl\w*', r'repertoires?', r'playbacks?', r'dialects?', r'pheromon\w*',
        r'gestur\w*', r'begging', r'codas?', r'biosonar', r'sonar', r'howl\w*', r'trills?',
        r'purr\w*', r'vibrational', r'tremulat\w*', r'mobbing', r'courtship',
        r'birdsong', r'soundscapes?', r'alarm\w*', r'auditory', r'hearing', r'hoots?', r'grunts?',
        r'screams?', r'squeaks?', r'croak\w*', r'honest signals?', r'speech', r'voices?', r'harmonics?',
        r'flight tones?', r'phonotaxis', r'call types?', r'utteranc\w*', r'scent[- ]?mark\w*',
        r'mating signals?', r'status signals?', r'facial expressions?', r'facial signals?',
        r'emotional contagion', r'(?:courtship|distraction|wing|bowing|threat|sexual) displays?',
        r'(?:honest|sexual|visual|vocal|acoustic|chemical|social|alarm|mating|courtship|warning|'
        r'aposematic|status|aggressive|multimodal|seismic|vibrational|tactile|olfactory|colou?r|'
        r'ornamental|dynamic|male|female) signall?ing']
WEAK = [r'sounds?', r'noise', r'pitch', r'tones?', r'signals?', r'displays?', r'mimic\w*', r'mate choice',
        r'female preferences?', r'hiss\w*', r'audio\w*', r'listen\w*', r'ears?',
        r'signall?ing', r'timbre', r'language']
CORE_RX = re.compile(r'\b(?:%s)\b' % '|'.join(CORE), re.I)
WEAK_RX = re.compile(r'\b(?:%s)\b' % '|'.join(WEAK), re.I)

# notes, reviews of books, anniversaries: not studies
NOT_RESEARCH = re.compile(
    r'^\s*(?:\d+|one hundred|fifty|a hundred) years ago\b|\bbook reviews?\b|^\s*reviews? of\b|'
    r'\bin memoriam\b|\bobituar\w*|^\s*(?:a )?conversation with\b|^\s*birds of\b|'
    r'\bbreeding birds of\b|\btaken in\b|\bnew records?\b|\bcorrigendum\b|\berratum\b|'
    r'\b(?:first )?records? of\b|^\s*notes?\b|\bnatural history of\b|\bpopulation study\b|'
    r'\bpredation (?:on|by)\b|\boccurrence\b|\bsightings?\b|'
    r', by [A-Z][a-z]+ (?:[A-Z]\. )?[A-Z][a-z]+\s*$', re.I)

# off-topic unless the text clearly says otherwise
OFFTOPIC_RX = re.compile(
    r'\b(?:sperm(?! whales?)|semen|milk|mastitis|transcriptom\w*|proteom\w*|genom\w*|gene flow|'
    r'phylogeograph\w*|microsatellite\w*|disease\w*|infection\w*|lyme|vaccin\w*|virus\w*|viral|'
    r'bacteri\w*|parasit\w*|helminth\w*|carcass\w*|meat|dairy|pregnan\w*|placent\w*|tumou?r\w*|'
    r'cancer|immun\w*|pathogen\w*|toxic\w*|pesticide\w*|diet|seed dispers\w*|feather\w*|plumage|'
    r'moult\w*|molt\w*|population dynamics|abundance|point[- ]counts?|harvest\w*|hunting|road\w*|'
    r'wind farm\w*|hearing loss|acoustic trauma|noise[- ]induced|ototox\w*|cochlear implants?|'
    r'hearing[- ]impaired|densit(?:y|ies)|population (?:size|trends?|estimates?)|home ranges?|'
    r'spring movements?)\b', re.I)

# "cell signalling", "intercellular communication" are not animal communication
CELLULAR = re.compile(
    r'\b(?:cell|cellular|intercellular|extracellular|synaptic|molecular|hormonal|immune|neuronal|'
    r'paracrine|endocrine|calcium|insulin|receptor)\s+(?:signall?ing|communication|signals?)\b|'
    r'\bsignall?ing (?:pathways?|molecules?|cascades?|proteins?)\b|'
    r'\b(?:brief|short|rapid|personal) communications?\b|'          # journal sections
    r'\b(?:science|risk|public|stakeholder|health|media) communication\b|'
    r'\bcalls? for\b|\bso[- ]called\b|\balarm clocks?\b|'
    r'\b(?:ultrasonic|acoustic) (?:sensors?|devices?|deterrents?|telemetry|tags?|tagging|transmitters?|receivers?|'
    r'tracking|cleaning|treatment)\b', re.I)


def comm_terms(text):
    t = CELLULAR.sub(' ', text or '')
    core = {m.group(0).lower().rstrip('s') for m in CORE_RX.finditer(t)}
    weak = {m.group(0).lower().rstrip('s') for m in WEAK_RX.finditer(t)}
    return core, weak


def about_communication(title, abstract, full):
    """True / False, or None when only a short abstract is known and it is not clear"""
    tc, tw = comm_terms(title)
    ac, aw = comm_terms(abstract)
    off = OFFTOPIC_RX.search(title or '')
    if tc and not off:
        return True
    core, weak = tc | ac, tw | aw
    need = 3 if off else 2
    if len(core) >= need or (len(core) >= need - 1 and len(weak) >= 2):
        return True
    return False if full else None


THEME_KW = {
    'vocal_learning': [r'vocal learning', r'vocal production learning', r'song learning', r'vocal imitation',
                       r'vocal plasticity', r'vocal convergence', r'babbling', r'learned vocal', r'song tutor'],
    'referential': [r'referential', r'food[- ]associated call', r'food calls?', r'semantic'],
    'syntax': [r'syntax', r'syntactic', r'compositional', r'combinatorial', r'call combination',
               r'word[- ]order', r'call sequence'],
    'individual_recognition': [r'individual recognition', r'signature whistle', r'individual identity',
                               r'individual signature', r'caller identity', r'vocal signature',
                               r'individually distinct', r'voice recognition', r'vocal individuality'],
    'cultural_transmission': [r'cultural transmission', r'cultural evolution', r'vocal tradition', r'social learning'],
    'turn_taking': [r'turn[- ]taking', r'duet', r'antiphonal', r'counter[- ]singing', r'vocal exchange'],
    'honest_signalling': [r'honest signal', r'size exaggeration', r'formant', r'male quality', r'mate quality',
                          r'condition[- ]depend', r'mate choice', r'female preference'],
    'echolocation': [r'echolocat', r'biosonar', r'\bsonar\b', r'click train'],
    'infrasound': [r'infrasound', r'infrasonic'],
    'dialects': [r'dialect', r'geographic variation', r'regional variation'],
    'emotion': [r'\bemotion', r'affective', r'\barousal', r'\bvalence', r'distress call', r'emotional state'],
    'multimodal': [r'multimodal', r'multi[- ]modal', r'visual display', r'gestur', r'cross[- ]modal',
                   r'audio[- ]visual', r'vibrational'],
    'deception': [r'decept', r'vocal mimicry', r'deceiv', r'false alarm', r'brood parasit'],
    'parent_offspring': [r'mother[- ]offspring', r'parent[- ]offspring', r'mother[- ]pup', r'begging call',
                         r'isolation call', r'mother[- ]infant', r'offspring recognition'],
    'alarm': [r'alarm call', r'anti[- ]?predator', r'\bmobbing\b', r'predator[- ]specific', r'warning call'],
    'cooperation': [r'cooperat', r'recruitment call', r'quorum', r'food[- ]sharing', r'group coordination',
                    r'group cohesion', r'flock cohesion', r'collective movement'],
}
THEME_RX = {t: re.compile('|'.join(ps), re.I) for t, ps in THEME_KW.items()}


# methods papers on animal signals: machine learning, signal processing, automatic detection, datasets
METHODS_RX = re.compile(
    r'deep learning|machine learning|neural network|convolutional|\bCNNs?\b|classifier|random forest|'
    r'support vector|automat\w* (?:detection|classification|recogni\w*|identification|annotation)|'
    r'passive acoustic monitoring|\bMFCCs?\b|signal processing|acoustic indices|unsupervised|'
    r'clustering algorithm|BirdNET|hidden markov|dynamic time warping|feature extraction|'
    r'sound event detection|transfer learning|annotated dataset|public dataset|open dataset|'
    r'spectro-?temporal modulation|self-supervised|embedding', re.I)


def themes_of(text):
    return sorted(t for t, rx in THEME_RX.items() if rx.search(text or ''))


def get_json(url, tries=4, timeout=40, missing_ok=False):
    """parsed JSON, or None if it failed; with missing_ok a 404 gives {} (= the service has nothing)"""
    for i in range(tries):
        try:
            with urlopen(Request(url, headers={'User-Agent': UA, 'Accept': 'application/json'}),
                         timeout=timeout) as r:
                return json.loads(r.read().decode('utf-8'))
        except HTTPError as e:
            if e.code in (404, 410) and missing_ok:
                return {}
            if e.code in (400, 401, 403, 404, 410):
                return None
        except Exception:
            pass
        time.sleep(2 ** i + 1)
    print('    giving up on', url[:110])
    return None


class OpenAlexLimit(Exception):
    pass


def openalex(path, **params):
    """None if the request is wrong; OpenAlexLimit when the daily budget is used up
    (no key: 100 searches a day, free key: 1000 searches and 10000 lists a day)"""
    if OPENALEX_KEY:
        params['api_key'] = OPENALEX_KEY
    url = 'https://api.openalex.org/%s?%s' % (path, urlencode(params))
    for i in range(4):
        try:
            with urlopen(Request(url, headers={'User-Agent': UA}), timeout=60) as r:
                return json.loads(r.read().decode('utf-8'))
        except HTTPError as e:
            if e.code == 429:
                if i == 3:
                    raise OpenAlexLimit(e.read().decode('utf-8', 'replace')[:200])
                time.sleep(3 * (i + 1))
                continue
            if e.code in (400, 401, 403, 404):
                print('    OpenAlex %d: %s' % (e.code, e.read().decode('utf-8', 'replace')[:200]))
                return None
        except Exception:
            pass
        time.sleep(2 ** i + 1)
    print('    giving up on', url.split('api_key')[0][:110])
    return None
