"""
normalisation.py
----------------
Species name and behaviour term normalisation for Zoe.Logos-Graph.

Normalisation ensures that equivalent terms extracted from different papers
map to the same node in the knowledge graph. This is essential for
surfacing cross-paper connections.
"""

from __future__ import annotations

import re
from typing import Optional

# ---------------------------------------------------------------------------
# Species common name normalisation
# ---------------------------------------------------------------------------

# Maps variant spellings / informal names → canonical common name
# Convention: all common names are lowercase throughout.
# Multi-word names follow standard zoological usage (all lowercase).
# Do not use scientific names as values in this map.
SPECIES_COMMON_NAME_MAP: dict[str, str] = {
    # Passerines
    "zebra finch": "zebra finch",
    "taeniopygia guttata": "zebra finch",
    "bengalese finch": "bengalese finch",
    "society finch": "bengalese finch",
    "canary": "domestic canary",
    "domestic canary": "domestic canary",
    "great tit": "great tit",
    "blue tit": "blue tit",
    "long-tailed tit": "long-tailed tit",
    "chaffinch": "chaffinch",
    "common chaffinch": "chaffinch",
    "starling": "european starling",
    "european starling": "european starling",
    "crow": "carrion crow",
    "carrion crow": "carrion crow",
    "raven": "common raven",
    "common raven": "common raven",
    "japanese tit": "japanese tit",
    # Galliformes
    "domestic chick": "domestic chick",
    "chicken": "domestic chick",
    "gallus gallus domesticus": "domestic chick",
    "japanese quail": "japanese quail",
    "quail": "japanese quail",
    # Primates
    "rhesus macaque": "rhesus macaque",
    "rhesus monkey": "rhesus macaque",
    "chimpanzee": "chimpanzee",
    "common chimpanzee": "chimpanzee",
    "bonobo": "bonobo",
    "marmoset": "common marmoset",
    "common marmoset": "common marmoset",
    "vervet monkey": "vervet monkey",
    # Cetaceans
    "bottlenose dolphin": "bottlenose dolphin",
    "common bottlenose dolphin": "bottlenose dolphin",
    "humpback whale": "humpback whale",
    "killer whale": "orca",
    "orca": "orca",
    # Bats
    "greater horseshoe bat": "greater horseshoe bat",
    "big brown bat": "big brown bat",
    "egyptian fruit bat": "egyptian fruit bat",
    # Anurans
    "túngara frog": "túngara frog",
    "tungara frog": "túngara frog",
    "gray tree frog": "gray tree frog",
    "grey tree frog": "gray tree frog",
    # Rodents
    "house mouse": "house mouse",
    # Insects
    "drosophila": "fruit fly",       # drosophila is a genus, map to common name
    "fruit fly": "fruit fly",
    "field cricket": "field cricket",
}


def normalise_common_name(name: str) -> str:
    """Return the canonical common name for a species, or the original lowercased."""
    if not name or name.lower() in ("unknown", "multiple species", "various"):
        return name
    return SPECIES_COMMON_NAME_MAP.get(name.lower().strip(), name.strip())


# ---------------------------------------------------------------------------
# Scientific name normalisation
# ---------------------------------------------------------------------------

def normalise_scientific_name(name: str) -> str:
    """
    Capitalise the genus, lowercase the species epithet.
    E.g. 'gallus gallus domesticus' -> 'Gallus gallus domesticus'
    """
    if not name or name.lower() == "unknown":
        return name
    parts = name.strip().split()
    if not parts:
        return name
    return " ".join([parts[0].capitalize()] + [p.lower() for p in parts[1:]])


# ---------------------------------------------------------------------------
# Vocalisation type normalisation
# ---------------------------------------------------------------------------

