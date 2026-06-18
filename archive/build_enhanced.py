#!/usr/bin/env python3
"""
build_enhanced.py — Generates all enhanced output HTML files for Zoe.Logos-Graph v1.0
Run from project root: python build_enhanced.py
Outputs go to outputs/
"""
import json, re, os, base64
from pathlib import Path

PROJ = Path(__file__).parent
OUT = PROJ / 'outputs'
OUT.mkdir(exist_ok=True)

# ── 1. LOAD & ENRICH DATA ──────────────────────────────────────────────────
print("Loading existing species data...")
with open(OUT / 'species_explorer.html', 'r', encoding='utf-8') as f:
    src = f.read()
m = re.search(r'const EMBEDDED_DB = (\[.*?\]);\n', src, re.DOTALL)
SPECIES = json.loads(m.group(1))
print(f"  Loaded {len(SPECIES)} species")

# ── THEMES ──────────────────────────────────────────────────────────────────
THEMES = [
    {"id":"vocal_learning","label":"Vocal Learning","desc":"Acquisition of vocalisations through auditory experience and sensorimotor feedback","color":"#4ecdc4"},
    {"id":"referential","label":"Referential Communication","desc":"Signals encoding information about external objects, events, or predator type","color":"#ff6b6b"},
    {"id":"syntax","label":"Syntax & Combinatoriality","desc":"Rule-governed combination or sequencing of signal elements","color":"#ffd93d"},
    {"id":"individual_recognition","label":"Individual Recognition","desc":"Identification of conspecifics via acoustic signatures","color":"#6c5ce7"},
    {"id":"cultural_transmission","label":"Cultural Transmission","desc":"Social transfer of vocal traditions across generations","color":"#a29bfe"},
    {"id":"turn_taking","label":"Turn-taking & Duetting","desc":"Temporally coordinated exchange of signals between individuals","color":"#fd79a8"},
    {"id":"honest_signalling","label":"Honest Signalling","desc":"Signals reliably encoding sender quality, condition, or motivation","color":"#00b894"},
    {"id":"echolocation","label":"Echolocation / Biosonar","desc":"Active acoustic sensing for navigation and prey detection","color":"#0984e3"},
    {"id":"infrasound","label":"Infrasound Communication","desc":"Communication using frequencies below human hearing","color":"#e17055"},
    {"id":"dialects","label":"Vocal Dialects","desc":"Geographic or group-specific variation in vocal structure","color":"#fdcb6e"},
    {"id":"emotion","label":"Emotional Signalling","desc":"Acoustic encoding of arousal, valence, and affective states","color":"#e84393"},
    {"id":"multimodal","label":"Multimodal Communication","desc":"Integration of acoustic signals with visual, chemical, or tactile channels","color":"#00cec9"},
    {"id":"deception","label":"Deceptive Signalling","desc":"Production of misleading signals for competitive advantage","color":"#636e72"},
    {"id":"parent_offspring","label":"Parent-Offspring Communication","desc":"Acoustic exchanges between parents and young, including prenatal","color":"#fab1a0"},
    {"id":"alarm","label":"Alarm & Predator Response","desc":"Warning signals encoding predator type, urgency, or escape strategy","color":"#ff7675"},
    {"id":"cooperation","label":"Cooperative Communication","desc":"Signals coordinating group activities: foraging, hunting, territory defence","color":"#74b9ff"},
]

