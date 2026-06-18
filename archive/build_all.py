"""
build_all.py
------------
Run the full Zoe.Logos-Graph build pipeline in sequence.

Usage:
    python build_all.py                  # all steps
    python build_all.py --from 2         # from step 2 onwards
    python build_all.py --only 4         # only step 4
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import sys
from pathlib import Path

STEPS = [
    (1, "scripts.01_match_taxa",           "GBIF name matching"),
    (2, "scripts.02_fetch_species_metadata","Wikipedia + iNaturalist metadata"),
    (3, "scripts.03_fetch_media",           "Audio registry (Xeno-canto + external)"),
    (4, "scripts.04_build_species_pages",   "Build species JSON pages"),
    (5, "scripts.05_build_graph",           "Build knowledge graph"),
]

def run_step(module_name: str, label: str, n: int) -> None:
    print(f"\n{'='*60}")
    print(f"Step {n}: {label}")
    print(f"{'='*60}")
    # Scripts use _ in filename but Python needs importable names
    mod_path = Path(module_name.replace(".", "/") + ".py")
    spec = importlib.util.spec_from_file_location(module_name, mod_path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.main()

def main():
    parser = argparse.ArgumentParser(description="Run Zoe.Logos-Graph build pipeline")
    parser.add_argument("--from", dest="from_step", type=int, default=1)
    parser.add_argument("--only", dest="only_step", type=int, default=None)
    args = parser.parse_args()

    for n, module, label in STEPS:
        if args.only_step and n != args.only_step:
            continue
        if n < args.from_step:
            continue
        run_step(module, label, n)

    print(f"\n{'='*60}")
    print("Build complete.")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
