#!/usr/bin/env python3
"""Optional VGGT bridge. Requires a separately installed, licensed VGGT environment.

This script is not in the verified default pipeline. It does not download weights,
execute CAD programs, infer metric scale, or attempt automatic object segmentation.
Supply tightly cropped object views or masks before running. Output remains relative.
"""

import argparse
from contextlib import nullcontext
import hashlib
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("images", type=Path, help="Directory of 2–16 tightly cropped JPG/PNG views")
    parser.add_argument(
        "--weights", type=Path, required=True, help="Local model.pt whose license you have reviewed"
    )
    parser.add_argument(
        "--vggt-source",
        type=Path,
        required=True,
        help="Separately installed upstream VGGT checkout",
    )
    parser.add_argument("--out", type=Path, required=True, help="New output directory")
    parser.add_argument("--device", choices=("cpu", "cuda", "mps"), default="cpu")
    parser.add_argument("--confidence-percentile", type=float, default=60)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("Output exists. Choose a new directory.")
    if not 0 <= args.confidence_percentile < 100:
        parser.error("Confidence percentile must be in [0,100).")
    images = sorted(
        p for p in args.images.iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg")
    )
    if not 2 <= len(images) <= 16:
        parser.error("Use 2–16 object views for the bounded adapter.")
    if not args.weights.is_file() or not args.vggt_source.is_dir():
        parser.error("Local weights and upstream source are required; no download is performed.")
    sys.path.insert(0, str(args.vggt_source.resolve()))
    import numpy as np
    import torch
    from vggt.models.vggt import VGGT
    from vggt.utils.load_fn import load_and_preprocess_images

    model = VGGT()
    # weights_only prevents arbitrary Python deserialization by torch.
    state = torch.load(args.weights, map_location="cpu", weights_only=True)
    model.load_state_dict(state)
    model = model.to(args.device).eval()
    batch = load_and_preprocess_images([str(p) for p in images]).to(args.device)
    context = (
        torch.autocast("cuda", dtype=torch.float16) if args.device == "cuda" else nullcontext()
    )
    with torch.inference_mode(), context:
        predictions = model(batch)
    points = predictions["world_points"].detach().float().cpu().numpy().reshape(-1, 3)
    confidence = predictions["world_points_conf"].detach().float().cpu().numpy().reshape(-1)
    keep = np.isfinite(points).all(1) & np.isfinite(confidence)
    keep &= confidence >= np.percentile(confidence[keep], args.confidence_percentile)
    points = points[keep]
    if len(points) < 80:
        raise RuntimeError("Insufficient finite high-confidence points.")
    if len(points) > 100000:
        points = points[np.random.default_rng(0).choice(len(points), 100000, replace=False)]
    args.out.mkdir(parents=True)
    np.savetxt(args.out / "relative_scan.xyz", points, fmt="%.8g")
    manifest = {
        "status": "unvalidated optional upstream adapter",
        "model": "VGGT local user-supplied weights",
        "weights_sha256": hashlib.file_digest(args.weights.open("rb"), "sha256").hexdigest(),
        "input_images": [
            {"name": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in images
        ],
        "units": "unknown",
        "confidence_percentile": args.confidence_percentile,
        "point_count": len(points),
        "limits": [
            "No metric scale without reference measurement.",
            "Confidence is an upstream model signal, not a calibrated accuracy interval.",
            "Background must be isolated before CAD fitting.",
            "No camera or depth reconstruction benchmark reproduced by ObjectDNA.",
        ],
    }
    (args.out / "provenance.json").write_text(json.dumps(manifest, indent=2))
    print(
        "Produced relative scan. Inspect and isolate object, then use objectdna fit --units unknown --reference-extent-mm ..."
    )


if __name__ == "__main__":
    main()
