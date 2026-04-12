# Zoe.Logos-Graph — Annotation Guidelines v1

**Status:** stable for pilot  
**Schema version:** 1.0  
**Last updated:** 2025

---

## Governing principle

> Extract only what is supported by the abstract text.  
> Do not infer. Do not add domain knowledge. Do not speculate.

When in doubt: use `"unknown"`, leave a list empty `[]`, or note the ambiguity in `notes_uncertainty`.

---

## Field-by-field reference

---

### `paper_id`

A unique identifier for this record in the corpus.

**Format:** `paper_NNN` (zero-padded) or a DOI slug stripped of special characters.  
**Rules:**
- Must be unique across all records.
- Assign sequentially during batch annotation.
- For DOI-based IDs: `10.1038/s41586-024-07498-3` → `10_1038_s41586_2024_07498_3`

---

### `title`

Copy the full title exactly as it appears in the source.  
Do not truncate, paraphrase, or correct capitalisation.

---

### `year`

The publication year as an integer.  
Set to `null` if year is not available in the source metadata.

---

### `species_common_name`

The common English name of the focal species.

**Rules:**
- Use the most specific focal species. If the paper studies multiple species comparatively, use `"multiple species"`.
- Normalise to a canonical form: `"zebra finch"`, not `"Zebra Finch"` or `"ZF"`.
- Use `"unknown"` only if no species is named in the abstract.

| Abstract says | Use |
|---|---|
| "zebra finches (Taeniopygia guttata)" | `"zebra finch"` |
| "songbirds" (no species named) | `"unknown"` |
| "three corvid species" | `"multiple species"` |

---

### `species_scientific_name`

Full binomial (or trinomial for subspecies) in standard italicised form.

**Rules:**
- Capitalise genus, lowercase species epithet: `"Taeniopygia guttata"`, `"Gallus gallus domesticus"`.
- If the abstract names the species only by common name and you are certain of the scientific name, you may include it — but note the inference in `notes_uncertainty`.
- Use `"unknown"` if not determinable.

---

### `taxonomic_family`

Linnean family of the focal species. Examples: `"Estrildidae"`, `"Delphinidae"`, `"Muridae"`.  
Use `"unknown"` if uncertain.

---

### `developmental_stage`

The developmental stage of the subjects studied.

| Value | When to use |
|---|---|
| `embryo` | Pre-hatching or pre-birth subjects |
| `early-life` | Hatchling, nestling, pup, neonate, chick (post-hatching, pre-juvenile) |
| `juvenile` | Post-early-life but not yet sexually mature |
| `adult` | Sexually mature animals |
| `mixed` | Study explicitly includes multiple stages |
| `unknown` | Stage not stated or not determinable from the abstract |

**Note:** if the abstract mentions "juvenile" or "adult" explicitly, use that. If it says "hatchlings" or "pups", use `early-life`.

---

### `communication_domain`

| Value | When to use |
|---|---|
| `vocal` | Study primarily concerns vocal / acoustic signals |
| `multimodal` | Study explicitly combines vocal and non-vocal signals (e.g. visual display + calls) |
| `unknown` | Not clear from the abstract |

---

### `vocalisation_type`

A list of the types of vocalisation described in the abstract.

**Rules:**
- Normalise to lowercase consistent terms.
- Use specific types where named; do not use `"vocalisation"` alone if a more specific term is given.
- Common normalised terms: `"call"`, `"contact call"`, `"alarm call"`, `"distress call"`, `"food call"`, `"song"`, `"subsong"`, `"plastic song"`, `"crystallised song"`, `"directed song"`, `"undirected song"`, `"signature whistle"`, `"whistle"`, `"echolocation call"`, `"ultrasonic vocalisation"`, `"chirp"`, `"peep"`, `"grunt"`, `"syllable"`, `"motif"`.
- Deduplicate.
- Leave as `[]` only if no vocalisation type is named or inferable.

**Examples:**

| Abstract says | Use |
|---|---|
| "we recorded alarm calls" | `["alarm call"]` |
| "song and subsong were recorded" | `["song", "subsong"]` |
| "vocal behaviour was studied" | `["call"]` if general, `[]` if truly unspecified |
| "phee calls (contact calls)" | `["contact call"]` |

---

### `behavioural_context`

The contexts in which vocalisations are produced or elicited.

**Rules:**
- Normalise to lowercase descriptive phrases.
- Do not invent contexts not mentioned in the abstract.
- Common normalised contexts: `"foraging"`, `"predator response"`, `"courtship"`, `"territorial defence"`, `"parent-offspring interaction"`, `"early social communication"`, `"isolation"`, `"group cohesion"`, `"vocal learning"`, `"individual recognition"`, `"long-distance communication"`, `"navigation"`, `"play"`.

---

### `putative_function`

The communicative functions **attributed to the vocalisation by the paper**.

**Critical rule:** Only include functions the abstract itself proposes or tests. Do not add functions from your background knowledge.

**Examples:**

| Abstract says | Use |
|---|---|
| "calls may serve to maintain group cohesion" | `["group cohesion"]` |
| "alarm calls warn conspecifics of predators" | `["predator warning"]` |
| Abstract describes call structure but proposes no function | `[]` |

---

### `analysis_method`

All analytical or computational methods mentioned in the abstract.