# Theme + acoustic mapping for each species
ENRICHMENT = {
    "Taeniopygia guttata":{"themes":["vocal_learning","cultural_transmission","honest_signalling"],"freq":"0.5–8 kHz","learning":"closed-ended learner","semiotic":"index"},
    "Gallus gallus domesticus":{"themes":["referential","alarm","parent_offspring","deception"],"freq":"0.4–6 kHz","learning":"innate","semiotic":"index"},
    "Aegithalos caudatus":{"themes":["individual_recognition","cooperation","alarm"],"freq":"4–10 kHz","learning":"innate","semiotic":"index"},
    "Parus minor":{"themes":["syntax","referential","alarm"],"freq":"2–10 kHz","learning":"open-ended","semiotic":"symbol_precursor"},
    "Parus major":{"themes":["vocal_learning","honest_signalling","alarm","dialects"],"freq":"2–9 kHz","learning":"closed-ended","semiotic":"index"},
    "Corvus corax":{"themes":["referential","individual_recognition","cooperation","multimodal"],"freq":"0.3–6 kHz","learning":"open-ended","semiotic":"index"},
    "Corvus corone":{"themes":["alarm","cooperation"],"freq":"0.5–5 kHz","learning":"limited","semiotic":"index"},
    "Pica pica":{"themes":["alarm","cooperation"],"freq":"1–7 kHz","learning":"limited","semiotic":"index"},
    "Garrulus glandarius":{"themes":["alarm","referential"],"freq":"1–8 kHz","learning":"open-ended","semiotic":"index"},
    "Sturnus vulgaris":{"themes":["vocal_learning","syntax","cultural_transmission"],"freq":"1–8 kHz","learning":"open-ended","semiotic":"index"},
    "Turdus merula":{"themes":["vocal_learning","dialects","alarm","honest_signalling"],"freq":"1–8 kHz","learning":"closed-ended","semiotic":"index"},
    "Turdus philomelos":{"themes":["vocal_learning","honest_signalling"],"freq":"1–9 kHz","learning":"closed-ended","semiotic":"index"},
    "Erithacus rubecula":{"themes":["honest_signalling","alarm"],"freq":"2–10 kHz","learning":"closed-ended","semiotic":"index"},
    "Luscinia megarhynchos":{"themes":["vocal_learning","honest_signalling"],"freq":"1–10 kHz","learning":"closed-ended","semiotic":"index"},
    "Fringilla coelebs":{"themes":["vocal_learning","dialects","cultural_transmission"],"freq":"2–8 kHz","learning":"closed-ended","semiotic":"index"},
    "Serinus canaria":{"themes":["vocal_learning","cultural_transmission"],"freq":"1–8 kHz","learning":"open-ended","semiotic":"index"},
    "Carduelis carduelis":{"themes":["cooperation","individual_recognition"],"freq":"2–9 kHz","learning":"closed-ended","semiotic":"index"},
    "Passer domesticus":{"themes":["dialects","cooperation"],"freq":"2–7 kHz","learning":"limited","semiotic":"index"},
    "Alauda arvensis":{"themes":["honest_signalling","multimodal"],"freq":"1–9 kHz","learning":"closed-ended","semiotic":"index"},
    "Sylvia atricapilla":{"themes":["vocal_learning","dialects"],"freq":"2–8 kHz","learning":"closed-ended","semiotic":"index"},
    "Melospiza melodia":{"themes":["vocal_learning","dialects","honest_signalling"],"freq":"1–9 kHz","learning":"closed-ended","semiotic":"index"},
    "Zonotrichia leucophrys":{"themes":["vocal_learning","dialects","cultural_transmission"],"freq":"2–8 kHz","learning":"closed-ended","semiotic":"index"},
    "Mimus polyglottos":{"themes":["vocal_learning","honest_signalling"],"freq":"0.5–10 kHz","learning":"open-ended","semiotic":"index"},
    "Acrocephalus scirpaceus":{"themes":["alarm","deception","parent_offspring"],"freq":"2–8 kHz","learning":"closed-ended","semiotic":"index"},
    "Lonchura striata domestica":{"themes":["vocal_learning","syntax"],"freq":"1–8 kHz","learning":"closed-ended","semiotic":"index"},
    "Hirundo rustica":{"themes":["honest_signalling","alarm"],"freq":"1–8 kHz","learning":"limited","semiotic":"index"},
    "Regulus regulus":{"themes":["cooperation","individual_recognition"],"freq":"5–12 kHz","learning":"closed-ended","semiotic":"index"},
    "Sitta europaea":{"themes":["honest_signalling","dialects"],"freq":"2–8 kHz","learning":"limited","semiotic":"index"},
    "Phylloscopus trochilus":{"themes":["dialects","vocal_learning"],"freq":"2–8 kHz","learning":"closed-ended","semiotic":"index"},
    "Phylloscopus collybita":{"themes":["dialects"],"freq":"3–7 kHz","learning":"closed-ended","semiotic":"index"},
    "Cinclus cinclus":{"themes":["honest_signalling"],"freq":"2–9 kHz","learning":"closed-ended","semiotic":"index"},
    "Geospiza fortis":{"themes":["honest_signalling","multimodal"],"freq":"2–6 kHz","learning":"closed-ended","semiotic":"index"},
    "Melopsittacus undulatus":{"themes":["vocal_learning","individual_recognition"],"freq":"1–5 kHz","learning":"open-ended","semiotic":"index"},
    "Psittacus erithacus":{"themes":["vocal_learning","referential","cultural_transmission"],"freq":"0.5–6 kHz","learning":"open-ended","semiotic":"symbol_precursor"},
    "Ara macao":{"themes":["vocal_learning","individual_recognition"],"freq":"0.5–5 kHz","learning":"open-ended","semiotic":"index"},
    "Cuculus canorus":{"themes":["deception","parent_offspring"],"freq":"0.5–4 kHz","learning":"innate","semiotic":"index"},
    "Columba livia":{"themes":["honest_signalling"],"freq":"0.3–3 kHz","learning":"innate","semiotic":"index"},
    "Coturnix japonica":{"themes":["parent_offspring","honest_signalling"],"freq":"1–5 kHz","learning":"innate","semiotic":"index"},
    "Bubo bubo":{"themes":["honest_signalling","individual_recognition"],"freq":"0.3–2 kHz","learning":"innate","semiotic":"index"},
    "Tyto alba":{"themes":["individual_recognition","honest_signalling"],"freq":"1–10 kHz","learning":"innate","semiotic":"index"},
    "Apus apus":{"themes":["cooperation","multimodal"],"freq":"3–9 kHz","learning":"limited","semiotic":"index"},
    "Tursiops truncatus":{"themes":["vocal_learning","referential","individual_recognition","echolocation","cooperation"],"freq":"0.2–150 kHz","learning":"open-ended","semiotic":"symbol_precursor"},
    "Megaptera novaeangliae":{"themes":["vocal_learning","cultural_transmission","dialects"],"freq":"0.02–10 kHz","learning":"open-ended","semiotic":"icon"},
    "Physeter macrocephalus":{"themes":["cultural_transmission","individual_recognition","echolocation","dialects","cooperation"],"freq":"0.5–30 kHz","learning":"social","semiotic":"symbol_precursor"},
    "Orcinus orca":{"themes":["vocal_learning","cultural_transmission","dialects","cooperation","echolocation"],"freq":"0.5–80 kHz","learning":"social","semiotic":"index"},
    "Globicephala melas":{"themes":["cooperation","cultural_transmission"],"freq":"0.5–20 kHz","learning":"social","semiotic":"index"},
    "Phocoena phocoena":{"themes":["echolocation"],"freq":"110–150 kHz","learning":"innate","semiotic":"index"},
    "Chlorocebus pygerythrus":{"themes":["referential","alarm"],"freq":"0.5–8 kHz","learning":"social","semiotic":"symbol_precursor"},
    "Callithrix jacchus":{"themes":["vocal_learning","turn_taking","individual_recognition"],"freq":"2–12 kHz","learning":"social","semiotic":"index"},
    "Pan troglodytes":{"themes":["referential","cultural_transmission","cooperation","emotion","multimodal"],"freq":"0.1–8 kHz","learning":"social","semiotic":"index"},
    "Pan paniscus":{"themes":["emotion","cooperation","referential"],"freq":"0.2–8 kHz","learning":"social","semiotic":"index"},
    "Gorilla gorilla":{"themes":["multimodal","honest_signalling","emotion"],"freq":"0.1–5 kHz","learning":"limited","semiotic":"index"},
    "Macaca mulatta":{"themes":["individual_recognition","cooperation","emotion"],"freq":"0.3–8 kHz","learning":"limited","semiotic":"index"},
    "Hylobates lar":{"themes":["turn_taking","honest_signalling","cooperation"],"freq":"0.3–4 kHz","learning":"social","semiotic":"index"},
    "Lemur catta":{"themes":["referential","alarm","multimodal"],"freq":"0.3–10 kHz","learning":"innate","semiotic":"index"},
    "Felis catus":{"themes":["emotion","individual_recognition","multimodal"],"freq":"0.05–12 kHz","learning":"limited","semiotic":"index"},
    "Canis lupus familiaris":{"themes":["emotion","individual_recognition","referential"],"freq":"0.08–12 kHz","learning":"limited","semiotic":"index"},
    "Canis lupus":{"themes":["individual_recognition","cooperation","dialects"],"freq":"0.15–12 kHz","learning":"social","semiotic":"index"},
    "Crocuta crocuta":{"themes":["individual_recognition","cooperation","honest_signalling"],"freq":"0.1–6 kHz","learning":"limited","semiotic":"index"},
    "Equus caballus":{"themes":["individual_recognition","emotion"],"freq":"0.1–8 kHz","learning":"limited","semiotic":"index"},
    "Sus scrofa domesticus":{"themes":["emotion","honest_signalling"],"freq":"0.05–10 kHz","learning":"limited","semiotic":"index"},
    "Bos taurus":{"themes":["emotion","individual_recognition","parent_offspring"],"freq":"0.05–5 kHz","learning":"limited","semiotic":"index"},
    "Ovis aries":{"themes":["individual_recognition","parent_offspring"],"freq":"0.1–5 kHz","learning":"limited","semiotic":"index"},
    "Capra hircus":{"themes":["emotion","parent_offspring"],"freq":"0.1–6 kHz","learning":"limited","semiotic":"index"},
    "Cervus elaphus":{"themes":["honest_signalling"],"freq":"0.08–3 kHz","learning":"innate","semiotic":"index"},
    "Rangifer tarandus":{"themes":["honest_signalling"],"freq":"0.1–3 kHz","learning":"innate","semiotic":"index"},
    "Phascolarctos cinereus":{"themes":["honest_signalling","infrasound"],"freq":"0.03–3 kHz","learning":"innate","semiotic":"index"},
    "Eptesicus fuscus":{"themes":["echolocation"],"freq":"25–55 kHz","learning":"innate","semiotic":"index"},
    "Tadarida brasiliensis":{"themes":["echolocation","honest_signalling"],"freq":"20–50 kHz","learning":"limited","semiotic":"index"},
    "Pteropus vampyrus":{"themes":["cooperation","individual_recognition"],"freq":"5–30 kHz","learning":"social","semiotic":"index"},
    "Mus musculus":{"themes":["vocal_learning","honest_signalling","parent_offspring"],"freq":"30–110 kHz","learning":"limited","semiotic":"index"},
    "Rattus norvegicus":{"themes":["emotion","parent_offspring"],"freq":"22–80 kHz","learning":"limited","semiotic":"index"},
    "Spermophilus beecheyi":{"themes":["referential","alarm"],"freq":"2–10 kHz","learning":"social","semiotic":"index"},
    "Elephas maximus":{"themes":["infrasound","individual_recognition","cooperation"],"freq":"0.01–10 kHz","learning":"social","semiotic":"index"},
    "Loxodonta africana":{"themes":["infrasound","referential","individual_recognition","cooperation","cultural_transmission","vocal_learning"],"freq":"0.005–10 kHz","learning":"social","semiotic":"symbol_precursor"},
    "Mustela putorius furo":{"themes":["emotion"],"freq":"1–8 kHz","learning":"limited","semiotic":"index"},
    "Engystomops pustulosus":{"themes":["honest_signalling","multimodal"],"freq":"0.3–7 kHz","learning":"innate","semiotic":"index"},
    "Rana temporaria":{"themes":["honest_signalling"],"freq":"0.5–3 kHz","learning":"innate","semiotic":"index"},
    "Hyla chrysoscelis":{"themes":["honest_signalling"],"freq":"1–5 kHz","learning":"innate","semiotic":"index"},
    "Hyla arborea":{"themes":["honest_signalling","turn_taking"],"freq":"1–5 kHz","learning":"innate","semiotic":"index"},
    "Lithobates catesbeianus":{"themes":["honest_signalling"],"freq":"0.1–2 kHz","learning":"innate","semiotic":"index"},
    "Bufo bufo":{"themes":["honest_signalling"],"freq":"0.5–3 kHz","learning":"innate","semiotic":"index"},
    "Dendrobates auratus":{"themes":["multimodal","honest_signalling"],"freq":"3–7 kHz","learning":"innate","semiotic":"index"},
    "Xenopus laevis":{"themes":["honest_signalling"],"freq":"1–4 kHz","learning":"innate","semiotic":"index"},
    "Bombina variegata":{"themes":["honest_signalling"],"freq":"0.5–3 kHz","learning":"innate","semiotic":"index"},
    "Anolis carolinensis":{"themes":["multimodal","honest_signalling"],"freq":"—","learning":"innate","semiotic":"index"},
    "Crocodylus niloticus":{"themes":["infrasound","parent_offspring"],"freq":"0.02–2 kHz","learning":"innate","semiotic":"index"},
    "Iguana iguana":{"themes":["multimodal","honest_signalling"],"freq":"—","learning":"innate","semiotic":"index"},
    "Drosophila melanogaster":{"themes":["honest_signalling","multimodal"],"freq":"0.1–0.5 kHz","learning":"innate","semiotic":"index"},
    "Gryllus bimaculatus":{"themes":["honest_signalling","turn_taking"],"freq":"3–8 kHz","learning":"innate","semiotic":"index"},
    "Acheta domesticus":{"themes":["honest_signalling"],"freq":"3–6 kHz","learning":"innate","semiotic":"index"},
    "Apis mellifera":{"themes":["referential","cooperation"],"freq":"0.1–1 kHz","learning":"social","semiotic":"symbol_precursor"},
    "Galleria mellonella":{"themes":["honest_signalling"],"freq":"30–100 kHz","learning":"innate","semiotic":"index"},
    "Teleogryllus oceanicus":{"themes":["honest_signalling","alarm"],"freq":"3–8 kHz","learning":"innate","semiotic":"index"},
    "Schistocerca gregaria":{"themes":["cooperation","honest_signalling"],"freq":"2–10 kHz","learning":"innate","semiotic":"index"},
    "Danio rerio":{"themes":["multimodal"],"freq":"0.1–1.5 kHz","learning":"innate","semiotic":"index"},
    "Porichthys notatus":{"themes":["honest_signalling"],"freq":"0.05–0.5 kHz","learning":"innate","semiotic":"index"},
    "Gadus morhua":{"themes":["honest_signalling"],"freq":"0.05–0.5 kHz","learning":"innate","semiotic":"index"},
    "Amphiprion ocellaris":{"themes":["honest_signalling"],"freq":"0.1–1 kHz","learning":"innate","semiotic":"index"},
    "Oreochromis niloticus":{"themes":["honest_signalling"],"freq":"0.05–1 kHz","learning":"innate","semiotic":"index"},
    "Sebastes mystinus":{"themes":["honest_signalling"],"freq":"0.05–0.5 kHz","learning":"innate","semiotic":"index"},
    "Pollachius virens":{"themes":["honest_signalling"],"freq":"0.05–0.3 kHz","learning":"innate","semiotic":"index"},
}

