"""Schema for LLM-extracted paper data."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict

# The 16 themes from the Zoe.Logos-Graph taxonomy
THEMES = [
    'vocal_learning', 'referential', 'syntax', 'individual_recognition',
    'cultural_transmission', 'turn_taking', 'honest_signalling',
    'echolocation', 'infrasound', 'dialects', 'emotion', 'multimodal',
    'deception', 'parent_offspring', 'alarm', 'cooperation',
]

STUDY_TYPES = ('descriptive', 'experimental', 'comparative',
               'neuroscience', 'review', 'meta_analysis',
               'computational', 'other')

RELEVANCE_LEVELS = ('low', 'medium', 'high')


@dataclass
class ExtractedPaper:
    """Structured paper extraction."""
    # Identity (from source data, not LLM)
    doi: str = ''
    pmid: str = ''
    title: str = ''
    year: int | None = None
    venue: str = ''
    authors: list[str] = field(default_factory=list)

    # LLM-extracted fields
    research_question: str = ''                            # 1-2 sentences
    species_studied: list[str] = field(default_factory=list)
    methods_recording_type: str = ''                       # field/lab/passive
    methods_sample_size: str = ''                          # "N=15 males"
    methods_setting: str = ''                              # wild/captive/lab
    methods_analysis: str = ''                             # short label
    key_findings: str = ''                                 # 2 sentences
    implications: str = ''                                 # 1 sentence
    limitations: str = ''                                  # 0-2 sentences
    themes: list[str] = field(default_factory=list)        # subset of THEMES
    study_type: str = ''                                   # one of STUDY_TYPES
    relevance: str = ''                                    # low/medium/high
    confidence: float = 0.0                                # 0..1

    # Provenance
    sources: list[str] = field(default_factory=list)
    cited_by: int = 0
    influential: int = 0
    is_oa: bool = False
    score: float = 0.0
    target_species: str = ''

    def to_dict(self) -> dict:
        return asdict(self)


# JSON Schema string used in the LLM prompt
EXTRACTION_SCHEMA = """{
  "research_question":     "string (1-2 sentences, the question the paper asks)",
  "species_studied":       ["string (scientific names of species actually studied, not just mentioned)"],
  "methods_recording_type": "string (one of: field_recording / lab_playback / passive_monitoring / archival / experimental / not_acoustic / unspecified)",
  "methods_sample_size":   "string (e.g. 'N=15 adult males' or 'unspecified')",
  "methods_setting":       "string (one of: wild / captive / laboratory / mixed / unspecified)",
  "methods_analysis":      "string (very short label, e.g. 'spectrographic analysis', 'machine learning classifier', 'playback experiment')",
  "key_findings":          "string (2 sentences max, the central results)",
  "implications":          "string (1 sentence max, what it means for the field)",
  "limitations":           "string (0-2 sentences, only if explicitly stated)",
  "themes":                ["array of theme ids from: vocal_learning, referential, syntax, individual_recognition, cultural_transmission, turn_taking, honest_signalling, echolocation, infrasound, dialects, emotion, multimodal, deception, parent_offspring, alarm, cooperation"],
  "study_type":            "string (one of: descriptive, experimental, comparative, neuroscience, review, meta_analysis, computational, other)",
  "relevance":             "string (one of: low, medium, high — how central this paper is to bioacoustics/animal vocal communication of the target species)",
  "confidence":            "number 0..1 (how confident the extraction is given the abstract)"
}"""