**Rules:**
- Include both signal processing methods and statistical / ML methods.
- Normalise: `"spectrogram analysis"`, not `"spectrographic analysis"` or `"sonogram analysis"`.
- Named tools or algorithms count: `"UMAP"`, `"MUPET"`, `"SAP"`, `"hidden Markov model"`, `"random forest"`, `"DTW"` (as `"dynamic time warping"`).
- `"playback experiment"` is a method. `"acoustic recording"` is a method.
- Do not include `"statistics"` as a method unless no specific method is named.

---

### `main_outcome`

1–2 sentences summarising the main finding of the paper, **faithful to the abstract**.

**Rules:**
- Do not start with "This paper..." or "The study...".
- Do not add interpretation beyond what the abstract states.
- Keep under 250 characters where possible.
- If the abstract reports a null result, capture that.

**Good example:**  
`"Big brown bats dynamically adjust call duration and frequency sweep in response to obstacle density, demonstrating context-dependent echolocation plasticity."`

**Poor example (too interpretive):**  
`"The paper proves that bats have flexible cognition, which has implications for understanding the evolution of active sensing."`

---

### `dataset_or_recording_available`

| Value | When to use |
|---|---|
| `yes` | The abstract states that data or recordings are deposited, available, or accessible |
| `no` | The abstract explicitly states data are not available |
| `unknown` | No statement about data availability in the abstract |

Do not assume `yes` from general journal data-sharing policies. Only mark `yes` if the abstract says so.

---

### `dataset_name`

The name or identifier of the dataset or repository mentioned in the abstract.

**Rules:**
- Use the name as given: `"xeno-canto"`, `"Macaulay Library"`, `"Dryad"`, `"OSF"`, `"GBIF"`, `"NIST"`.
- If a specific accession or project ID is given, include it: `"Macaulay Library ML_Borneo_2021"`.
- Set to `null` if no dataset name is mentioned.
- If `dataset_name` is set, `dataset_or_recording_available` must be `"yes"`.

---

### `notes_uncertainty`

Free-text notes on any ambiguity, inference, or caveat in the extraction.

**Use when:**
- A field required inference not directly stated in the abstract
- The abstract is ambiguous about species, stage, or function
- You normalised a term that required judgment
- Any field value is uncertain

**Set to `null`** when the extraction is clean and unambiguous.

---

## Common annotation mistakes

| Mistake | Correct approach |
|---|---|
| Adding species from knowledge not in abstract | Only use what the abstract states |
| Including functions the abstract does not propose | Leave `putative_function` empty if no function is proposed |
| Writing a long `main_outcome` by copying the abstract | Summarise in 1–2 sentences in your own words |
| Setting `dataset_or_recording_available: "yes"` without a statement in the abstract | Use `"unknown"` unless the abstract says so |
| Using plural vocalisation terms (`"calls"`, `"songs"`) | Normalise to singular: `"call"`, `"song"` |
| Marking `developmental_stage: "adult"` because most animal studies use adults | Use `"unknown"` unless the abstract specifies |

---

## Inter-annotator agreement targets (pilot)

For a pilot corpus of 10 records annotated by two people:

| Field | Target agreement |
|---|---|
| `species_scientific_name` | ≥ 0.95 |
| `vocalisation_type` (Jaccard) | ≥ 0.80 |
| `behavioural_context` (Jaccard) | ≥ 0.75 |
| `putative_function` (Jaccard) | ≥ 0.70 |
| `developmental_stage` | ≥ 0.85 |
| `dataset_or_recording_available` | ≥ 0.90 |

Disagreements below target thresholds should trigger a guidelines update before proceeding to larger-scale annotation.

---

## Worked examples

### Example 1 — Clean extraction

**Abstract:**  
*"We recorded alarm calls from 32 adult vervet monkeys (Chlorocebus pygerythrus) in response to aerial (eagle) and terrestrial (leopard) predators. Calls were analysed using spectrogram analysis and linear discriminant analysis. Aerial predator calls had significantly higher peak frequency than terrestrial predator calls. Playback of aerial calls elicited tree-climbing, while terrestrial calls elicited bipedal scanning."*

**Correct extraction:**
```json
{
  "species_common_name": "vervet monkey",
  "species_scientific_name": "Chlorocebus pygerythrus",
  "developmental_stage": "adult",
  "vocalisation_type": ["alarm call"],
  "behavioural_context": ["predator response"],
  "putative_function": ["predator warning"],
  "analysis_method": ["spectrogram analysis", "linear discriminant analysis", "playback experiment"],
  "main_outcome": "Vervet monkey alarm calls differ acoustically by predator class; playback elicits class-appropriate anti-predator behaviour.",
  "notes_uncertainty": null
}
```

### Example 2 — Uncertain function, multiple species

**Abstract:**  
*"We compared the acoustic structure of contact calls in three corvid species using spectrogram cross-correlation. Call repertoire sizes differed across species but no clear acoustic convergence was detected within species pairs."*

**Correct extraction:**
```json
{
  "species_common_name": "multiple species",
  "species_scientific_name": "multiple",
  "taxonomic_family": "Corvidae",
  "developmental_stage": "unknown",
  "vocalisation_type": ["contact call"],
  "behavioural_context": ["group cohesion"],
  "putative_function": [],
  "analysis_method": ["spectrogram cross-correlation"],
  "main_outcome": "Repertoire sizes differ across three corvid species; no within-species acoustic convergence was detected.",
  "notes_uncertainty": "No function proposed in abstract. Behavioural context inferred from 'contact call' label; not explicitly stated."
}
```