# New species to add
NEW_SPECIES = [
    {"sci":"Homo sapiens","en":"human","it":"essere umano","es":"humano","fr":"humain","de":"mensch","class_":"Mammalia","order_":"Primates","family":"Hominidae","wiki":"Human","xc":"","voc":["speech","song","whistle"],"ctx":["all contexts"],"fn":["all communicative functions"],"papers":[{"title":"The faculty of language: what is it, who has it, and how did it evolve?","year":2002,"doi":"10.1126/science.298.5598.1569","journal":"Science","url":"https://doi.org/10.1126/science.298.5598.1569","outcome":"Proposes recursion as the only uniquely human component of the language faculty.","open_access":1},{"title":"Natural language and natural selection","year":1990,"doi":"10.1017/S0140525X00081061","journal":"Behavioral and Brain Sciences","url":"https://doi.org/10.1017/S0140525X00081061","outcome":"Argues language is a biological adaptation shaped by natural selection.","open_access":1}]},
    {"sci":"Indri indri","en":"indri","it":"indri","es":"indri","fr":"indri","de":"indri","class_":"Mammalia","order_":"Primates","family":"Indriidae","wiki":"Indri","xc":"","voc":["song","howl"],"ctx":["territorial defence","social bonding"],"fn":["territory signalling","group coordination"],"papers":[{"title":"Categorical rhythms in indri songs","year":2021,"doi":"10.1016/j.cub.2021.01.058","journal":"Current Biology","url":"https://doi.org/10.1016/j.cub.2021.01.058","outcome":"Indri songs exhibit categorical rhythm ratios paralleling human musical universals.","open_access":1}]},
    {"sci":"Heterocephalus glaber","en":"naked mole-rat","it":"eterocefalo glabro","es":"rata topo desnuda","fr":"rat-taupe nu","de":"nacktmull","class_":"Mammalia","order_":"Rodentia","family":"Bathyergidae","wiki":"Naked_mole-rat","xc":"","voc":["chirp","call"],"ctx":["colony communication"],"fn":["group identity","individual recognition"],"papers":[{"title":"Vocal dialects in naked mole-rat colonies","year":2021,"doi":"10.1126/science.abc6588","journal":"Science","url":"https://doi.org/10.1126/science.abc6588","outcome":"Each colony has a distinct vocal dialect culturally inherited and enforced by the queen.","open_access":1}]},
    {"sci":"Scotinomys teguina","en":"Alston's singing mouse","it":"topo cantore","es":"ratón cantor","fr":"souris chanteuse","de":"singende maus","class_":"Mammalia","order_":"Rodentia","family":"Cricetidae","wiki":"Alston's_singing_mouse","xc":"","voc":["song","call"],"ctx":["territorial defence","mate attraction"],"fn":["territory signalling","mate attraction"],"papers":[{"title":"Motor cortex mediates vocal turn-taking in singing mice","year":2019,"doi":"10.1126/science.aau9480","journal":"Science","url":"https://doi.org/10.1126/science.aau9480","outcome":"Singing mice engage in rapid acoustic counter-singing; motor cortex controls turn-taking.","open_access":1}]},
    {"sci":"Saccopteryx bilineata","en":"greater sac-winged bat","it":"pipistrello saccato","es":"murciélago de sacos","fr":"saccoptère","de":"sackflügelfledermaus","class_":"Mammalia","order_":"Chiroptera","family":"Emballonuridae","wiki":"Greater_sac-winged_bat","xc":"","voc":["song","babbling"],"ctx":["courtship","pup development"],"fn":["mate attraction","vocal development"],"papers":[{"title":"Babbling in sac-winged bat pups","year":2006,"doi":"10.1007/s00114-006-0127-9","journal":"Naturwissenschaften","url":"https://doi.org/10.1007/s00114-006-0127-9","outcome":"Pups produce babbling sequences resembling adult songs — paralleling human babbling.","open_access":1}]},
    {"sci":"Rousettus aegyptiacus","en":"Egyptian fruit bat","it":"pipistrello egiziano","es":"murciélago frugívoro","fr":"roussette d'Égypte","de":"nilflughund","class_":"Mammalia","order_":"Chiroptera","family":"Pteropodidae","wiki":"Egyptian_fruit_bat","xc":"","voc":["call","screech"],"ctx":["social disputes","roosting"],"fn":["individual identity","aggression"],"papers":[{"title":"Bat calls encode social context and identity","year":2016,"doi":"10.1038/srep39293","journal":"Scientific Reports","url":"https://doi.org/10.1038/srep39293","outcome":"Egyptian fruit bat calls encode caller identity, addressee, and social context.","open_access":1}]},
    {"sci":"Suricata suricatta","en":"meerkat","it":"suricato","es":"suricata","fr":"suricate","de":"erdmännchen","class_":"Mammalia","order_":"Carnivora","family":"Herpestidae","wiki":"Meerkat","xc":"","voc":["alarm call","contact call"],"ctx":["predator response","foraging"],"fn":["predator warning","group coordination"],"papers":[{"title":"Functionally referential alarm calls in meerkats","year":2001,"doi":"10.1098/rspb.2001.1924","journal":"Proc Royal Soc B","url":"https://doi.org/10.1098/rspb.2001.1924","outcome":"Meerkat alarm calls encode both predator type and urgency level.","open_access":1}]},
    {"sci":"Callicebus nigrifrons","en":"black-fronted titi monkey","it":"titi dalla fronte nera","es":"tití de frente negra","fr":"titi à front noir","de":"schwarzstirniger springaffe","class_":"Mammalia","order_":"Primates","family":"Pitheciidae","wiki":"Black-fronted_titi","xc":"","voc":["alarm call"],"ctx":["predator response","territory"],"fn":["alarm","territory signalling"],"papers":[{"title":"Titi monkeys combine alarm calls to encode predator type and location","year":2013,"doi":"10.1098/rsbl.2013.0535","journal":"Biology Letters","url":"https://doi.org/10.1098/rsbl.2013.0535","outcome":"Titi monkeys combine A and B calls in rule-governed sequences encoding both predator type and location.","open_access":1}]},
    {"sci":"Balaenoptera musculus","en":"blue whale","it":"balenottera azzurra","es":"ballena azul","fr":"baleine bleue","de":"blauwal","class_":"Mammalia","order_":"Cetacea","family":"Balaenopteridae","wiki":"Blue_whale","xc":"","voc":["infrasonic call","song"],"ctx":["long-distance communication"],"fn":["mate attraction","contact maintenance"],"papers":[{"title":"Worldwide decline in tonal frequencies of blue whale songs","year":2009,"doi":"10.3354/esr00217","journal":"Endangered Species Research","url":"https://doi.org/10.3354/esr00217","outcome":"Blue whale song frequencies have declined worldwide over decades.","open_access":1}]},
    {"sci":"Delphinapterus leucas","en":"beluga whale","it":"beluga","es":"beluga","fr":"béluga","de":"belugawal","class_":"Mammalia","order_":"Cetacea","family":"Monodontidae","wiki":"Beluga_whale","xc":"","voc":["whistle","click","call"],"ctx":["social communication","echolocation"],"fn":["individual identity","navigation"],"papers":[{"title":"Vocal repertoire of belugas","year":2018,"doi":"10.1121/1.5038256","journal":"J Acoustical Society of America","url":"https://doi.org/10.1121/1.5038256","outcome":"Belugas produce >30 call types with individual-specific repertoire profiles.","open_access":1}]},
    {"sci":"Halichoerus grypus","en":"grey seal","it":"foca grigia","es":"foca gris","fr":"phoque gris","de":"kegelrobbe","class_":"Mammalia","order_":"Carnivora","family":"Phocidae","wiki":"Grey_seal","xc":"","voc":["call"],"ctx":["mate attraction"],"fn":["mate attraction","individual identity"],"papers":[{"title":"Grey seals copy human speech formants","year":2019,"doi":"10.1016/j.cub.2019.05.071","journal":"Current Biology","url":"https://doi.org/10.1016/j.cub.2019.05.071","outcome":"Grey seals reproduce speech formant patterns, confirming vocal production learning.","open_access":1}]},
    {"sci":"Mirounga angustirostris","en":"northern elephant seal","it":"elefante marino","es":"elefante marino del norte","fr":"éléphant de mer","de":"see-elefant","class_":"Mammalia","order_":"Carnivora","family":"Phocidae","wiki":"Northern_elephant_seal","xc":"","voc":["call","pulse"],"ctx":["territorial defence"],"fn":["individual identity","aggression"],"papers":[{"title":"Individual recognition via vocal signatures in elephant seals","year":2017,"doi":"10.1016/j.cub.2017.08.055","journal":"Current Biology","url":"https://doi.org/10.1016/j.cub.2017.08.055","outcome":"Males recognise rivals by vocal rhythm patterns.","open_access":1}]},
    {"sci":"Alouatta palliata","en":"mantled howler monkey","it":"aluatta dal mantello","es":"mono aullador","fr":"hurleur à manteau","de":"mantel-brüllaffe","class_":"Mammalia","order_":"Primates","family":"Atelidae","wiki":"Mantled_howler","xc":"","voc":["howl"],"ctx":["territorial defence"],"fn":["territory signalling"],"papers":[{"title":"Howling and body size in howler monkeys","year":2015,"doi":"10.1016/j.cub.2015.09.029","journal":"Current Biology","url":"https://doi.org/10.1016/j.cub.2015.09.029","outcome":"Evolutionary trade-off: species with larger hyoids have smaller testes.","open_access":1}]},
    {"sci":"Aptenodytes patagonicus","en":"king penguin","it":"pinguino reale","es":"pingüino rey","fr":"manchot royal","de":"königspinguin","class_":"Aves","order_":"Sphenisciformes","family":"Spheniscidae","wiki":"King_penguin","xc":"Aptenodytes patagonicus","voc":["call","contact call"],"ctx":["colony recognition","parent-offspring"],"fn":["individual recognition","parent-offspring"],"papers":[{"title":"How king penguins find their mate in a crowded colony","year":1999,"doi":"10.1121/1.427349","journal":"J Acoustical Society of America","url":"https://doi.org/10.1121/1.427349","outcome":"King penguins use temporal patterns for individual recognition in dense colonies.","open_access":1}]},
    {"sci":"Acanthisitta chloris","en":"rifleman","it":"xenico verde","es":"acantisita","fr":"xénique grimpeur","de":"grünschlüpfer","class_":"Aves","order_":"Passeriformes","family":"Acanthisittidae","wiki":"Rifleman_(bird)","xc":"Acanthisitta chloris","voc":["call"],"ctx":["parent-offspring"],"fn":["parent-offspring recognition"],"papers":[{"title":"Prenatal call learning in rifleman birds","year":2014,"doi":"10.1016/j.cub.2014.06.053","journal":"Current Biology","url":"https://doi.org/10.1016/j.cub.2014.06.053","outcome":"Mothers teach embryos a password call used post-hatch to reject brood parasites.","open_access":1}]},
    {"sci":"Chelonia mydas","en":"green sea turtle","it":"tartaruga verde","es":"tortuga verde","fr":"tortue verte","de":"grüne meeresschildkröte","class_":"Reptilia","order_":"Testudines","family":"Cheloniidae","wiki":"Green_sea_turtle","xc":"","voc":["call"],"ctx":["nest emergence"],"fn":["group synchronisation"],"papers":[{"title":"Sound production in sea turtles","year":2014,"doi":"10.1016/j.anbehav.2014.02.008","journal":"Animal Behaviour","url":"https://doi.org/10.1016/j.anbehav.2014.02.008","outcome":"Nesting turtles and hatchlings produce sounds synchronising group emergence.","open_access":1}]},
]

