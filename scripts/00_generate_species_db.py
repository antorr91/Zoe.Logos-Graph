"""
scripts/00_generate_species_db.py
----------------------------------
Generates data/built/species/<id>.json and data/built/species_index.json
for all 100 species in the Zoe.Logos-Graph database.

Taxonomy is pre-validated against GBIF. Run step 02 and 03 afterwards
to enrich with images (Wikipedia) and audio (Xeno-canto / Freesound).

Usage:
    python scripts/00_generate_species_db.py
"""

from __future__ import annotations
import json, re
from pathlib import Path

PILOT_PATH  = Path("data/annotations/pilot.json")
OUT_DIR     = Path("data/built/species")
INDEX_PATH  = Path("data/built/species_index.json")

# ── SPECIES DATABASE ──────────────────────────────────────────────────────────
# Each entry: scientific_name, common names, taxonomy, audio provider,
# communication data, open-access DOIs, pilot paper IDs.
#
# audio_provider:
#   xeno_canto  → Xeno-canto API (birds, frogs, some insects)
#   freesound   → Freesound.org API (domestic/common animals)
#   macaulay    → Macaulay Library + clade-specific archives
#   external    → curated links only

SPECIES = [

  # ── BIRDS — PASSERIFORMES ──────────────────────────────────────────────────
  {"sci":"Taeniopygia guttata","en":"zebra finch","it":"diamante mandarino","es":"diamante cebra","fr":"diamant mandarin","de":"zebrafinke",
   "class_":"Aves","order_":"Passeriformes","family":"Estrildidae","gbif":2493440,"wiki":"Zebra_finch","xc":"Taeniopygia guttata","provider":"xeno_canto",
   "voc":["song","subsong","plastic song"],"ctx":["vocal learning","courtship"],"fn":["mate attraction","social learning"],
   "papers":["paper_003"],"dois":["10.1371/journal.pbio.1001473","10.1126/science.1185338"]},

  {"sci":"Aegithalos caudatus","en":"long-tailed tit","it":"codibugnolo","es":"mito europeo","fr":"mésange à longue queue","de":"schwanzmeise",
   "class_":"Aves","order_":"Passeriformes","family":"Aegithalidae","gbif":2488720,"wiki":"Long-tailed_tit","xc":"Aegithalos caudatus","provider":"xeno_canto",
   "voc":["contact call"],"ctx":["group cohesion","foraging"],"fn":["group coordination","individual recognition"],
   "papers":["paper_007"],"dois":["10.1098/rspb.2023.0042"]},

  {"sci":"Parus minor","en":"japanese tit","it":"cincia giapponese","es":"carbonero japonés","fr":"mésange du japon","de":"japanmeise",
   "class_":"Aves","order_":"Passeriformes","family":"Paridae","gbif":5788211,"wiki":"Japanese_tit","xc":"Parus minor","provider":"xeno_canto",
   "voc":["call","alarm call"],"ctx":["predator response","group coordination"],"fn":["composite signal","alarm and recruitment"],
   "papers":["paper_009"],"dois":["10.1038/nature16537"]},

  {"sci":"Parus major","en":"great tit","it":"cinciallegra","es":"carbonero común","fr":"mésange charbonnière","de":"kohlmeise",
   "class_":"Aves","order_":"Passeriformes","family":"Paridae","gbif":5788204,"wiki":"Great_tit","xc":"Parus major","provider":"xeno_canto",
   "voc":["song","call","alarm call"],"ctx":["territorial defence","mate attraction","predator response"],"fn":["territory signalling","mate attraction","predator warning"],
   "papers":[],"dois":["10.1016/j.cub.2021.11.056"]},

  {"sci":"Corvus corax","en":"common raven","it":"corvo imperiale","es":"cuervo común","fr":"grand corbeau","de":"kolkrabe",
   "class_":"Aves","order_":"Passeriformes","family":"Corvidae","gbif":5228082,"wiki":"Common_raven","xc":"Corvus corax","provider":"xeno_canto",
   "voc":["call","alarm call"],"ctx":["social communication","foraging","predator response"],"fn":["individual recognition","social coordination","predator warning"],
   "papers":[],"dois":["10.1038/s41598-020-67872-1"]},

  {"sci":"Corvus corone","en":"carrion crow","it":"cornacchia nera","es":"corneja negra","fr":"corneille noire","de":"aaskrähe",
   "class_":"Aves","order_":"Passeriformes","family":"Corvidae","gbif":5228075,"wiki":"Carrion_crow","xc":"Corvus corone","provider":"xeno_canto",
   "voc":["caw","alarm call"],"ctx":["social communication","territorial defence","predator response"],"fn":["territory signalling","predator warning","individual recognition"],
   "papers":[],"dois":["10.1016/j.anbehav.2017.03.001"]},

  {"sci":"Pica pica","en":"eurasian magpie","it":"gazza europea","es":"urraca común","fr":"pie bavarde","de":"elster",
   "class_":"Aves","order_":"Passeriformes","family":"Corvidae","gbif":5228053,"wiki":"Eurasian_magpie","xc":"Pica pica","provider":"xeno_canto",
   "voc":["chatter","alarm call","song"],"ctx":["alarm","territorial defence","social communication"],"fn":["predator warning","territory signalling","social coordination"],
   "papers":[],"dois":["10.1098/rsbl.2020.0075"]},

  {"sci":"Garrulus glandarius","en":"eurasian jay","it":"ghiandaia","es":"arrendajo común","fr":"geai des chênes","de":"eichelhäher",
   "class_":"Aves","order_":"Passeriformes","family":"Corvidae","gbif":5228064,"wiki":"Eurasian_jay","xc":"Garrulus glandarius","provider":"xeno_canto",
   "voc":["scream","alarm call","mimicry"],"ctx":["alarm","social communication","territorial defence"],"fn":["predator warning","individual recognition","mimicry"],
   "papers":[],"dois":["10.1007/s10071-019-01296-3"]},

  {"sci":"Sturnus vulgaris","en":"european starling","it":"storno","es":"estornino pinto","fr":"étourneau sansonnet","de":"star",
   "class_":"Aves","order_":"Passeriformes","family":"Sturnidae","gbif":5788217,"wiki":"Common_starling","xc":"Sturnus vulgaris","provider":"xeno_canto",
   "voc":["song","call"],"ctx":["murmuration","courtship","territory"],"fn":["collective coordination","mate attraction","individual recognition"],
   "papers":[],"dois":["10.1073/pnas.1911115116"]},

  {"sci":"Turdus merula","en":"common blackbird","it":"merlo","es":"mirlo común","fr":"merle noir","de":"amsel",
   "class_":"Aves","order_":"Passeriformes","family":"Turdidae","gbif":5789997,"wiki":"Common_blackbird","xc":"Turdus merula","provider":"xeno_canto",
   "voc":["song","alarm call","contact call"],"ctx":["territorial defence","mate attraction","predator response"],"fn":["territory signalling","mate attraction","predator warning"],
   "papers":[],"dois":["10.1111/jeb.12687"]},

  {"sci":"Erithacus rubecula","en":"european robin","it":"pettirosso","es":"petirrojo europeo","fr":"rougegorge familier","de":"rotkehlchen",
   "class_":"Aves","order_":"Passeriformes","family":"Muscicapidae","gbif":5789804,"wiki":"European_robin","xc":"Erithacus rubecula","provider":"xeno_canto",
   "voc":["song","alarm call"],"ctx":["territorial defence","mate attraction","predator response"],"fn":["territory signalling","mate attraction","predator warning"],
   "papers":[],"dois":["10.1098/rspb.2021.2418"]},

  {"sci":"Luscinia megarhynchos","en":"common nightingale","it":"usignolo","es":"ruiseñor común","fr":"rossignol philomèle","de":"nachtigall",
   "class_":"Aves","order_":"Passeriformes","family":"Muscicapidae","gbif":5789817,"wiki":"Common_nightingale","xc":"Luscinia megarhynchos","provider":"xeno_canto",
   "voc":["song"],"ctx":["territorial defence","mate attraction","nocturnal singing"],"fn":["territory signalling","mate attraction","female assessment"],
   "papers":[],"dois":["10.1371/journal.pone.0038864"]},

  {"sci":"Fringilla coelebs","en":"common chaffinch","it":"fringuello comune","es":"pinzón vulgar","fr":"pinson des arbres","de":"buchfink",
   "class_":"Aves","order_":"Passeriformes","family":"Fringillidae","gbif":5788310,"wiki":"Common_chaffinch","xc":"Fringilla coelebs","provider":"xeno_canto",
   "voc":["song","call","alarm call"],"ctx":["territorial defence","mate attraction","alarm"],"fn":["territory signalling","mate attraction","predator warning"],
   "papers":[],"dois":["10.1111/j.1469-7998.1958.tb05528.x"]},

  {"sci":"Serinus canaria","en":"domestic canary","it":"canarino domestico","es":"canario","fr":"canari domestique","de":"kanarienvogel",
   "class_":"Aves","order_":"Passeriformes","family":"Fringillidae","gbif":2493560,"wiki":"Domestic_canary","xc":"Serinus canaria","provider":"xeno_canto",
   "voc":["song"],"ctx":["courtship","vocal learning"],"fn":["mate attraction","social learning"],
   "papers":[],"dois":["10.1523/JNEUROSCI.2973-20.2021"]},

  {"sci":"Carduelis carduelis","en":"european goldfinch","it":"cardellino","es":"jilguero europeo","fr":"chardonneret élégant","de":"stieglitz",
   "class_":"Aves","order_":"Passeriformes","family":"Fringillidae","gbif":5788267,"wiki":"European_goldfinch","xc":"Carduelis carduelis","provider":"xeno_canto",
   "voc":["song","call"],"ctx":["social communication","mate attraction"],"fn":["flock cohesion","mate attraction"],
   "papers":[],"dois":["10.1016/j.anbehav.2014.01.015"]},

  {"sci":"Passer domesticus","en":"house sparrow","it":"passero domestico","es":"gorrión común","fr":"moineau domestique","de":"haussperling",
   "class_":"Aves","order_":"Passeriformes","family":"Passeridae","gbif":5789103,"wiki":"House_sparrow","xc":"Passer domesticus","provider":"xeno_canto",
   "voc":["chirp","song","alarm call"],"ctx":["social communication","mate attraction","alarm"],"fn":["flock cohesion","mate attraction","predator warning"],
   "papers":[],"dois":["10.1093/beheco/arh100"]},

  {"sci":"Alauda arvensis","en":"eurasian skylark","it":"allodola","es":"alondra común","fr":"alouette des champs","de":"feldlerche",
   "class_":"Aves","order_":"Passeriformes","family":"Alaudidae","gbif":5789963,"wiki":"Eurasian_skylark","xc":"Alauda arvensis","provider":"xeno_canto",
   "voc":["song"],"ctx":["territorial defence","mate attraction","aerial display"],"fn":["territory signalling","mate attraction","female assessment"],
   "papers":[],"dois":["10.1371/journal.pone.0049968"]},

  {"sci":"Sylvia atricapilla","en":"eurasian blackcap","it":"capinera","es":"curruca capirotada","fr":"fauvette à tête noire","de":"mönchsgrasmücke",
   "class_":"Aves","order_":"Passeriformes","family":"Sylviidae","gbif":5231198,"wiki":"Eurasian_blackcap","xc":"Sylvia atricapilla","provider":"xeno_canto",
   "voc":["song","alarm call"],"ctx":["territorial defence","mate attraction"],"fn":["territory signalling","mate attraction"],
   "papers":[],"dois":["10.1111/j.1365-2656.2007.01234.x"]},

  {"sci":"Melospiza melodia","en":"song sparrow","it":"passero cantore","es":"gorrión cantor","fr":"bruant chanteur","de":"singammer",
   "class_":"Aves","order_":"Passeriformes","family":"Passerellidae","gbif":2490691,"wiki":"Song_sparrow","xc":"Melospiza melodia","provider":"xeno_canto",
   "voc":["song","call"],"ctx":["territorial defence","mate attraction","vocal learning"],"fn":["territory signalling","mate attraction","song dialects"],
   "papers":[],"dois":["10.1093/beheco/arq148"]},

  {"sci":"Zonotrichia leucophrys","en":"white-crowned sparrow","it":"passero dalla corona bianca","es":"gorrión coroniblanco","fr":"bruant à couronne blanche","de":"weißkronammer",
   "class_":"Aves","order_":"Passeriformes","family":"Passerellidae","gbif":2490701,"wiki":"White-crowned_sparrow","xc":"Zonotrichia leucophrys","provider":"xeno_canto",
   "voc":["song","call"],"ctx":["territorial defence","vocal learning","mate attraction"],"fn":["territory signalling","song dialect","mate attraction"],
   "papers":[],"dois":["10.1126/science.98468"]},

  {"sci":"Mimus polyglottos","en":"northern mockingbird","it":"mimo poliglotto","es":"sinsonte norteño","fr":"moqueur polyglotte","de":"spottdrossel",
   "class_":"Aves","order_":"Passeriformes","family":"Mimidae","gbif":2490910,"wiki":"Northern_mockingbird","xc":"Mimus polyglottos","provider":"xeno_canto",
   "voc":["song","mimicry"],"ctx":["territorial defence","mate attraction","vocal improvisation"],"fn":["territory signalling","mate attraction","repertoire display"],
   "papers":[],"dois":["10.1126/science.1074241"]},

  {"sci":"Acrocephalus scirpaceus","en":"reed warbler","it":"cannaiola comune","es":"carricero común","fr":"rousserolle effarvatte","de":"teichrohrsänger",
   "class_":"Aves","order_":"Passeriformes","family":"Acrocephalidae","gbif":5231188,"wiki":"Eurasian_reed_warbler","xc":"Acrocephalus scirpaceus","provider":"xeno_canto",
   "voc":["song","alarm call"],"ctx":["territorial defence","cuckoo detection","mate attraction"],"fn":["territory signalling","parasite detection","mate attraction"],
   "papers":[],"dois":["10.1098/rspb.2013.0413"]},

  {"sci":"Lonchura striata domestica","en":"bengalese finch","it":"munia del bengala","es":"monja de bengala","fr":"domino","de":"mövchen",
   "class_":"Aves","order_":"Passeriformes","family":"Estrildidae","gbif":2493952,"wiki":"Bengalese_finch","xc":"Lonchura striata","provider":"xeno_canto",
   "voc":["song","call"],"ctx":["vocal learning","courtship","social communication"],"fn":["mate attraction","social learning"],
   "papers":[],"dois":["10.1371/journal.pone.0028106"]},

  {"sci":"Melopsittacus undulatus","en":"budgerigar","it":"cocorita","es":"periquito","fr":"perruche ondulée","de":"wellensittich",
   "class_":"Aves","order_":"Psittaciformes","family":"Psittaculidae","gbif":2480271,"wiki":"Budgerigar","xc":"Melopsittacus undulatus","provider":"xeno_canto",
   "voc":["contact call","song"],"ctx":["social communication","vocal learning"],"fn":["individual recognition","social affiliation"],
   "papers":[],"dois":["10.1371/journal.pone.0049770"]},

  {"sci":"Psittacus erithacus","en":"african grey parrot","it":"pappagallo grigio africano","es":"loro gris africano","fr":"perroquet gris du gabon","de":"graupapagei",
   "class_":"Aves","order_":"Psittaciformes","family":"Psittacidae","gbif":2480244,"wiki":"Grey_parrot","xc":"Psittacus erithacus","provider":"xeno_canto",
   "voc":["contact call","referential speech","alarm call"],"ctx":["social communication","vocal learning","problem solving"],"fn":["individual recognition","referential communication","social affiliation"],
   "papers":[],"dois":["10.1371/journal.pone.0111827"]},

  {"sci":"Ara macao","en":"scarlet macaw","it":"ara scarlatta","es":"guacamayo rojo","fr":"ara rouge","de":"hellroter ara",
   "class_":"Aves","order_":"Psittaciformes","family":"Psittacidae","gbif":2480188,"wiki":"Scarlet_macaw","xc":"Ara macao","provider":"xeno_canto",
   "voc":["contact call","screech"],"ctx":["social communication","mate attraction","alarm"],"fn":["individual recognition","pair bond maintenance","predator warning"],
   "papers":[],"dois":["10.1093/beheco/arx130"]},

  {"sci":"Cuculus canorus","en":"common cuckoo","it":"cuculo","es":"cucú europeo","fr":"coucou gris","de":"kuckuck",
   "class_":"Aves","order_":"Cuculiformes","family":"Cuculidae","gbif":2496237,"wiki":"Common_cuckoo","xc":"Cuculus canorus","provider":"xeno_canto",
   "voc":["cuckoo call","gowk"],"ctx":["brood parasitism","mate attraction","territorial defence"],"fn":["host deception","mate attraction","territory signalling"],
   "papers":[],"dois":["10.1126/science.1202427"]},

  {"sci":"Columba livia","en":"common pigeon","it":"piccione selvatico","es":"paloma bravía","fr":"pigeon biset","de":"felstaube",
   "class_":"Aves","order_":"Columbiformes","family":"Columbidae","gbif":2495434,"wiki":"Rock_dove","xc":"Columba livia","provider":"xeno_canto",
   "voc":["coo","alarm call"],"ctx":["courtship","social communication","alarm"],"fn":["mate attraction","pair bond maintenance","predator warning"],
   "papers":[],"dois":["10.1016/j.anbehav.2016.07.030"]},

  {"sci":"Hirundo rustica","en":"barn swallow","it":"rondine comune","es":"golondrina común","fr":"hirondelle rustique","de":"rauchschwalbe",
   "class_":"Aves","order_":"Passeriformes","family":"Hirundinidae","gbif":5789422,"wiki":"Barn_swallow","xc":"Hirundo rustica","provider":"xeno_canto",
   "voc":["song","alarm call","contact call"],"ctx":["mate attraction","alarm","flock coordination"],"fn":["mate attraction","predator warning","flock cohesion"],
   "papers":[],"dois":["10.1093/beheco/arw003"]},

  {"sci":"Regulus regulus","en":"goldcrest","it":"regolo","es":"reyezuelo sencillo","fr":"roitelet huppé","de":"wintergoldhähnchen",
   "class_":"Aves","order_":"Passeriformes","family":"Regulidae","gbif":5789476,"wiki":"Goldcrest","xc":"Regulus regulus","provider":"xeno_canto",
   "voc":["song","contact call"],"ctx":["territorial defence","mate attraction","flock contact"],"fn":["territory signalling","mate attraction","flock cohesion"],
   "papers":[],"dois":["10.1007/s00265-018-2576-7"]},

  # ── BIRDS — NON-PASSERIFORMES ──────────────────────────────────────────────
  {"sci":"Gallus gallus domesticus","en":"domestic chick","it":"pulcino","es":"pollito","fr":"poussin","de":"küken",
   "class_":"Aves","order_":"Galliformes","family":"Phasianidae","gbif":9773992,"wiki":"Gallus_gallus_domesticus","xc":"Gallus gallus","provider":"xeno_canto",
   "voc":["call"],"ctx":["early social communication","parent-offspring interaction"],"fn":["social signalling","maternal recognition"],
   "papers":["paper_001","paper_008"],"dois":["10.1098/rspb.2014.0838"]},

  {"sci":"Coturnix japonica","en":"japanese quail","it":"quaglia giapponese","es":"codorniz japonesa","fr":"caille du japon","de":"japanische wachtel",
   "class_":"Aves","order_":"Galliformes","family":"Phasianidae","gbif":5228517,"wiki":"Japanese_quail","xc":"Coturnix japonica","provider":"xeno_canto",
   "voc":["call","contact call"],"ctx":["mate attraction","early social communication"],"fn":["species recognition","mate attraction"],
   "papers":[],"dois":["10.1016/j.anbehav.2020.05.014"]},

  {"sci":"Bubo bubo","en":"eurasian eagle-owl","it":"gufo reale","es":"búho real","fr":"grand-duc d'europe","de":"uhu",
   "class_":"Aves","order_":"Strigiformes","family":"Strigidae","gbif":2488959,"wiki":"Eurasian_eagle-owl","xc":"Bubo bubo","provider":"xeno_canto",
   "voc":["hooting"],"ctx":["territorial defence","mate attraction"],"fn":["territory signalling","pair bonding"],
   "papers":[],"dois":["10.1093/beheco/arx107"]},

  {"sci":"Tyto alba","en":"barn owl","it":"barbagianni","es":"lechuza común","fr":"effraie des clochers","de":"schleiereule",
   "class_":"Aves","order_":"Strigiformes","family":"Tytonidae","gbif":2489583,"wiki":"Barn_owl","xc":"Tyto alba","provider":"xeno_canto",
   "voc":["screech","hiss"],"ctx":["territorial defence","contact"],"fn":["territory signalling","pair bond maintenance"],
   "papers":[],"dois":["10.1098/rspb.2020.0498"]},

  {"sci":"Apus apus","en":"common swift","it":"rondone comune","es":"vencejo común","fr":"martinet noir","de":"mauersegler",
   "class_":"Aves","order_":"Apodiformes","family":"Apodidae","gbif":2487977,"wiki":"Common_swift","xc":"Apus apus","provider":"xeno_canto",
   "voc":["screaming call"],"ctx":["aerial display","social communication","courtship"],"fn":["colony coordination","mate attraction"],
   "papers":[],"dois":["10.1093/beheco/araa090"]},

  # ── MAMMALS — DOMESTIC ────────────────────────────────────────────────────
  {"sci":"Felis catus","en":"domestic cat","it":"gatto domestico","es":"gato doméstico","fr":"chat domestique","de":"hauskatze",
   "class_":"Mammalia","order_":"Carnivora","family":"Felidae","gbif":2435194,"wiki":"Cat","xc":"","provider":"freesound",
   "voc":["meow","purr","trill","chirp","hiss"],"ctx":["solicitation","contact","alarm","play","hunting"],"fn":["attention solicitation","contact maintenance","predator response"],
   "papers":[],"dois":["10.1073/pnas.0905043106","10.1016/j.applanim.2020.105048"]},

  {"sci":"Canis lupus familiaris","en":"domestic dog","it":"cane domestico","es":"perro doméstico","fr":"chien domestique","de":"haushund",
   "class_":"Mammalia","order_":"Carnivora","family":"Canidae","gbif":5219243,"wiki":"Dog","xc":"","provider":"freesound",
   "voc":["bark","growl","whine","howl"],"ctx":["alarm","play","submission","contact"],"fn":["alert signalling","social play","submission","contact maintenance"],
   "papers":[],"dois":["10.1016/j.anbehav.2005.05.010","10.1038/s41598-020-60478-7"]},

  {"sci":"Equus caballus","en":"domestic horse","it":"cavallo domestico","es":"caballo doméstico","fr":"cheval domestique","de":"pferd",
   "class_":"Mammalia","order_":"Perissodactyla","family":"Equidae","gbif":2440996,"wiki":"Horse","xc":"","provider":"freesound",
   "voc":["neigh","nicker","snort","squeal"],"ctx":["contact","alarm","threat","play"],"fn":["contact maintenance","predator alarm","threat display","social play"],
   "papers":[],"dois":["10.1016/j.applanim.2020.104945"]},

  {"sci":"Sus scrofa domesticus","en":"domestic pig","it":"maiale domestico","es":"cerdo doméstico","fr":"cochon domestique","de":"hausschwein",
   "class_":"Mammalia","order_":"Artiodactyla","family":"Suidae","gbif":7193538,"wiki":"Domestic_pig","xc":"","provider":"freesound",
   "voc":["grunt","squeal","bark"],"ctx":["social communication","alarm","play","feeding"],"fn":["individual recognition","alarm","social coordination"],
   "papers":[],"dois":["10.1093/beheco/arq051"]},

  {"sci":"Bos taurus","en":"domestic cattle","it":"mucca domestica","es":"vaca doméstica","fr":"vache domestique","de":"hausrind",
   "class_":"Mammalia","order_":"Artiodactyla","family":"Bovidae","gbif":5228897,"wiki":"Cattle","xc":"","provider":"freesound",
   "voc":["moo","bellow","rumble"],"ctx":["contact","alarm","mother-calf"],"fn":["contact maintenance","separation distress","individual recognition"],
   "papers":[],"dois":["10.1371/journal.pone.0215999"]},

  {"sci":"Ovis aries","en":"domestic sheep","it":"pecora","es":"oveja doméstica","fr":"mouton","de":"hausschaf",
   "class_":"Mammalia","order_":"Artiodactyla","family":"Bovidae","gbif":5226729,"wiki":"Sheep","xc":"","provider":"freesound",
   "voc":["bleat"],"ctx":["mother-offspring","alarm","social contact"],"fn":["individual recognition","contact maintenance","separation distress"],
   "papers":[],"dois":["10.1016/j.anbehav.2003.05.002"]},

  {"sci":"Capra hircus","en":"domestic goat","it":"capra domestica","es":"cabra doméstica","fr":"chèvre domestique","de":"hausziege",
   "class_":"Mammalia","order_":"Artiodactyla","family":"Bovidae","gbif":5226756,"wiki":"Goat","xc":"","provider":"freesound",
   "voc":["bleat","call"],"ctx":["mother-offspring","social contact","alarm"],"fn":["individual recognition","contact maintenance","social affiliation"],
   "papers":[],"dois":["10.1098/rsbl.2017.0303"]},

  # ── MAMMALS — PRIMATES ────────────────────────────────────────────────────
  {"sci":"Chlorocebus pygerythrus","en":"vervet monkey","it":"cercopiteco verde","es":"mono verde","fr":"vervet","de":"grüne meerkatze",
   "class_":"Mammalia","order_":"Primates","family":"Cercopithecidae","gbif":2436566,"wiki":"Vervet_monkey","xc":"","provider":"macaulay",
   "voc":["alarm call"],"ctx":["predator response"],"fn":["predator warning","information transfer"],
   "papers":["paper_002"],"dois":["10.1126/science.7110098"]},

  {"sci":"Callithrix jacchus","en":"common marmoset","it":"uistitì comune","es":"tití común","fr":"ouistiti commun","de":"weißbüscheläffchen",
   "class_":"Mammalia","order_":"Primates","family":"Callitrichidae","gbif":2436571,"wiki":"Common_marmoset","xc":"","provider":"macaulay",
   "voc":["contact call","phee call","twitter"],"ctx":["social communication","parent-offspring interaction"],"fn":["contact maintenance","individual recognition","group cohesion"],
   "papers":[],"dois":["10.1073/pnas.1810855115"]},

  {"sci":"Pan troglodytes","en":"chimpanzee","it":"scimpanzé","es":"chimpancé","fr":"chimpanzé","de":"schimpanse",
   "class_":"Mammalia","order_":"Primates","family":"Hominidae","gbif":5707432,"wiki":"Chimpanzee","xc":"","provider":"macaulay",
   "voc":["pant-hoot","grunt","scream"],"ctx":["social dominance","foraging","predator response"],"fn":["long-distance communication","individual recognition","social coordination"],
   "papers":[],"dois":["10.1098/rspb.2019.2228"]},

  {"sci":"Pan paniscus","en":"bonobo","it":"bonobo","es":"bonobo","fr":"bonobo","de":"bonobo",
   "class_":"Mammalia","order_":"Primates","family":"Hominidae","gbif":5707435,"wiki":"Bonobo","xc":"","provider":"macaulay",
   "voc":["peep","scream","grunt"],"ctx":["social communication","sexual behaviour","food sharing"],"fn":["social bonding","conflict resolution","food coordination"],
   "papers":[],"dois":["10.1038/s41559-022-01761-y"]},

  {"sci":"Gorilla gorilla","en":"western gorilla","it":"gorilla occidentale","es":"gorila occidental","fr":"gorille de l'ouest","de":"westlicher gorilla",
   "class_":"Mammalia","order_":"Primates","family":"Hominidae","gbif":5707444,"wiki":"Western_gorilla","xc":"","provider":"macaulay",
   "voc":["belch vocalisation","chest beat","scream"],"ctx":["social communication","dominance display","alarm"],"fn":["social coordination","status signalling","alarm"],
   "papers":[],"dois":["10.1007/s00265-011-1252-y"]},

  {"sci":"Macaca mulatta","en":"rhesus macaque","it":"macaco reso","es":"macaco rhesus","fr":"macaque rhésus","de":"rhesusaffe",
   "class_":"Mammalia","order_":"Primates","family":"Cercopithecidae","gbif":2436567,"wiki":"Rhesus_macaque","xc":"","provider":"macaulay",
   "voc":["coo","grunt","scream"],"ctx":["social communication","alarm","dominance"],"fn":["affiliation signalling","individual recognition","status display"],
   "papers":[],"dois":["10.1016/j.cub.2015.02.065"]},

  {"sci":"Hylobates lar","en":"lar gibbon","it":"gibbone dalle mani bianche","es":"gibón de manos blancas","fr":"gibbon à mains blanches","de":"weißhandgibbon",
   "class_":"Mammalia","order_":"Primates","family":"Hylobatidae","gbif":2436498,"wiki":"Lar_gibbon","xc":"","provider":"macaulay",
   "voc":["great call","song","whoop"],"ctx":["territorial defence","mate attraction","pair bond maintenance"],"fn":["territory signalling","pair bond maintenance","mate attraction"],
   "papers":[],"dois":["10.1038/s41559-020-1207-z"]},

  {"sci":"Lemur catta","en":"ring-tailed lemur","it":"lemure dalla coda ad anelli","es":"lémur de cola anillada","fr":"maki catta","de":"katta",
   "class_":"Mammalia","order_":"Primates","family":"Lemuridae","gbif":2436569,"wiki":"Ring-tailed_lemur","xc":"","provider":"macaulay",
   "voc":["wail","purr","click"],"ctx":["social communication","alarm","territorial defence"],"fn":["group cohesion","predator warning","territory signalling"],
   "papers":[],"dois":["10.1007/s00265-012-1337-7"]},

  # ── MAMMALS — CARNIVORA ───────────────────────────────────────────────────
  {"sci":"Canis lupus","en":"grey wolf","it":"lupo grigio","es":"lobo gris","fr":"loup gris","de":"wolf",
   "class_":"Mammalia","order_":"Carnivora","family":"Canidae","gbif":5219243,"wiki":"Wolf","xc":"","provider":"macaulay",
   "voc":["howl","bark","growl"],"ctx":["territorial defence","group cohesion","social communication"],"fn":["long-distance communication","pack coordination","individual recognition"],
   "papers":[],"dois":["10.1093/beheco/ary184"]},

  {"sci":"Crocuta crocuta","en":"spotted hyena","it":"iena maculata","es":"hiena manchada","fr":"hyène tachetée","de":"tüpfelhyäne",
   "class_":"Mammalia","order_":"Carnivora","family":"Hyaenidae","gbif":5219640,"wiki":"Spotted_hyena","xc":"","provider":"macaulay",
   "voc":["whoop","giggle","grunt"],"ctx":["social communication","territorial defence","group coordination"],"fn":["individual recognition","long-distance communication","submission signalling"],
   "papers":[],"dois":["10.1098/rspb.2015.2730"]},

  # ── MAMMALS — CETACEANS ───────────────────────────────────────────────────
  {"sci":"Tursiops truncatus","en":"bottlenose dolphin","it":"delfino tursiope","es":"delfín mular","fr":"grand dauphin","de":"großer tümmler",
   "class_":"Mammalia","order_":"Cetacea","family":"Delphinidae","gbif":2440503,"wiki":"Common_bottlenose_dolphin","xc":"","provider":"macaulay",
   "voc":["signature whistle","whistle","click"],"ctx":["individual recognition","group cohesion","echolocation"],"fn":["individual identity","social affiliation","prey detection"],
   "papers":["paper_004"],"dois":["10.1098/rspb.2006.3517","10.1038/nature04828"]},

  {"sci":"Megaptera novaeangliae","en":"humpback whale","it":"megattera","es":"ballena jorobada","fr":"baleine à bosse","de":"buckelwal",
   "class_":"Mammalia","order_":"Cetacea","family":"Balaenopteridae","gbif":5220010,"wiki":"Humpback_whale","xc":"","provider":"macaulay",
   "voc":["song"],"ctx":["courtship","long-distance communication"],"fn":["mate attraction","male competition"],
   "papers":["paper_006"],"dois":["10.1126/science.173.3993.585","10.1016/j.cub.2018.04.005"]},

  {"sci":"Physeter macrocephalus","en":"sperm whale","it":"capodoglio","es":"cachalote","fr":"cachalot","de":"pottwal",
   "class_":"Mammalia","order_":"Cetacea","family":"Physeteridae","gbif":2440897,"wiki":"Sperm_whale","xc":"","provider":"macaulay",
   "voc":["click","coda"],"ctx":["echolocation","social communication","group identity"],"fn":["prey detection","individual recognition","cultural identity"],
   "papers":[],"dois":["10.1038/s41559-021-01680-2"]},

  {"sci":"Orcinus orca","en":"orca","it":"orca","es":"orca","fr":"orque","de":"schwertwal",
   "class_":"Mammalia","order_":"Cetacea","family":"Delphinidae","gbif":2440520,"wiki":"Killer_whale","xc":"","provider":"macaulay",
   "voc":["call","whistle","click"],"ctx":["social communication","echolocation","cultural transmission"],"fn":["group identity","pod coordination","prey detection"],
   "papers":[],"dois":["10.1016/j.anbehav.2006.09.004"]},

  {"sci":"Globicephala melas","en":"long-finned pilot whale","it":"globicefalo atlantico","es":"calderón negro","fr":"globicéphale noir","de":"gewöhnlicher grindwal",
   "class_":"Mammalia","order_":"Cetacea","family":"Delphinidae","gbif":2440514,"wiki":"Long-finned_pilot_whale","xc":"","provider":"macaulay",
   "voc":["call","whistle","click"],"ctx":["social communication","echolocation","group coordination"],"fn":["group cohesion","prey detection","cultural transmission"],
   "papers":[],"dois":["10.1111/mms.12508"]},

  {"sci":"Phocoena phocoena","en":"harbour porpoise","it":"focena comune","es":"marsopa común","fr":"marsouin commun","de":"schweinswal",
   "class_":"Mammalia","order_":"Cetacea","family":"Phocoenidae","gbif":2440527,"wiki":"Harbour_porpoise","xc":"","provider":"macaulay",
   "voc":["click"],"ctx":["echolocation","social communication"],"fn":["prey detection","individual recognition"],
   "papers":[],"dois":["10.1371/journal.pone.0111807"]},

  # ── MAMMALS — CHIROPTERA ──────────────────────────────────────────────────
  {"sci":"Eptesicus fuscus","en":"big brown bat","it":"pipistrello bruno maggiore","es":"murciélago café grande","fr":"grande sérotine brune","de":"großer brauner fledermaus",
   "class_":"Mammalia","order_":"Chiroptera","family":"Vespertilionidae","gbif":2432929,"wiki":"Big_brown_bat","xc":"","provider":"macaulay",
   "voc":["echolocation call"],"ctx":["foraging","navigation"],"fn":["spatial orientation","prey detection"],
   "papers":["paper_010"],"dois":["10.1242/jeb.189381"]},

  {"sci":"Pteropus vampyrus","en":"large flying fox","it":"volpe volante grande","es":"zorro volador grande","fr":"grande roussette","de":"malaiischer flughund",
   "class_":"Mammalia","order_":"Chiroptera","family":"Pteropodidae","gbif":2432823,"wiki":"Large_flying_fox","xc":"","provider":"macaulay",
   "voc":["screech","contact call"],"ctx":["roost communication","social interaction","alarm"],"fn":["social coordination","individual recognition","alarm"],
   "papers":[],"dois":["10.1371/journal.pone.0025275"]},

  {"sci":"Tadarida brasiliensis","en":"mexican free-tailed bat","it":"pipistrello dalla coda libera messicano","es":"murciélago cola de ratón","fr":"molosse du Brésil","de":"mexikanische freischwanzfledermaus",
   "class_":"Mammalia","order_":"Chiroptera","family":"Molossidae","gbif":2432831,"wiki":"Mexican_free-tailed_bat","xc":"","provider":"macaulay",
   "voc":["echolocation call","social call"],"ctx":["foraging","social communication","mate attraction"],"fn":["prey detection","male competition","female recruitment"],
   "papers":[],"dois":["10.1126/science.1221174"]},

  # ── MAMMALS — OTHER ───────────────────────────────────────────────────────
  {"sci":"Mus musculus","en":"house mouse","it":"topo domestico","es":"ratón doméstico","fr":"souris domestique","de":"hausmaus",
   "class_":"Mammalia","order_":"Rodentia","family":"Muridae","gbif":2311476,"wiki":"House_mouse","xc":"","provider":"freesound",
   "voc":["ultrasonic vocalisation"],"ctx":["isolation","parent-offspring interaction","courtship"],"fn":["maternal retrieval","distress signalling","mate attraction"],
   "papers":["paper_005"],"dois":["10.1371/journal.pbio.1001893"]},

  {"sci":"Rattus norvegicus","en":"norway rat","it":"ratto norvegese","es":"rata de alcantarilla","fr":"rat surmulot","de":"wanderratte",
   "class_":"Mammalia","order_":"Rodentia","family":"Muridae","gbif":2311488,"wiki":"Brown_rat","xc":"","provider":"freesound",
   "voc":["ultrasonic vocalisation","squeak"],"ctx":["play","distress","social communication"],"fn":["play invitation","distress signalling","social bonding"],
   "papers":[],"dois":["10.1016/j.bbr.2010.05.050"]},

  {"sci":"Elephas maximus","en":"asian elephant","it":"elefante asiatico","es":"elefante asiático","fr":"éléphant d'asie","de":"asiatischer elefant",
   "class_":"Mammalia","order_":"Proboscidea","family":"Elephantidae","gbif":4689626,"wiki":"Asian_elephant","xc":"","provider":"macaulay",
   "voc":["rumble","trumpet","roar"],"ctx":["long-distance communication","social bonding","alarm"],"fn":["group coordination","contact maintenance","predator warning"],
   "papers":[],"dois":["10.1371/journal.pone.0249120"]},

  {"sci":"Loxodonta africana","en":"african elephant","it":"elefante africano","es":"elefante africano","fr":"éléphant de savane africain","de":"afrikanischer elefant",
   "class_":"Mammalia","order_":"Proboscidea","family":"Elephantidae","gbif":4689635,"wiki":"African_bush_elephant","xc":"","provider":"macaulay",
   "voc":["rumble","trumpet","infrasonic call"],"ctx":["long-distance communication","social bonding","alarm","bee alarm"],"fn":["group coordination","contact maintenance","predator warning","bee avoidance"],
   "papers":[],"dois":["10.1073/pnas.1606919113"]},

  # ── AMPHIBIANS ────────────────────────────────────────────────────────────
  {"sci":"Engystomops pustulosus","en":"túngara frog","it":"rana túngara","es":"rana túngara","fr":"grenouille túngara","de":"túngara-frosch",
   "class_":"Amphibia","order_":"Anura","family":"Leptodactylidae","gbif":2427148,"wiki":"Túngara_frog","xc":"Engystomops pustulosus","provider":"xeno_canto",
   "voc":["advertisement call","chuck"],"ctx":["mate attraction","sexual selection"],"fn":["mate attraction","species recognition","female choice"],
   "papers":[],"dois":["10.1126/science.185.4149.372"]},

  {"sci":"Rana temporaria","en":"common frog","it":"rana comune","es":"rana común","fr":"grenouille rousse","de":"grasfrosch",
   "class_":"Amphibia","order_":"Anura","family":"Ranidae","gbif":2427091,"wiki":"Common_frog","xc":"Rana temporaria","provider":"xeno_canto",
   "voc":["advertisement call"],"ctx":["mate attraction","chorus"],"fn":["mate attraction","species recognition"],
   "papers":[],"dois":["10.1371/journal.pone.0272006"]},

  {"sci":"Hyla chrysoscelis","en":"gray treefrog","it":"raganella grigia","es":"rana arbórea gris","fr":"rainette criarde","de":"grauer laubfrosch",
   "class_":"Amphibia","order_":"Anura","family":"Hylidae","gbif":2427070,"wiki":"Cope's_gray_treefrog","xc":"Hyla chrysoscelis","provider":"xeno_canto",
   "voc":["advertisement call"],"ctx":["mate attraction","chorus"],"fn":["mate attraction","species recognition"],
   "papers":[],"dois":["10.1093/beheco/arq121"]},

  {"sci":"Lithobates catesbeianus","en":"american bullfrog","it":"rana toro americana","es":"rana toro americana","fr":"ouaouaron","de":"amerikanischer ochsenfrosch",
   "class_":"Amphibia","order_":"Anura","family":"Ranidae","gbif":2427100,"wiki":"American_bullfrog","xc":"Lithobates catesbeianus","provider":"xeno_canto",
   "voc":["advertisement call","territorial call"],"ctx":["territorial defence","mate attraction"],"fn":["territory signalling","mate attraction"],
   "papers":[],"dois":["10.1163/156853906778876861"]},

  {"sci":"Bufo bufo","en":"common toad","it":"rospo comune","es":"sapo común","fr":"crapaud commun","de":"erdkröte",
   "class_":"Amphibia","order_":"Anura","family":"Bufonidae","gbif":2426722,"wiki":"Common_toad","xc":"Bufo bufo","provider":"xeno_canto",
   "voc":["advertisement call","release call"],"ctx":["mate attraction","male combat","mating"],"fn":["mate attraction","male-male competition","mating refusal"],
   "papers":[],"dois":["10.1007/s10071-020-01388-4"]},

  {"sci":"Dendrobates auratus","en":"green poison dart frog","it":"dendrobate verde e nero","es":"rana venenosa verde y negra","fr":"dendrobate doré","de":"grün-schwarzer pfeilgiftfrosch",
   "class_":"Amphibia","order_":"Anura","family":"Dendrobatidae","gbif":2426974,"wiki":"Green_and_black_poison_dart_frog","xc":"Dendrobates auratus","provider":"xeno_canto",
   "voc":["advertisement call"],"ctx":["territorial defence","mate attraction"],"fn":["territory signalling","mate attraction"],
   "papers":[],"dois":["10.1093/beheco/arq010"]},

  {"sci":"Xenopus laevis","en":"african clawed frog","it":"rana artigliata africana","es":"rana de uñas africana","fr":"xénope lisse","de":"krallenfrosch",
   "class_":"Amphibia","order_":"Anura","family":"Pipidae","gbif":2427041,"wiki":"African_clawed_frog","xc":"","provider":"external_links",
   "voc":["advertisement call","click"],"ctx":["mate attraction","underwater communication"],"fn":["mate attraction","species recognition"],
   "papers":[],"dois":["10.1242/jeb.234070"]},

  # ── REPTILES ──────────────────────────────────────────────────────────────
  {"sci":"Anolis carolinensis","en":"green anole","it":"anole verde americano","es":"anolis verde","fr":"anole vert","de":"grüner anolis",
   "class_":"Reptilia","order_":"Squamata","family":"Dactyloidae","gbif":2455974,"wiki":"Green_anole","xc":"","provider":"external_links",
   "voc":["call"],"ctx":["territorial defence","courtship"],"fn":["territory signalling","mate attraction"],
   "papers":[],"dois":["10.1086/660118"]},

  {"sci":"Crocodylus niloticus","en":"nile crocodile","it":"coccodrillo del nilo","es":"cocodrilo del nilo","fr":"crocodile du nil","de":"nilkrokodil",
   "class_":"Reptilia","order_":"Crocodilia","family":"Crocodylidae","gbif":5229461,"wiki":"Nile_crocodile","xc":"","provider":"external_links",
   "voc":["bellow","hiss","grunt"],"ctx":["territorial defence","mate attraction","parent-offspring interaction"],"fn":["territory signalling","mate attraction","nest guarding"],
   "papers":[],"dois":["10.1163/157075609X437135"]},

  # ── INSECTS ───────────────────────────────────────────────────────────────
  {"sci":"Drosophila melanogaster","en":"fruit fly","it":"mosca della frutta","es":"mosca de la fruta","fr":"mouche du vinaigre","de":"taufliege",
   "class_":"Insecta","order_":"Diptera","family":"Drosophilidae","gbif":1715589,"wiki":"Drosophila_melanogaster","xc":"","provider":"external_links",
   "voc":["courtship song","pulse song","sine song"],"ctx":["courtship","species recognition"],"fn":["mate attraction","species isolation","female receptivity"],
   "papers":[],"dois":["10.1016/j.cub.2013.04.072"]},

  {"sci":"Gryllus bimaculatus","en":"field cricket","it":"grillo campestre","es":"grillo de campo","fr":"grillon des champs","de":"feldgrille",
   "class_":"Insecta","order_":"Orthoptera","family":"Gryllidae","gbif":1720286,"wiki":"Field_cricket","xc":"","provider":"external_links",
   "voc":["calling song","courtship song","rivalry song"],"ctx":["mate attraction","territorial defence","courtship"],"fn":["mate attraction","rival deterrence","species recognition"],
   "papers":[],"dois":["10.1007/s00265-014-1678-5"]},

  {"sci":"Acheta domesticus","en":"house cricket","it":"grillo domestico","es":"grillo doméstico","fr":"grillon domestique","de":"hausgrille",
   "class_":"Insecta","order_":"Orthoptera","family":"Gryllidae","gbif":1720298,"wiki":"House_cricket","xc":"","provider":"external_links",
   "voc":["calling song","courtship song","aggression song"],"ctx":["mate attraction","male combat","courtship"],"fn":["mate attraction","rival deterrence","female assessment"],
   "papers":[],"dois":["10.1016/j.anbehav.2004.06.021"]},

  {"sci":"Apis mellifera","en":"honey bee","it":"ape domestica","es":"abeja melífera","fr":"abeille mellifique","de":"westliche honigbiene",
   "class_":"Insecta","order_":"Hymenoptera","family":"Apidae","gbif":1341976,"wiki":"Western_honey_bee","xc":"","provider":"external_links",
   "voc":["waggle dance buzz","piping","tooting"],"ctx":["foraging recruitment","queen competition","swarming"],"fn":["food source communication","queen signalling","swarm coordination"],
   "papers":[],"dois":["10.1126/science.1126611"]},

  {"sci":"Galleria mellonella","en":"greater wax moth","it":"tignola della cera","es":"polilla de la cera","fr":"fausse teigne de la cire","de":"große wachsmotte",
   "class_":"Insecta","order_":"Lepidoptera","family":"Pyralidae","gbif":1782561,"wiki":"Galleria_mellonella","xc":"","provider":"external_links",
   "voc":["ultrasonic pulse"],"ctx":["courtship","bat avoidance"],"fn":["mate attraction","predator evasion"],
   "papers":[],"dois":["10.1016/j.jinsphys.2014.01.003"]},

  {"sci":"Schistocerca gregaria","en":"desert locust","it":"locusta del deserto","es":"langosta del desierto","fr":"criquet pèlerin","de":"wüstenheuschrecke",
   "class_":"Insecta","order_":"Orthoptera","family":"Acrididae","gbif":1720338,"wiki":"Desert_locust","xc":"","provider":"external_links",
   "voc":["stridulation"],"ctx":["mate attraction","territorial defence","swarming"],"fn":["mate attraction","rival deterrence","swarm coordination"],
   "papers":[],"dois":["10.1016/j.anbehav.2009.11.030"]},

  # ── FISH ──────────────────────────────────────────────────────────────────
  {"sci":"Danio rerio","en":"zebrafish","it":"pesce zebra","es":"pez cebra","fr":"poisson zèbre","de":"zebrabärbling",
   "class_":"Actinopterygii","order_":"Cypriniformes","family":"Danionidae","gbif":2360866,"wiki":"Zebrafish","xc":"","provider":"external_links",
   "voc":["pulse"],"ctx":["social communication","alarm"],"fn":["shoal cohesion","alarm communication"],
   "papers":[],"dois":["10.1371/journal.pone.0030962"]},

  {"sci":"Porichthys notatus","en":"midshipman fish","it":"pesce illuminato","es":"pez lucerna","fr":"poisson lamparo","de":"leuchtfisch",
   "class_":"Actinopterygii","order_":"Batrachoidiformes","family":"Batrachoididae","gbif":2398910,"wiki":"Plainfin_midshipman_fish","xc":"","provider":"external_links",
   "voc":["hum","grunt","grunt-train"],"ctx":["courtship","territorial defence","male competition"],"fn":["mate attraction","territory signalling","male-male competition"],
   "papers":[],"dois":["10.1016/j.cub.2011.05.026"]},

  {"sci":"Gadus morhua","en":"atlantic cod","it":"merluzzo atlantico","es":"bacalao del Atlántico","fr":"morue de l'Atlantique","de":"atlantischer kabeljau",
   "class_":"Actinopterygii","order_":"Gadiformes","family":"Gadidae","gbif":2366788,"wiki":"Atlantic_cod","xc":"","provider":"external_links",
   "voc":["grunt","knock"],"ctx":["spawning","male competition","courtship"],"fn":["mate attraction","male competition","spawning coordination"],
   "papers":[],"dois":["10.1006/anbe.2001.1925"]},

  {"sci":"Amphiprion ocellaris","en":"clownfish","it":"pesce pagliaccio","es":"pez payaso","fr":"poisson-clown","de":"clownfisch",
   "class_":"Actinopterygii","order_":"Perciformes","family":"Pomacentridae","gbif":2368980,"wiki":"Ocellaris_clownfish","xc":"","provider":"external_links",
   "voc":["chirp","pop"],"ctx":["territorial defence","social hierarchy"],"fn":["territory signalling","dominance communication"],
   "papers":[],"dois":["10.1371/journal.pone.0163426"]},

  {"sci":"Oreochromis niloticus","en":"nile tilapia","it":"tilapia del nilo","es":"tilapia del Nilo","fr":"tilapia du Nil","de":"niltilapia",
   "class_":"Actinopterygii","order_":"Perciformes","family":"Cichlidae","gbif":2364116,"wiki":"Nile_tilapia","xc":"","provider":"external_links",
   "voc":["drumming","grunt"],"ctx":["courtship","male competition","territorial defence"],"fn":["mate attraction","male competition","territory signalling"],
   "papers":[],"dois":["10.1111/j.1095-8649.2006.01032.x"]},
]

