#!/usr/bin/env python3
"""Reproduce real scan-envelope success and outside-grammar failure with no GT claims."""

from pathlib import Path
import sys
import json
import hashlib
import argparse
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from objectdna.inference import reconstruct
from objectdna.geometry import sample_surface, chamfer
from _run_outputs import require_new_directory, create_output_directory, model_files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "runs/real-v1",
        help="Fresh report/export directory; existing evidence is preserved.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        help="Directory containing the two XYZ scans and provenance.json; defaults to bundled real scans.",
    )
    parser.add_argument(
        "--models",
        type=Path,
        help="Both model JSON files and matching manifests; defaults to bundled weights.",
    )
    parser.add_argument("--candidate-mode", choices=("dense", "learned_compact"), default="dense")
    args = parser.parse_args()
    example = "python scripts/real_demo.py --out runs/real-v1-new"
    out = require_new_directory(args.out, parser, example)
    models = model_files(args.models, parser, ROOT)
    from objectdna.paths import asset_root

    data = (args.data_dir or asset_root() / "data/real").expanduser()
    try:
        metadata = json.loads((data / "provenance.json").read_text())
        scans = {}
        for name in ("cereal_box", "porcelain_tray"):
            path = data / f"{name}.xyz"
            if hashlib.sha256(path.read_bytes()).hexdigest() != metadata[name]["xyz_sha256"]:
                raise ValueError(f"{name} scan hash differs from provenance")
            scans[name] = np.loadtxt(path)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.error(
            f"Cannot use real scan bundle {data}: {exc}. Use bundled scans or run scripts/fetch_real.py --out runs/real-scans and pass --data-dir runs/real-scans."
        )
    from objectdna.cad import shape_stats, export_file

    create_output_directory(out, parser, example)
    rows = []
    for id in ("cereal_box", "porcelain_tray"):
        points = scans[id]
        for ranking in ("geometric", "learned"):
            r = reconstruct(
                points,
                ranking=ranking,
                use_learned_proposal=ranking == "learned"
                or args.candidate_mode == "learned_compact",
                candidate_mode=args.candidate_mode,
                ranker_path=models["ranker"],
                proposal_path=models["proposal"],
            )
            r["metrics"].update(shape_stats(r["spec"]))
            local = points - np.asarray(r["provenance"]["transform"]["translation"])
            # Full source scan vs independent dense candidate surface, no hidden GT CAD.
            r["metrics"]["scan_to_cad_sampled_chamfer_mm"] = chamfer(
                local, sample_surface(r["spec"], 12000, 616)
            )
            r["metrics"]["ground_truth_volume_iou"] = None
            r["metrics"]["independent_dimensional_error_mm"] = None
            r["provenance"]["dataset"] = metadata[id]
            r["warnings"].append(
                "The filled block is an external envelope hypothesis. Actual shell, contents and hidden structure are unknown. No independent caliper ground truth exists."
            )
            folder = out / f"{id}-{ranking}"
            if folder.exists():
                raise FileExistsError(
                    f"{folder} exists; preserve it and choose a fresh version before rerunning."
                )
            folder.mkdir()
            for ext in ("step", "stl", "py"):
                export_file(r["spec"], folder / f"candidate.{ext}", ext)
            (folder / "evidence.json").write_text(
                json.dumps(
                    {k: v for k, v in r.items() if k not in ("source_points", "residuals")},
                    indent=2,
                )
            )
            rows.append(
                dict(
                    object=id,
                    candidate_mode=args.candidate_mode,
                    ranking=ranking,
                    family=r["spec"]["family"],
                    metrics=r["metrics"],
                    runtime_seconds=r["runtime_seconds"],
                    spec=r["spec"],
                    scan_sha256=metadata[id]["xyz_sha256"],
                )
            )
            print(id, ranking, r["spec"]["family"], r["metrics"], flush=True)
    report = {
        "objects": rows,
        "candidate_mode": args.candidate_mode,
        "method": "physical processed mesh scans sampled to points; external envelope approximation, no real CAD or caliper truth",
        "model_paths": {k: str(v) for k, v in models.items()},
        "model_sha256": {
            kind: hashlib.sha256(path.read_bytes()).hexdigest() for kind, path in models.items()
        },
        "source_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (ROOT / "objectdna").glob("*.py")
        },
        "limits": [
            "Two small qualitative real cases, no generalization claim.",
            "Volume IoU and independent measured dimensional error unavailable, stored as null.",
            "Support acceptance is a heuristic, not an accuracy certificate.",
            "Mesh preprocessing by dataset publisher may remove real capture defects.",
        ],
    }
    (out / "summary.json").write_text(json.dumps(report, indent=2))
    lines = [
        "# Real scan demonstrations",
        "",
        "Actual CPU reconstruction of two CC BY 4.0 Google Scanned Objects captures. Published processed meshes are sampled into 12,000 points. These are physical-capture derivatives, not raw depth frames.",
        "",
        "| Object | Ranking | Model | Observed RMS mm | Sampled scan/CAD Chamfer mm | Support | Hypothesis accepted |",
        "|---|---|---|---:|---:|---:|---|",
    ]
    for row in rows:
        m = row["metrics"]
        lines.append(
            f"| {row['object']} | {row['ranking']} | {row['family']} | {m['observed_rmse_mm']:.3f} | {m['scan_to_cad_sampled_chamfer_mm']:.3f} | {m['observed_support']:.1%} | {m['accepted']} |"
        )
    lines += [
        "",
        "No ground-truth CAD or independently measured dimensions are available. Volume IoU and dimensional accuracy are unknown. The cereal result describes the outer envelope; it does not establish a solid interior, cardboard thickness, material, or function. The flared porcelain tray is outside the grammar and must be treated as a failure/stress example.",
        "",
        "STEP, STL, editable CadQuery and complete evidence are saved in each case folder. Attribution and byte-level provenance are in the selected scan bundle (provenance.json) and the repository data/real/README.md.",
        "",
    ]
    (out / "REPORT.md").write_text("\n".join(lines))


if __name__ == "__main__":
    main()