NEW_ENRICHMENT = {
    "Homo sapiens":{"themes":["vocal_learning","referential","syntax","cultural_transmission","individual_recognition","turn_taking","dialects","emotion","multimodal","deception","cooperation","parent_offspring","alarm","honest_signalling"],"freq":"0.08–12 kHz","learning":"open-ended","semiotic":"symbol"},
    "Indri indri":{"themes":["turn_taking","cultural_transmission","cooperation"],"freq":"0.6–6 kHz","learning":"social","semiotic":"index"},
    "Heterocephalus glaber":{"themes":["dialects","individual_recognition","cooperation"],"freq":"0.5–15 kHz","learning":"social","semiotic":"index"},
    "Scotinomys teguina":{"themes":["turn_taking","honest_signalling"],"freq":"10–45 kHz","learning":"limited","semiotic":"index"},
    "Saccopteryx bilineata":{"themes":["vocal_learning","parent_offspring"],"freq":"10–90 kHz","learning":"open-ended","semiotic":"index"},
    "Rousettus aegyptiacus":{"themes":["vocal_learning","individual_recognition"],"freq":"5–80 kHz","learning":"social","semiotic":"index"},
    "Suricata suricatta":{"themes":["referential","alarm","cooperation"],"freq":"0.3–12 kHz","learning":"social","semiotic":"index"},
    "Callicebus nigrifrons":{"themes":["syntax","referential","alarm"],"freq":"0.5–8 kHz","learning":"innate","semiotic":"index"},
    "Balaenoptera musculus":{"themes":["infrasound","dialects"],"freq":"0.01–0.2 kHz","learning":"unknown","semiotic":"index"},
    "Delphinapterus leucas":{"themes":["vocal_learning","echolocation","individual_recognition"],"freq":"0.5–120 kHz","learning":"open-ended","semiotic":"index"},
    "Halichoerus grypus":{"themes":["vocal_learning"],"freq":"0.1–8 kHz","learning":"open-ended","semiotic":"index"},
    "Mirounga angustirostris":{"themes":["individual_recognition","honest_signalling"],"freq":"0.1–4 kHz","learning":"limited","semiotic":"index"},
    "Alouatta palliata":{"themes":["honest_signalling","cooperation"],"freq":"0.3–2 kHz","learning":"innate","semiotic":"index"},
    "Aptenodytes patagonicus":{"themes":["individual_recognition","parent_offspring"],"freq":"0.5–4 kHz","learning":"innate","semiotic":"index"},
    "Acanthisitta chloris":{"themes":["parent_offspring","vocal_learning"],"freq":"5–12 kHz","learning":"innate","semiotic":"index"},
    "Chelonia mydas":{"themes":["parent_offspring"],"freq":"0.1–1 kHz","learning":"innate","semiotic":"index"},
}

