#!/usr/bin/env python3
"""Fetch two versioned CC BY 4.0 physical scans; sample their published meshes.

No account, credentials, paid service, or upstream model weights are needed.
The point samples are derived from processed scans, not raw sensor readings.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import tempfile
import urllib.request
import zipfile
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from _run_outputs import require_new_directory, create_output_directory

import numpy as np

SAMPLES = {
    "cereal_box": {
        "name": "Vans_Cereal_Honey_Nut_Crunch_11_oz_box",
        "archive_sha256": "31a5acdad9f8f05b186a8430d09982e5f156a02846eb9fa2b7f69ffb78d0ad1d",
        "intended_use": "Closed-cuboid envelope fit. Cardboard, folded edges, and bowing are outside the ideal block grammar.",
    },
    "porcelain_tray": {
        "name": "Threshold_Tray_Rectangle_Porcelain",
        "archive_sha256": "02d4670faedb0befcf875f0f57df185210d442f7025baaa6f1ab864bd6fcec57",
        "intended_use": "Failure/stress example: flared walls, rounded corners, and feet are outside the uniform-wall enclosure grammar.",
    },
}
CAPTURE_SOURCE = "https://research.google/blog/scanned-objects-by-google-research-a-dataset-of-3d-scanned-common-household-items/"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sample_obj(data: bytes, count: int = 12000, seed: int = 20261025) -> np.ndarray:
    """Area-weighted triangle samples without importing mesh rendering libraries."""
    vertices, faces = [], []
    for line in data.decode("utf-8").splitlines():
        words = line.split()
        if not words:
            continue
        if words[0] == "v":
            vertices.append([float(v) for v in words[1:4]])
        elif words[0] == "f":
            face = [int(v.split("/")[0]) - 1 for v in words[1:]]
            faces.extend((face[0], face[i], face[i + 1]) for i in range(1, len(face) - 1))
    v = np.asarray(vertices, dtype=float) * 1000.0  # SDF/Gazebo SI metres -> mm
    tri = v[np.asarray(faces, dtype=int)]
    area = np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1)
    if not len(tri) or not np.isfinite(v).all() or area.sum() <= 0:
        raise ValueError("Invalid or degenerate source mesh")
    rng = np.random.default_rng(seed)
    selected = tri[rng.choice(len(tri), count, p=area / area.sum())]
    uv = rng.random((count, 2))
    uv[uv.sum(axis=1) > 1] = 1 - uv[uv.sum(axis=1) > 1]
    return (
        selected[:, 0]
        + uv[:, :1] * (selected[:, 1] - selected[:, 0])
        + uv[:, 1:] * (selected[:, 2] - selected[:, 0])
    )


def prepare(key: str, archive: bytes, output: Path) -> dict:
    info = SAMPLES[key]
    sha = digest(archive)
    if sha != info["archive_sha256"]:
        raise ValueError(
            f"Source archive changed for {key}: SHA256 mismatch; inspect before updating provenance"
        )
    with zipfile.ZipFile(io.BytesIO(archive)) as source:
        obj = source.read("meshes/model.obj")
        points = sample_obj(obj)
        np.savetxt(
            output / f"{key}.xyz",
            points,
            fmt="%.6f",
            header="Google LLC 2020; CC BY 4.0; processed physical scan mesh samples in mm; no caliper ground truth",
        )
        (output / f"{key}.jpg").write_bytes(source.read("thumbnails/0.jpg"))
        (output / f"{key}_metadata.pbtxt").write_bytes(source.read("metadata.pbtxt"))
        (output / f"{key}_model.config").write_bytes(source.read("model.config"))
    return {
        **info,
        "owner": "GoogleResearch",
        "copyright": "Copyright 2020 Google LLC.",
        "license": "CC-BY-4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "source_url": f"https://app.gazebosim.org/GoogleResearch/fuel/models/{info['name']}",
        "archive_url": f"https://fuel.gazebosim.org/1.0/GoogleResearch/models/{info['name']}/1/{info['name']}.zip",
        "version": 1,
        "mesh_sha256": digest(obj),
        "xyz_sha256": digest((output / f"{key}.xyz").read_bytes()),
        "processing": "Area-weighted surface sampling of published processed OBJ scan mesh; 12000 samples; NumPy default_rng seed 20261025; coordinates multiplied by 1000 from SDF SI metres to mm. No denoising, alignment, or fitting applied.",
        "physical_capture_evidence": CAPTURE_SOURCE,
        "independent_measured_dimensions_mm": None,
        "limits": "Published mesh is a simplified processed physical scan, not raw sensor input. Reconstructed distances are scan-relative; manufacturing accuracy and hidden structure are unverified. Packaging shell thickness and material are unknown.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "real-scans")
    parser.add_argument(
        "--cache", type=Path, default=Path(tempfile.gettempdir()) / "objectdna-real-cache"
    )
    args = parser.parse_args()
    example = "python scripts/fetch_real.py --out runs/real-scans-new"
    args.out = require_new_directory(args.out, parser, example)
    create_output_directory(args.out, parser, example)
    args.cache.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for key, info in SAMPLES.items():
        cache = args.cache / (info["name"] + ".zip")
        if not cache.exists():
            url = f"https://fuel.gazebosim.org/1.0/GoogleResearch/models/{info['name']}/1/{info['name']}.zip"
            with urllib.request.urlopen(url, timeout=60) as response:
                payload = response.read(30_000_001)
            if len(payload) > 30_000_000:
                raise ValueError("Unexpectedly large archive")
            if digest(payload) != info["archive_sha256"]:
                raise ValueError("Downloaded source differs from reviewed version")
            try:
                with cache.open("xb") as target:
                    target.write(payload)
            except FileExistsError:
                if digest(cache.read_bytes()) != info["archive_sha256"]:
                    raise ValueError(
                        "Existing cache differs from the reviewed source; preserve it and choose a fresh --cache directory"
                    )
        manifest[key] = prepare(key, cache.read_bytes(), args.out)
        print(f"Prepared {key}: {args.out / (key + '.xyz')}")
    (args.out / "provenance.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
