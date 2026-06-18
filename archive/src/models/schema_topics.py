"""
src/models/schema_topics.py
----------------------------
Pydantic model for research topic terms in Zoe.Logos.

## Conceptual distinction (critical for scientific precision)

  context  = observable behavioural situation in which a signal occurs
             (e.g. "predator response", "courtship", "group movement")

  function = inferred communicative role of the signal
             (e.g. "mate attraction", "predator warning")

  topic    = scientific/cognitive phenomenon that the paper investigates
             (e.g. "vocal learning", "individual recognition", "sensitive period")

A topic is NOT a context or a function. It is the research question or
cognitive capacity being studied. A single paper may address:

  signal = "contact call"
  context = "group movement"
  function = "group cohesion"
  topic = "individual recognition"   ← the scientific question being tested

Without this separation, "vocal learning" and "courtship" would sit in the
same context vocabulary, which is scientifically incoherent.

Loaded from: data/vocab/research_topic_terms.yaml
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ResearchTopicTerm(BaseModel):
    """
    A controlled vocabulary entry for a research topic or cognitive phenomenon.

    Topics are the scientific questions or capacities that a paper investigates.
    They are orthogonal to both context (the behavioural situation) and
    function (the communicative role).

    Loaded from data/vocab/research_topic_terms.yaml.
    """

    model_config = ConfigDict(use_enum_values=True)

    topic_id:           str = Field(
        ...,
        description="Unique term ID. Format: 'topic:<slug>'.",
        examples=["topic:vocal_learning", "topic:individual_recognition"],
    )
    canonical_label:    str = Field(
        ...,
        description="Canonical English label used in DB and UI.",
        examples=["vocal learning"],
    )
    topic_category:     Optional[str] = Field(
        None,
        description="Broad category: 'developmental' | 'cognitive' | 'social' | "
                    "'perceptual' | 'evolutionary' | 'ecological'.",
    )
    aliases:            list[str] = Field(
        default_factory=list,
        description="Variant labels from literature that normalise to this term.",
    )
    definition:         Optional[str] = Field(
        None,
        description="Short definition (1–2 sentences).",
    )
    scope_note:         Optional[str] = Field(
        None,
        description="When to use this term vs a context or function term.",
    )
    parent_topic_id:    Optional[str] = Field(
        None,
        description="ID of parent topic for hierarchical browsing.",
    )