# Enrich existing species
existing_names = {s['sci'] for s in SPECIES}
for sp in SPECIES:
    enr = ENRICHMENT.get(sp['sci'], {})
    sp['themes'] = enr.get('themes', ['honest_signalling'])
    sp['freq'] = enr.get('freq', '—')
    sp['learning'] = enr.get('learning', 'unknown')
    sp['semiotic'] = enr.get('semiotic', 'index')

# Add new species
added = 0
for ns in NEW_SPECIES:
    if ns['sci'] not in existing_names:
        enr = NEW_ENRICHMENT.get(ns['sci'], {})
        ns['themes'] = enr.get('themes', ['honest_signalling'])
        ns['freq'] = enr.get('freq', '—')
        ns['learning'] = enr.get('learning', 'unknown')
        ns['semiotic'] = enr.get('semiotic', 'index')
        SPECIES.append(ns)
        added += 1

SPECIES.sort(key=lambda s: (s.get('class_',''), s['sci']))
total_papers = sum(len(s.get('papers',[])) for s in SPECIES)
print(f"  Added {added} new species. Total: {len(SPECIES)}, Papers: {total_papers}")

# Serialize
DB_JSON = json.dumps(SPECIES, ensure_ascii=False, separators=(',',':'))
THEMES_JSON = json.dumps(THEMES, ensure_ascii=False, separators=(',',':'))

# ── 2. GENERATE INDEX.HTML ──────────────────────────────────────────────────
print("Generating index.html...")

# Read existing and patch it
with open(OUT / 'index.html', 'r', encoding='utf-8') as f:
    idx = f.read()

# Update version
idx = idx.replace('v0.6', 'v1.0').replace('v0.1.2', 'v1.0')

# Add compare link to nav
idx = idx.replace(
    '<a href="graph_explorer.html">graph</a>',
    '<a href="graph_explorer.html">graph</a>\n    <a href="compare.html">compare</a>'
)

# Add tree background to hero
idx = idx.replace(
    '/* HERO */',
    '''/* HERO BG — trees on body, light overlay */
  body::before {
    content: '';
    position: fixed;
    inset: 0;
    background: url('tree.jpg') center top/cover no-repeat;
    opacity: 0.55;
    z-index: -2;
    pointer-events: none;
  }
  body::after {
    content: '';
    position: fixed;
    inset: 0;
    background: linear-gradient(180deg, rgba(14,15,17,0.15) 0%, rgba(14,15,17,0.45) 100%);
    z-index: -1;
    pointer-events: none;
  }
  .hero-bg { position: relative; }
  .hero-section { position: relative; z-index: 2; }
  nav { background: rgba(14,15,17,0.65) !important; }
  .tools-section { position: relative; z-index: 2; }
  .tool-card { background: rgba(22,24,32,0.85) !important; backdrop-filter: blur(8px); }
  .tool-card:hover { background: rgba(30,32,40,0.95) !important; }
  .pipeline { background: rgba(22,24,32,0.85) !important; backdrop-filter: blur(8px); }
  .tools-grid { background: rgba(14,15,17,0.3); }
  footer { background: rgba(14,15,17,0.7); position: relative; z-index: 2; }
  /* HERO */'''
)
# Force normal style on hero title
idx = idx.replace(
    '.hero-title {\n    font-family',
    '.hero-title {\n    font-style: normal;\n    font-family'
)

# Wrap hero section with bg div
idx = idx.replace(
    '<section class="hero-section">',
    '<div class="hero-bg">\n<section class="hero-section">'
)
idx = idx.replace(
    '</section>\n\n<section class="tools-section">',
    '</section>\n</div>\n\n<section class="tools-section">'
)

# Update stats
idx = idx.replace('<span class="stat-n">102</span>', f'<span class="stat-n">{len(SPECIES)}</span>')
idx = idx.replace('<span class="stat-n">122</span>', f'<span class="stat-n">{total_papers}</span>')
idx = idx.replace('<span class="stat-n">324</span>', '<span class="stat-n">16</span>')
idx = idx.replace('<span class="stat-l">graph nodes</span>', '<span class="stat-l">research themes</span>')
idx = idx.replace('<span class="stat-n">12</span>', '<span class="stat-n">6</span>')
idx = idx.replace('<span class="stat-l">communities</span>', '<span class="stat-l">classes</span>')

# Update tool card descriptions
idx = idx.replace(
    '102 species · search in 6 languages · radial communication graph · taxonomy · audio · curated papers with DOI.',
    f'{len(SPECIES)} species · search in 6 languages · thematic tagging · acoustic profiles · curated papers with DOI · species comparison.'
)
idx = idx.replace(
    'Filter papers by species, function, vocalisation type, year, source. Evidence matrix · by-function barplot · BibTeX export.',
    f'{total_papers} papers organised by 16 research themes. Vocal learning · referential communication · syntax · echolocation · and more.'
)
idx = idx.replace(
    'Interactive D3 force graph · 12 communities detected · bipartite and species-projection modes · download SVG / GraphML.',
    'Interactive force graph with 3 modes: by theme, by class, by function. Drag nodes, zoom, double-click for species details.'
)

with open(OUT / 'index.html', 'w', encoding='utf-8') as f:
    f.write(idx)
print("  ✓ index.html")

# ── 3. GENERATE ENHANCED SPECIES EXPLORER ──────────────────────────────────
print("Generating species_explorer.html...")

# Read original
with open(OUT / 'species_explorer.html', 'r', encoding='utf-8') as f:
    sp_html = f.read()

# Replace the EMBEDDED_DB with enriched version
sp_html = re.sub(
    r'const EMBEDDED_DB = \[.*?\];',
    f'const EMBEDDED_DB = {DB_JSON};',
    sp_html,
    flags=re.DOTALL
)

# Add THEMES constant after EMBEDDED_DB
sp_html = sp_html.replace(
    f'const EMBEDDED_DB = {DB_JSON};',
    f'const EMBEDDED_DB = {DB_JSON};\nconst THEMES = {THEMES_JSON};\nconst themeMap = Object.fromEntries(THEMES.map(t=>[t.id,t]));'
)

# Update version
sp_html = sp_html.replace('v0.1.2', 'v1.0')

# Add compare + literature + graph links to nav
sp_html = sp_html.replace(
    '<a href="index.html">home</a>',
    '<a href="index.html">home</a>\n    <a href="literature.html">literature</a>\n    <a href="graph_explorer.html">graph</a>\n    <a href="compare.html">compare</a>'
)

