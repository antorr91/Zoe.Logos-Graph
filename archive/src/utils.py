"""
utils.py
--------
Shared utilities for Zoe.Logos-Graph.
"""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any


def load_json(path: Path | str) -> Any:
    """Load and parse a JSON file."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_json(data: Any, path: Path | str, indent: int = 2) -> None:
    """Save data to a JSON file."""
    Path(path).write_text(json.dumps(data, indent=indent, ensure_ascii=False), encoding="utf-8")


def make_paper_id(title: str, year: int | None = None) -> str:
    """
    Generate a deterministic paper_id from title and year.
    Useful when no DOI or external ID is available.
    """
    slug = title.lower().strip()[:80]
    slug = "".join(c if c.isalnum() else "_" for c in slug)
    slug = "_".join(filter(None, slug.split("_")))  # collapse underscores
    suffix = hashlib.md5((title + str(year)).encode()).hexdigest()[:6]
    return f"{slug}_{suffix}" if year is None else f"{slug}_{year}_{suffix}"


def slugify(text: str) -> str:
    """Convert a string to a lowercase slug with underscores."""
    return "_".join(text.lower().strip().split())


def truncate(text: str, max_len: int = 80) -> str:
    """Truncate a string with an ellipsis."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."