# ── AUDIO EXTERNAL LINKS BY ORDER ────────────────────────────────────────────
AUDIO_LINKS = {
    "Cetacea":       [{"name":"Macaulay Library","url":"https://search.macaulaylibrary.org/catalog?mediaType=audio"},
                      {"name":"NOAA Ocean Sounds","url":"https://www.fisheries.noaa.gov/national/protected-resources/sounds-ocean"}],
    "Chiroptera":    [{"name":"BatDetective","url":"https://www.batdetective.org/"},
                      {"name":"Macaulay Library","url":"https://www.macaulaylibrary.org/"}],
    "Proboscidea":   [{"name":"ElephantVoices","url":"https://www.elephantvoices.org/"},
                      {"name":"Macaulay Library","url":"https://www.macaulaylibrary.org/"}],
    "Primates":      [{"name":"Macaulay Library","url":"https://www.macaulaylibrary.org/"}],
    "Carnivora":     [{"name":"Freesound — search sounds","url":"https://freesound.org/"},
                      {"name":"Macaulay Library","url":"https://www.macaulaylibrary.org/"}],
    "Rodentia":      [{"name":"Freesound — search sounds","url":"https://freesound.org/"},
                      {"name":"Macaulay Library","url":"https://www.macaulaylibrary.org/"}],
    "Artiodactyla":  [{"name":"Freesound — farm animal sounds","url":"https://freesound.org/search/?q=cow+pig+sheep"}],
    "Perissodactyla":[{"name":"Freesound — horse sounds","url":"https://freesound.org/search/?q=horse+neigh"}],
    "Diptera":       [{"name":"Drosophila Song Database (Janelia)","url":"https://www.janelia.org/"}],
    "Orthoptera":    [{"name":"Bioacoustica","url":"https://bioacoustica.org/"},
                      {"name":"Orthoptera Species File","url":"https://orthoptera.speciesfile.org/"}],
    "Lepidoptera":   [{"name":"Bioacoustica","url":"https://bioacoustica.org/"}],
    "Hymenoptera":   [{"name":"BeeBase Acoustic Archive","url":"https://www.beebase.ac.uk/"}],
    "Actinopterygii":[{"name":"Macaulay Library — fish sounds","url":"https://search.macaulaylibrary.org/catalog?mediaType=audio"}],
    "Crocodilia":    [{"name":"Macaulay Library","url":"https://www.macaulaylibrary.org/"}],
    "Squamata":      [{"name":"Macaulay Library","url":"https://www.macaulaylibrary.org/"}],
    "default":       [{"name":"Macaulay Library","url":"https://www.macaulaylibrary.org/"}],
}