# Add extra CSS for theme tags, compare button, acoustic info, and compare bar
extra_css = """
/* Theme tags */
.theme-tags{display:flex;flex-wrap:wrap;gap:3px;margin-top:4px}
.ttag{font-size:9px;padding:2px 6px;border-radius:99px}
/* Compare btn on cards */
.card-cmp{position:absolute;top:8px;right:8px;width:20px;height:20px;border-radius:50%;border:1.5px solid var(--border2);background:none;cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:10px;color:var(--hint);transition:.15s;z-index:2}
.card-cmp:hover,.card-cmp.sel{background:var(--amber);border-color:var(--amber);color:var(--bg)}
/* Compare bar */
.cmp-bar{position:fixed;bottom:0;left:0;right:0;z-index:90;background:var(--surface);border-top:1px solid var(--border2);padding:.6rem 1.5rem;display:flex;align-items:center;gap:10px;transform:translateY(100%);transition:.25s}
.cmp-bar.vis{transform:translateY(0)}
.cmp-bar-names{font-size:12px;color:var(--muted);flex:1}
.cmp-bar-go{font-size:12px;padding:6px 16px;border-radius:6px;border:none;background:var(--amber);color:var(--bg);cursor:pointer;font-family:'DM Sans',sans-serif;font-weight:500}
.cmp-bar-clr{font-size:11px;padding:5px 12px;border-radius:6px;border:1px solid var(--border2);background:none;color:var(--muted);cursor:pointer;font-family:'DM Sans',sans-serif}
/* Acoustic info */
.aic{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-bottom:1rem}
.aic .ic{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:8px 10px}
.aic .ic label{font-size:9px;color:var(--hint);text-transform:uppercase;letter-spacing:.06em;display:block;margin-bottom:2px}
.aic .ic span{font-size:12px;color:var(--text);font-weight:300}
"""
sp_html = sp_html.replace('</style>', extra_css + '\n</style>')

# Add compare bar before closing body
# Insert cmp-bar BEFORE the script (so DOM exists when JS runs)
cmp_bar_div = '''<div class="cmp-bar" id="cmp-bar">
  <span class="cmp-bar-names" id="cmp-bar-names"></span>
  <a class="cmp-bar-go" href="compare.html">Compare →</a>
  <button class="cmp-bar-clr" onclick="clearCompare()">Clear</button>
</div>
'''
# Find the script that contains EMBEDDED_DB and insert cmp-bar right before it
script_pos = sp_html.rfind('<script>')
sp_html = sp_html[:script_pos] + cmp_bar_div + '\n' + sp_html[script_pos:]

# Add theme filter row + enhanced card rendering + compare logic
# We need to inject new JS. Find the script section and add to it.
# Add theme tags to card rendering
sp_html = sp_html.replace(
    "const themeTags = (sp.themes||[]).slice(0,3)",
    "/* theme tags already computed */ const themeTags = (sp.themes||[]).slice(0,3)"
)

# Inject enhanced JS before closing script
inject_js = """
// ── COMPARE SYSTEM ──────────────────────────────────────
let compareSet = new Set();
try { compareSet = new Set(JSON.parse(sessionStorage.getItem('zl_compare')||'[]')); } catch(e){}
function saveCompare(){ sessionStorage.setItem('zl_compare',JSON.stringify([...compareSet])); }
function toggleCompare(sci,ev){
  if(ev)ev.stopPropagation();
  if(compareSet.has(sci)) compareSet.delete(sci); else if(compareSet.size<4) compareSet.add(sci);
  saveCompare(); updateCompareBar();
  // re-render
  document.querySelectorAll('.card-cmp').forEach(b=>{
    b.classList.toggle('sel', compareSet.has(b.dataset.sci));
  });
}
function clearCompare(){ compareSet.clear(); saveCompare(); updateCompareBar(); document.querySelectorAll('.card-cmp').forEach(b=>b.classList.remove('sel')); }
function updateCompareBar(){
  const bar=document.getElementById('cmp-bar');
  if(!bar)return;
  if(compareSet.size>0){
    bar.classList.add('vis');
    const names=[...compareSet].map(sci=>{const sp=EMBEDDED_DB.find(s=>s.sci===sci);return sp?sp.en:sci;});
    document.getElementById('cmp-bar-names').textContent=names.join(' vs ');
  } else bar.classList.remove('vis');
}
updateCompareBar();
"""
sp_html = sp_html.replace('</script>', inject_js + '\n</script>')

with open(OUT / 'species_explorer.html', 'w', encoding='utf-8') as f:
    f.write(sp_html)
print("  ✓ species_explorer.html")

# ── 4. GENERATE LITERATURE BY THEME ────────────────────────────────────────
print("Generating literature.html...")

lit_papers_by_theme = {}
for th in THEMES:
    sps = [s for s in SPECIES if th['id'] in s.get('themes',[])]
    papers = []
    seen_dois = set()
    for sp in sps:
        for p in sp.get('papers',[]):
            if p.get('doi') and p['doi'] not in seen_dois:
                seen_dois.add(p['doi'])
                papers.append({**p, 'species_sci':sp['sci'], 'species_en':sp['en']})
    papers.sort(key=lambda p: -p.get('year',0))
    if papers:
        lit_papers_by_theme[th['id']] = {'theme':th, 'species_count':len(sps), 'papers':papers}

lit_html_groups = ""
for th in THEMES:
    data = lit_papers_by_theme.get(th['id'])
    if not data: continue
    papers_html = ""
    for p in data['papers']:
        url = p.get('url','') or f"https://doi.org/{p.get('doi','')}"
        papers_html += f'''<div class="pc">
  <a class="pc-title" href="{url}" target="_blank">{p['title']}</a>
  <div class="pc-meta"><span class="pc-journal">{p.get('journal','')}</span> <span>({p.get('year','')})</span> <span style="color:var(--teal);font-style:italic;margin-left:8px">{p['species_sci']}</span></div>
  <div class="pc-outcome">{p.get('outcome','')}</div>
  <div class="pc-actions"><a class="pact" href="{url}" target="_blank">DOI: {p.get('doi','')}</a></div>
</div>'''
    lit_html_groups += f'''<div class="lit-group" style="margin-bottom:2.5rem">
  <h3 style="font-family:'DM Serif Display',serif;font-size:20px;font-weight:400;margin-bottom:.3rem;display:flex;align-items:center;gap:8px">
    <span style="width:12px;height:12px;border-radius:50%;background:{th['color']};display:inline-block;flex-shrink:0"></span>
    {th['label']}
  </h3>
  <p style="font-size:12px;color:var(--muted);margin-bottom:.5rem">{th['desc']}</p>
  <p style="font-size:11px;color:var(--hint);margin-bottom:1rem;padding-bottom:.8rem;border-bottom:1px solid var(--border)">{data['species_count']} species · {len(data['papers'])} papers</p>
  <div class="paper-list">{papers_html}</div>
</div>'''

with open(OUT / 'literature.html', 'r', encoding='utf-8') as f:
    lit_orig = f.read()

# Extract CSS from original literature.html (keep the styling)
lit_css_match = re.search(r'<style>(.*?)</style>', lit_orig, re.DOTALL)
lit_css = lit_css_match.group(1) if lit_css_match else ""

lit_new = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Zoe.Logos-Graph — Literature by Theme</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<style>
{lit_css}
.main{{max-width:900px;margin:0 auto;padding:2rem}}
</style>
</head>
<body>
<nav>
  <a class="logo" href="index.html">
    <span>Zoe<span class="a">.</span>Logos<span class="a">-</span>Graph</span>
    <span class="logo-sub">v1.0</span>
  </a>
  <div class="nav-links">
    <a href="species_explorer.html">species</a>
    <a href="literature.html" style="color:var(--text)">literature</a>
    <a href="graph_explorer.html">graph</a>
    <a href="compare.html">compare</a>
    <a class="nav-gh" href="https://github.com/antorr91/Zoe.Logos-Graph" target="_blank">github →</a>
  </div>
</nav>
<div class="main">
  <div style="padding:2rem 0 1.5rem;border-bottom:1px solid var(--border);margin-bottom:2rem">
    <h1 style="font-family:'DM Serif Display',serif;font-size:28px;font-weight:400;color:var(--text)">Literature by <em style="color:var(--amber);font-style:italic">research theme</em></h1>
    <p style="font-size:14px;color:var(--muted);margin-top:.5rem;font-weight:300">{total_papers} curated papers across {len(THEMES)} research themes. Click DOI to access the original publication.</p>
    <div class="stat-row" style="margin-top:1.5rem">
      <div class="stat"><span class="stat-n">{len(SPECIES)}</span><span class="stat-l">species</span></div>
      <div class="stat"><span class="stat-n">{total_papers}</span><span class="stat-l">papers</span></div>
      <div class="stat"><span class="stat-n">{len(THEMES)}</span><span class="stat-l">themes</span></div>
    </div>
  </div>
  {lit_html_groups}
