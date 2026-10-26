#!/usr/bin/env python3
"""Regenerate original demonstration scans into a fresh output directory."""

from pathlib import Path
import argparse
import sys
import json

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from _run_outputs import require_new_directory, create_output_directory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "runs/synthetic-samples",
        help="Fresh destination for the three scans and their CAD truth; bundled data is preserved.",
    )
    args = parser.parse_args()
    example = "python scripts/generate_samples.py --out runs/synthetic-samples-new"
    out = require_new_directory(args.out, parser, example)
    import numpy as np
    from objectdna.samples import SPECS, get_sample

    create_output_directory(out, parser, example)
    for name, spec in SPECS.items():
        np.savetxt(out / f"{name}.xyz", get_sample(name), fmt="%.6f")
        (out / f"{name}.truth.json").write_text(
            json.dumps(
                {"source_kind": "original procedural fixture", "units": "mm", "spec": spec},
                indent=2,
            )
            + "\n"
        )
    print(f"Generated three synthetic fixtures in {out}. These are not physical scans.")


if __name__ == "__main__":
    main()