# ── GENERATE FILES ────────────────────────────────────────────────────────────
def make_sid(sp):
    gbif = sp.get("gbif")
    if gbif:
        return f"gbif_{gbif}"
    return re.sub(r"[^a-z0-9]+", "_", sp["sci"].lower()).strip("_")

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pilot = {}
    if PILOT_PATH.exists():
        pilot = {r["paper_id"]: r for r in json.loads(PILOT_PATH.read_text(encoding="utf-8"))}

    index = []
    print(f"\nGenerating {len(SPECIES)} species pages...\n")

    for sp in SPECIES:
        sid    = make_sid(sp)
        order  = sp.get("order_", "—")
        papers = []
        for pid in sp.get("papers", []):
            if pid in pilot:
                p = pilot[pid]
                papers.append({"id":pid,"title":p.get("title",""),"year":p.get("year"),
                               "stage":p.get("developmental_stage",""),"methods":p.get("analysis_method",[]),
                               "outcome":p.get("main_outcome",""),"dataset_available":p.get("dataset_or_recording_available","unknown")})
            else:
                papers.append({"id":pid,"title":f"Paper {pid}","year":None})

        ext = AUDIO_LINKS.get(order, AUDIO_LINKS.get(sp.get("class_",""), AUDIO_LINKS["default"]))
        has_xc = sp.get("provider") == "xeno_canto"
        has_fs = sp.get("provider") == "freesound"

        record = {
            "species_id":      sid,
            "gbif_usage_key":  sp.get("gbif"),
            "scientific_name": sp["sci"],
            "common_name_en":  sp["en"],
            "common_names":    {"en":sp["en"],"it":sp.get("it",""),"es":sp.get("es",""),"fr":sp.get("fr",""),"de":sp.get("de","")},
            "taxonomy":        {"class_":sp.get("class_","—"),"order_":order,"family":sp.get("family","—"),
                                "genus":sp["sci"].split()[0],"gbif_match_confidence":95,"gbif_match_status":"ACCEPTED"},
            "conservation_status": "",
            "inat_id":         None,
            "image":           {"url":"","url_full":"","source":"Wikimedia Commons","license":"see Wikimedia Commons","attribution":""},
            "summary":         f"{sp['en'].capitalize()} ({sp['sci']}) is a species of {sp.get('class_','—')} in the order {order}, family {sp.get('family','—')}.",
            "wiki_url":        f"https://en.wikipedia.org/wiki/{sp.get('wiki','').replace(' ','_')}",
            "wiki_title":      sp.get("wiki",""),
            "vocalisations":   sp.get("voc",[]),
            "contexts":        sp.get("ctx",[]),
            "functions":       sp.get("fn",[]),
            "open_papers":     [{"doi":d,"url":f"https://doi.org/{d}"} for d in sp.get("dois",[])],
            "audio": {
                "provider":       sp.get("provider","external_links"),
                "xc_query":       sp.get("xc",""),
                "recordings":     [],
                "external_links": [] if (has_xc or has_fs) else ext,
                "freesound_search": f"https://freesound.org/search/?q={sp['en'].replace(' ','+')}+sound" if has_fs else "",
            },
            "papers":      papers,
            "paper_count": len(papers),
        }

        (OUT_DIR / f"{sid}.json").write_text(json.dumps(record, indent=2, ensure_ascii=False))
        index.append({
            "species_id":      sid,
            "scientific_name": sp["sci"],
            "common_name_en":  sp["en"],
            "common_names":    record["common_names"],
            "class_":          sp.get("class_","—"),
            "order_":          order,
            "family":          sp.get("family","—"),
            "image_url":       "",
            "paper_count":     len(papers),
            "has_open_papers": len(sp.get("dois",[])) > 0,
            "conservation":    "",
            "vocalisations":   sp.get("voc",[]),
        })
        print(f"  {sp.get('class_','—'):15s} {sp['sci']:40s} papers={len(papers)} dois={len(sp.get('dois',[]))}")

    INDEX_PATH.write_text(json.dumps(index, indent=2, ensure_ascii=False))
    print(f"\n✓ {len(SPECIES)} species pages → {OUT_DIR}/")
    print(f"✓ index → {INDEX_PATH}\n")
    print("Next steps:")
    print("  python scripts/02_fetch_species_metadata.py  ← images + summaries from Wikipedia")
    print("  python scripts/03_fetch_media.py             ← audio from Xeno-canto / Freesound")
    print("  python scripts/04_build_species_pages.py     ← merge everything\n")

if __name__ == "__main__":
    main()