</div>
</body>
</html>'''

with open(OUT / 'literature.html', 'w', encoding='utf-8') as f:
    f.write(lit_new)
print("  ✓ literature.html")

# ── 5. GENERATE COMPARE PAGE ──────────────────────────────────────────────
print("Generating compare.html...")
compare_html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Zoe.Logos-Graph — Species Comparison</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<style>
:root{{--bg:#0e0f11;--surface:#161820;--surface2:#1e2028;--border:rgba(255,255,255,0.08);--border2:rgba(255,255,255,0.14);--text:#e8e9ec;--muted:#7a7e8a;--hint:#454854;--amber:#e8a427;--amber-dim:rgba(232,164,39,0.12);--teal:#2cb88a;--teal-dim:rgba(44,184,138,0.12);--violet:#9b8ef0;--violet-dim:rgba(155,142,240,0.12)}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'DM Sans',sans-serif;background:var(--bg);color:var(--text);min-height:100vh}}
nav{{display:flex;align-items:center;justify-content:space-between;padding:1rem 2rem;border-bottom:1px solid var(--border);position:sticky;top:0;z-index:50;background:rgba(14,15,17,0.85);backdrop-filter:blur(16px)}}
.logo{{font-family:'DM Serif Display',serif;font-size:17px;color:var(--text);text-decoration:none;letter-spacing:-0.02em}}
.logo .a{{color:var(--amber)}}
.logo-sub{{font-size:11px;color:var(--muted);font-weight:300;margin-left:8px;font-family:'DM Sans'}}
.nav-links{{display:flex;gap:1.5rem;align-items:center}}
.nav-links a{{font-size:13px;color:var(--muted);text-decoration:none}}.nav-links a:hover{{color:var(--text)}}
.nav-gh{{font-size:12px;padding:5px 14px;border:1px solid var(--border2);border-radius:99px;color:var(--text);text-decoration:none}}
.main{{max-width:1000px;margin:0 auto;padding:2rem}}
.cmp-slots{{display:flex;gap:1rem;margin:1.5rem 0;flex-wrap:wrap}}
.cmp-slot{{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:1rem;min-width:160px;flex:1;text-align:center}}
.cmp-slot em{{font-size:14px;color:var(--text)}}
.cmp-slot small{{font-size:11px;color:var(--muted);display:block;margin-top:2px}}
.cmp-rm{{background:none;border:none;color:#ff6b6b;cursor:pointer;font-size:11px;margin-top:4px;font-family:'DM Sans'}}
table{{width:100%;border-collapse:collapse;font-size:12.5px;margin-top:1rem}}
th{{text-align:left;padding:8px 10px;font-size:10px;text-transform:uppercase;letter-spacing:1px;color:var(--amber);border-bottom:1px solid var(--border);font-weight:500}}
td{{padding:8px 10px;border-bottom:1px solid rgba(255,255,255,.04);color:var(--muted);vertical-align:top}}
td:first-child{{color:var(--hint);font-weight:500;width:140px}}
tr:hover td{{background:var(--surface)}}
.overlap{{margin-top:2rem}}
.overlap h3{{font-size:11px;text-transform:uppercase;letter-spacing:1.5px;color:var(--amber);margin-bottom:.8rem}}
.ogrid{{display:grid;grid-template-columns:1fr 1fr;gap:1rem}}
.ocard{{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:1rem}}
.ocard h4{{font-size:12px;color:var(--text);margin-bottom:.5rem}}
.stag{{font-size:10px;padding:3px 8px;border-radius:99px;display:inline-block;margin:2px;background:var(--amber-dim);color:var(--amber);border:1px solid rgba(232,164,39,.25)}}
.utag{{font-size:10px;padding:3px 8px;border-radius:99px;display:inline-block;margin:2px;background:var(--surface2);color:var(--muted);border:1px solid var(--border)}}
@media(max-width:700px){{.ogrid{{grid-template-columns:1fr}}.cmp-slots{{flex-direction:column}}}}
</style>
</head>
<body>
<nav>
  <a class="logo" href="index.html"><span>Zoe<span class="a">.</span>Logos<span class="a">-</span>Graph</span><span class="logo-sub">v1.0</span></a>
  <div class="nav-links">
    <a href="species_explorer.html">species</a>
    <a href="literature.html">literature</a>
    <a href="graph_explorer.html">graph</a>
    <a href="compare.html" style="color:var(--text)">compare</a>
    <a class="nav-gh" href="https://github.com/antorr91/Zoe.Logos-Graph" target="_blank">github →</a>
  </div>
</nav>
<div class="main">
  <h1 style="font-family:'DM Serif Display',serif;font-size:28px;font-weight:400;margin-bottom:.4rem">Species <em style="color:var(--amber);font-style:italic">comparison</em></h1>
  <p style="font-size:13px;color:var(--muted);margin-bottom:1.5rem">Select 2–4 species from the <a href="species_explorer.html" style="color:var(--amber)">Species tab</a> (click ✓), then return here.</p>
  <div id="cmp-slots" class="cmp-slots"></div>
  <div id="cmp-result"></div>
</div>
<script>
const DB = {DB_JSON};
const THEMES = {THEMES_JSON};
const themeMap = Object.fromEntries(THEMES.map(t=>[t.id,t]));
let cmpSet = [];
try {{ cmpSet = JSON.parse(sessionStorage.getItem('zl_compare')||'[]'); }} catch(e){{}}

function render() {{
  const sps = cmpSet.map(sci=>DB.find(s=>s.sci===sci)).filter(Boolean);
  const slots = document.getElementById('cmp-slots');
  const result = document.getElementById('cmp-result');
  if(sps.length<2){{
    slots.innerHTML='<p style="color:var(--muted)">Go to <a href="species_explorer.html" style="color:var(--amber)">Species</a> and select 2–4 species with the ✓ button.</p>';
    result.innerHTML='';return;
  }}
  slots.innerHTML=sps.map(sp=>`<div class="cmp-slot"><em>${{sp.sci}}</em><small>${{sp.en}}</small><button class="cmp-rm" onclick="rm('${{sp.sci}}')">remove</button></div>`).join('');

  const rows=[
    ['Class',s=>s.class_],['Order',s=>s.order_||''],['Family',s=>s.family||''],
    ['Freq range',s=>s.freq||'—'],['Learning',s=>s.learning||'—'],['Semiotic',s=>s.semiotic||'—'],
    ['Vocalisations',s=>(s.voc||[]).join(', ')],['Contexts',s=>(s.ctx||[]).join(', ')],
    ['Functions',s=>(s.fn||[]).join(', ')],
    ['Themes',s=>(s.themes||[]).map(t=>themeMap[t]?themeMap[t].label:t).join(', ')],
    ['Papers',s=>(s.papers||[]).length],
  ];
  let h=`<table><thead><tr><th>Dimension</th>${{sps.map(s=>`<th>${{s.en}}</th>`).join('')}}</tr></thead><tbody>`;
  rows.forEach(([l,fn])=>{{h+=`<tr><td>${{l}}</td>${{sps.map(s=>`<td>${{fn(s)}}</td>`).join('')}}</tr>`;}});
  h+='</tbody></table>';

  const allTh=sps.map(s=>new Set(s.themes||[]));
  const shared=[...allTh[0]].filter(t=>allTh.every(s=>s.has(t)));
  const allFn=sps.map(s=>new Set(s.fn||[]));
  const sharedFn=[...allFn[0]].filter(f=>allFn.every(s=>s.has(f)));

  h+=`<div class="overlap"><h3>Trait Overlap</h3><div class="ogrid">
    <div class="ocard"><h4>Shared Themes</h4>${{shared.length?shared.map(t=>`<span class="stag">${{themeMap[t]?themeMap[t].label:t}}</span>`).join(''):'<span style="color:var(--muted);font-size:11px">None</span>'}}</div>
    <div class="ocard"><h4>Shared Functions</h4>${{sharedFn.length?sharedFn.map(f=>`<span class="stag">${{f}}</span>`).join(''):'<span style="color:var(--muted);font-size:11px">None</span>'}}</div>
  </div></div>`;
  result.innerHTML=h;
}}
function rm(sci){{cmpSet=cmpSet.filter(s=>s!==sci);sessionStorage.setItem('zl_compare',JSON.stringify(cmpSet));render();}}
render();
</script>
</body>
</html>'''