VOCALISATION_MAP: dict[str, str] = {
    # Calls
    "call": "call",
    "calls": "call",
    "contact call": "contact call",
    "contact calls": "contact call",
    "alarm call": "alarm call",
    "alarm calls": "alarm call",
    "distress call": "distress call",
    "distress calls": "distress call",
    "food call": "food call",
    "recruitment call": "recruitment call",
    "isolation call": "isolation call",
    # Song
    "song": "song",
    "songs": "song",
    "subsong": "subsong",
    "plastic song": "plastic song",
    "crystallised song": "crystallised song",
    "crystallized song": "crystallised song",
    "directed song": "directed song",
    "undirected song": "undirected song",
    # Vocalisations
    "vocalisation": "vocalisation",
    "vocalization": "vocalisation",
    "vocalisations": "vocalisation",
    "vocalizations": "vocalisation",
    "syllable": "syllable",
    "syllables": "syllable",
    "motif": "motif",
    "motifs": "motif",
    "note": "note",
    "notes": "note",
    # Specialised
    "echolocation": "echolocation call",
    "echolocation call": "echolocation call",
    "click": "click",
    "clicks": "click",
    "whistle": "whistle",
    "whistles": "whistle",
    "signature whistle": "signature whistle",
    "chirp": "chirp",
    "chirps": "chirp",
    "peep": "peep",
    "peeps": "peep",
    "grunt": "grunt",
    "grunts": "grunt",
    "screech": "screech",
    "screeches": "screech",
    "ultrasonic vocalisation": "ultrasonic vocalisation",
    "ultrasonic vocalization": "ultrasonic vocalisation",
    "usv": "ultrasonic vocalisation",
}


def normalise_vocalisation(v: str) -> str:
    """Return the canonical vocalisation type label."""
    return VOCALISATION_MAP.get(v.lower().strip(), v.lower().strip())


def normalise_vocalisation_list(items: list[str]) -> list[str]:
    """Normalise and deduplicate a list of vocalisation types."""
    seen = set()
    result = []
    for item in items:
        norm = normalise_vocalisation(item)
        if norm not in seen:
            seen.add(norm)
            result.append(norm)
    return result


# ---------------------------------------------------------------------------
# Behavioural context normalisation
# ---------------------------------------------------------------------------

CONTEXT_MAP: dict[str, str] = {
    "foraging": "foraging",
    "feeding": "foraging",
    "predator avoidance": "predator response",
    "predator response": "predator response",
    "anti-predator": "predator response",
    "anti predator": "predator response",
    "mate attraction": "mate attraction",
    "courtship": "courtship",
    "mating": "courtship",
    "territorial defence": "territorial defence",
    "territorial defense": "territorial defence",
    "territory": "territorial defence",
    "parent offspring": "parent-offspring interaction",
    "parent-offspring": "parent-offspring interaction",
    "parent-offspring interaction": "parent-offspring interaction",
    "social communication": "social communication",
    "early social communication": "early social communication",
    "group cohesion": "group cohesion",
    "flock cohesion": "group cohesion",
    "individual recognition": "individual recognition",
    "vocal learning": "vocal learning",
    "song learning": "vocal learning",
    "play": "play",
    "distress": "distress",
    "isolation": "isolation",
    "separation": "isolation",
}


def normalise_context(c: str) -> str:
    """Return the canonical behavioural context label."""
    return CONTEXT_MAP.get(c.lower().strip(), c.lower().strip())


def normalise_context_list(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        norm = normalise_context(item)
        if norm not in seen:
            seen.add(norm)
            result.append(norm)
    return result


# ---------------------------------------------------------------------------
# Full record normalisation
# ---------------------------------------------------------------------------

from src.schema import PaperRecord


def normalise_record(record: PaperRecord, cfg=None) -> PaperRecord:
    """
    Apply normalisation steps to a validated PaperRecord.
    cfg (ZoeConfig) controls which maps are applied.
    If cfg is None, all maps are applied (default behaviour).
    Returns a new PaperRecord with normalised fields.
    """
    data = record.model_dump()

    apply_species = True
    apply_voc = True
    apply_ctx = True

    if cfg is not None:
        apply_species = cfg.normalisation.apply_species_map
        apply_voc = cfg.normalisation.apply_vocalisation_map
        apply_ctx = cfg.normalisation.apply_context_map

    if apply_species:
        data["species_common_name"] = normalise_common_name(data["species_common_name"])
        data["species_scientific_name"] = normalise_scientific_name(data["species_scientific_name"])
    if apply_voc:
        data["vocalisation_type"] = normalise_vocalisation_list(data["vocalisation_type"])
    if apply_ctx:
        data["behavioural_context"] = normalise_context_list(data["behavioural_context"])

    return PaperRecord(**data)
