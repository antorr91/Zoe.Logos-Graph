"""
config.py
---------
Loads and exposes the Zoe.Logos-Graph configuration from configs/config.yaml.

Usage:
    from src.config import cfg
    print(cfg.extraction.model)
    print(cfg.paths.raw)
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Config sub-models
# ---------------------------------------------------------------------------

class PathsConfig(BaseModel):
    raw: Path = Path("data/raw/")
    annotations: Path = Path("data/annotations/")
    processed: Path = Path("data/processed/")
    graph: Path = Path("data/graph/")
    outputs: Path = Path("outputs/")


class ExtractionConfig(BaseModel):
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 1000
    retries: int = 2
    delay: float = 0.5


class ValidationConfig(BaseModel):
    strict: bool = False


class GraphConfig(BaseModel):
    export_graphml: bool = True
    export_json: bool = True
    output_file: Path = Path("outputs/zoe_logos_graph.graphml")


class NormalisationConfig(BaseModel):
    apply_species_map: bool = True
    apply_vocalisation_map: bool = True
    apply_context_map: bool = True


class ZoeConfig(BaseModel):
    paths: PathsConfig = PathsConfig()
    extraction: ExtractionConfig = ExtractionConfig()
    validation: ValidationConfig = ValidationConfig()
    graph: GraphConfig = GraphConfig()
    normalisation: NormalisationConfig = NormalisationConfig()


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

_DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "configs" / "config.yaml"


def load_config(path: Path | str | None = None) -> ZoeConfig:
    """
    Load configuration from a YAML file.
    Falls back to defaults if file is not found.
    """
    config_path = Path(path) if path else _DEFAULT_CONFIG_PATH

    if not config_path.exists():
        return ZoeConfig()

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return ZoeConfig(**raw)


# ---------------------------------------------------------------------------
# Singleton — import this everywhere
# ---------------------------------------------------------------------------

cfg: ZoeConfig = load_config()