with open(OUT / 'compare.html', 'w', encoding='utf-8') as f:
    f.write(compare_html)
print("  ✓ compare.html")

# ── 6. ENHANCE GRAPH EXPLORER ──────────────────────────────────────────────
print("Enhancing graph_explorer.html...")

with open(OUT / 'graph_explorer.html', 'r', encoding='utf-8') as f:
    graph_html = f.read()

# Update version and nav
graph_html = graph_html.replace('v0.4', 'v1.0')
graph_html = graph_html.replace(
    '<a href="species_explorer.html">species</a>',
    '<a href="species_explorer.html">species</a> <a href="literature.html">literature</a>'
)

# Add mode buttons to the controls
mode_btns = '''<div class="ctrl-group">
    <span class="ctrl-label">view mode</span>
    <div class="chip-row">
      <button class="chip on" onclick="setGMode('community',this)">communities</button>
      <button class="chip" onclick="setGMode('theme',this)">by theme</button>
      <button class="chip" onclick="setGMode('class',this)">by class</button>
      <button class="chip" onclick="setGMode('function',this)">by function</button>
    </div>
  </div>'''

# Insert mode buttons at the top of controls
graph_html = graph_html.replace(
    '<div class="ctrl-group">\n    <span class="ctrl-label">communities</span>',
    mode_btns + '\n  <div class="ctrl-group" id="comm-ctrl">\n    <span class="ctrl-label">communities</span>'
)

# Inject the thematic graph data and mode switching
theme_graph_js = f"""
// ── THEMATIC GRAPH MODES ──────────────────────
const THEME_DB = {DB_JSON};
const GRAPH_THEMES = {THEMES_JSON};
const classColors = {{'Aves':'#4ecdc4','Mammalia':'#ff6b6b','Amphibia':'#ffd93d','Actinopterygii':'#6c5ce7','Insecta':'#a29bfe','Reptilia':'#e17055'}};
let currentGMode = 'community';

function setGMode(mode, btn) {{
  currentGMode = mode;
  document.querySelectorAll('.chip').forEach(c=>c.classList.remove('on'));
  btn.classList.add('on');
  // Show/hide community controls
  const commCtrl = document.getElementById('comm-ctrl');
  if(commCtrl) commCtrl.style.display = mode==='community' ? 'block' : 'none';

  if(mode === 'community') {{
    // Restore original D3 graph
    if(typeof loadData === 'function') loadData();
  }} else {{
    buildThematicGraph(mode);
  }}
}}

function buildThematicGraph(mode) {{
  // Clear D3 SVG
  const svg = d3.select('#canvas svg');
  if(!svg.empty()) svg.selectAll('*').remove();

  const width = document.getElementById('canvas').clientWidth;
  const height = document.getElementById('canvas').clientHeight;

  const s = svg.empty() ?
    d3.select('#canvas').append('svg').attr('width',width).attr('height',height) :
    svg.attr('width',width).attr('height',height);

  const nodes = [], links = [];
  const themeMap = Object.fromEntries(GRAPH_THEMES.map(t=>[t.id,t]));

  if(mode === 'theme') {{
    GRAPH_THEMES.forEach(th => {{
      const sps = THEME_DB.filter(sp=>(sp.themes||[]).includes(th.id));
      if(sps.length) nodes.push({{id:'th_'+th.id,label:th.label,type:'hub',color:th.color,r:16+sps.length}});
    }});
    THEME_DB.forEach(sp => {{
      nodes.push({{id:'sp_'+sp.sci,label:sp.en,type:'species',color:classColors[sp.class_]||'#888',r:5+(sp.papers||[]).length*1.5,sci:sp.sci}});
      (sp.themes||[]).forEach(tid => {{
        if(nodes.find(n=>n.id==='th_'+tid))
          links.push({{source:'sp_'+sp.sci,target:'th_'+tid}});
      }});
    }});
  }} else if(mode === 'class') {{
    [...new Set(THEME_DB.map(s=>s.class_))].forEach(c => {{
      nodes.push({{id:'cl_'+c,label:c,type:'hub',color:classColors[c]||'#888',r:22}});
    }});
    THEME_DB.forEach(sp => {{
      nodes.push({{id:'sp_'+sp.sci,label:sp.en,type:'species',color:classColors[sp.class_]||'#888',r:5+(sp.papers||[]).length*1.5,sci:sp.sci}});
      links.push({{source:'sp_'+sp.sci,target:'cl_'+sp.class_}});
    }});
  }} else {{
    const fns = {{}};
    THEME_DB.forEach(sp=>(sp.fn||[]).forEach(f=>{{fns[f]=(fns[f]||0)+1;}}));
    Object.entries(fns).filter(([,n])=>n>=2).forEach(([f,n]) => {{
      nodes.push({{id:'fn_'+f,label:f,type:'hub',color:'#e8a427',r:10+n}});
    }});
    THEME_DB.forEach(sp => {{
      nodes.push({{id:'sp_'+sp.sci,label:sp.en,type:'species',color:classColors[sp.class_]||'#888',r:5+(sp.papers||[]).length*1.5,sci:sp.sci}});
      (sp.fn||[]).forEach(f => {{
        if(nodes.find(n=>n.id==='fn_'+f))
          links.push({{source:'sp_'+sp.sci,target:'fn_'+f}});
      }});
    }});
  }}

  const sim = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(links).id(d=>d.id).distance(80))
    .force('charge', d3.forceManyBody().strength(-120))
    .force('center', d3.forceCenter(width/2, height/2))
    .force('collision', d3.forceCollide().radius(d=>d.r+2));

  const link = s.append('g').selectAll('line').data(links).join('line')
    .attr('stroke','rgba(255,255,255,0.06)').attr('stroke-width',0.5);

  const node = s.append('g').selectAll('g').data(nodes).join('g')
    .call(d3.drag().on('start',(e,d)=>{{if(!e.active)sim.alphaTarget(0.3).restart();d.fx=d.x;d.fy=d.y;}})
      .on('drag',(e,d)=>{{d.fx=e.x;d.fy=e.y;}}).on('end',(e,d)=>{{if(!e.active)sim.alphaTarget(0);d.fx=null;d.fy=null;}}));

  node.append('circle').attr('r',d=>d.r).attr('fill',d=>d.type==='hub'?d.color+'cc':d.color+'33').attr('stroke',d=>d.color).attr('stroke-width',d=>d.type==='hub'?0:1);
  node.filter(d=>d.type==='hub').append('text').text(d=>d.label.length>18?d.label.slice(0,16)+'…':d.label)
    .attr('text-anchor','middle').attr('dy','0.35em').attr('fill','#0e0f11').attr('font-size',d=>d.r>14?'9px':'7px').attr('font-weight','bold');
  node.filter(d=>d.type==='species'&&d.r>7).append('text').text(d=>d.label).attr('text-anchor','middle').attr('dy',d=>d.r+12)
    .attr('fill','#7a7e8a').attr('font-size','8px');

  sim.on('tick',()=>{{
    link.attr('x1',d=>d.source.x).attr('y1',d=>d.source.y).attr('x2',d=>d.target.x).attr('y2',d=>d.target.y);
    node.attr('transform',d=>`translate(${{d.x}},${{d.y}})`);
  }});

  // Update stats
  const stEl = document.getElementById('st-n');
  if(stEl) stEl.textContent = nodes.length + ' nodes';
  const stE = document.getElementById('st-e');
  if(stE) stE.textContent = links.length + ' edges';
}}
"""

graph_html = graph_html.replace('</script>', theme_graph_js + '\n</script>')

with open(OUT / 'graph_explorer.html', 'w', encoding='utf-8') as f:
    f.write(graph_html)
print("  ✓ graph_explorer.html")

print(f"\n✓ All files generated in {OUT}/")
print(f"  Total: {len(SPECIES)} species, {total_papers} papers, {len(THEMES)} themes")
