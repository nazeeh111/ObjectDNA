#!/usr/bin/env python3
"""Fixed v2 learned-proposal speed/quality experiment on a fresh unseen split.

Design fixed after v1 diagnostic: three learned thickness proposals per non-block
family (0.85, 1.0, 1.15 times predicted thickness), same geometry and refinement.
No hyperparameter selection is performed on the final split.
"""

from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import platform
import sys
import time

for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(name, "1")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import numpy as np
from objectdna.inference import reconstruct
from train import make_case, canonical_hash
from benchmark import measure, aggregate, paired_interval
from _run_outputs import (
    require_new_directory,
    create_output_directory,
    model_files,
    source_files,
    file_hashes,
)

METHODS = {
    "dense_geometric": dict(
        ranking="geometric", use_learned_proposal=False, candidate_mode="dense"
    ),
    "compact_geometric": dict(
        ranking="geometric", use_learned_proposal=True, candidate_mode="learned_compact"
    ),
    "compact_ranker": dict(
        ranking="learned", use_learned_proposal=True, candidate_mode="learned_compact"
    ),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=("dev", "test"), default="test")
    parser.add_argument("--count", type=int)
    parser.add_argument(
        "--out", type=Path, help="Fresh run directory; defaults to runs/compact-{split}-v2."
    )
    parser.add_argument(
        "--models",
        type=Path,
        help="Model directory with both weights and matching manifests; defaults to bundled models.",
    )
    args = parser.parse_args()
    count = args.count if args.count is not None else (12 if args.split == "dev" else 48)
    if not 3 <= count <= (12 if args.split == "dev" else 48):
        parser.error("Count exceeds fixed split size.")
    seeds = list(range(4000, 4012) if args.split == "dev" else range(10000, 10048))[:count]
    example = f"python scripts/benchmark_compact.py --split {args.split} --out runs/compact-{args.split}-v2-new"
    out = require_new_directory(args.out or ROOT / f"runs/compact-{args.split}-v2", parser, example)
    models = model_files(args.models, parser, ROOT)
    paths = source_files(
        ROOT,
        [
            "objectdna/geometry.py",
            "objectdna/inference.py",
            "objectdna/proposal.py",
            "objectdna/cad.py",
            "objectdna/paths.py",
            "scripts/benchmark_compact.py",
            "scripts/benchmark.py",
            "scripts/train.py",
            "scripts/_run_outputs.py",
        ],
        models,
    )
    versions = file_hashes(paths)
    create_output_directory(out, parser, example)
    (out / "source_versions.json").write_text(json.dumps(versions, indent=2) + "\n")
    rows = []
    cases = []
    started = time.perf_counter()
    for index, seed in enumerate(seeds):
        truth, scan, cloud, dims, pose, record = make_case(seed)
        cases.append(record)
        # Balance repeated-method/cold-cache order without changing any reconstruction.
        order = list(METHODS)
        np.random.default_rng(seed + 177).shuffle(order)
        case_rows = []
        for method in order:
            row = {
                "seed": seed,
                "method": method,
                "truth_family": truth["family"],
                "partial": record["partial"],
                "noise_fraction_diagonal": record["noise_fraction_diagonal"],
            }
            try:
                result = reconstruct(
                    scan,
                    units="mm",
                    refine=True,
                    ranker_path=models["ranker"],
                    proposal_path=models["proposal"],
                    **METHODS[method],
                )
                spec = result["spec"]
                row.update(
                    spec=spec,
                    predicted_family=spec["family"],
                    runtime_seconds=result["runtime_seconds"],
                    candidate_mode=result["provenance"].get("candidate_mode"),
                    candidate_count=result["provenance"].get("candidate_count"),
                    accepted=result["metrics"]["accepted"],
                    observed_support=result["metrics"]["observed_support"],
                    surface_coverage=result["metrics"]["surface_coverage"],
                    **measure(
                        spec,
                        truth,
                        np.asarray(result["provenance"]["transform"]["translation"]),
                        seed,
                    ),
                )
                if row["candidate_mode"] != METHODS[method]["candidate_mode"]:
                    raise ValueError(
                        "Production candidate-mode provenance does not match experiment."
                    )
            except Exception as exc:
                row["error"] = f"{type(exc).__name__}: {exc}"
            rows.append(row)
            case_rows.append(row)
        (out / "cases.json").write_text(json.dumps(rows, indent=2) + "\n")
        print(
            f"{args.split} {index + 1}/{count}: "
            + ", ".join(
                f"{r['method']} IoU={r.get('volumetric_iou', r.get('error'))} runtime={r.get('runtime_seconds')}"
                for r in case_rows
            ),
            flush=True,
        )
    agg = {method: aggregate([r for r in rows if r["method"] == method]) for method in METHODS}
    for method in METHODS:
        agg[method]["candidate_count_mean"] = float(
            np.mean(
                [r["candidate_count"] for r in rows if r["method"] == method and "error" not in r]
            )
        )
    paired = [
        paired_interval(rows, "dense_geometric", method, metric)
        for method in ("compact_geometric", "compact_ranker")
        for metric in ("chamfer_mm", "volumetric_iou", "runtime_seconds")
    ]
    source_unchanged = file_hashes(paths) == versions
    summary = {
        "schema_version": 2,
        "split": args.split,
        "test_cases": count,
        "dataset": "Same authored procedural grammar, fresh random dimensions/acquisition seeds",
        "seeds": seeds,
        "test_sha256": canonical_hash(cases),
        "design": "Dense deterministic thickness search versus learned thickness x {0.85,1,1.15}; same block/bore proposals, evidence and refinement. Fixed before new test.",
        "design_history": "v1 fixed test exposed no improvement from adding learned proposals to an already dense search and a regression from its learned ranker. v1 retained as a negative result. v2 tests whether learned proposals replace dense search efficiently.",
        "methods": agg,
        "paired_comparisons": paired,
        "software": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "platform": platform.platform(),
        },
        "source_unchanged_during_run": source_unchanged,
        "source_versions": versions,
        "model_paths": {k: str(v) for k, v in models.items()},
        "total_seconds": time.perf_counter() - started,
        "limitations": [
            "Synthetic in-distribution grammar, not unconstrained CAD or verified real-dimensional metrology.",
            "Proposal network was trained on seeds2000–2599; development4000–4059; final v2 test10000–10047 unused in training/development.",
            "V2 design changed after v1 diagnostic test9000–9047; that old set is never reused for a confirmatory claim.",
            "Runtime is production reconstruction wall time, excludes cold import and benchmark-only ground-truth/CAD checks; method order randomized per object.",
            "Chamfer: symmetric unsquared nearest-neighbor distance on independent 7000-point surfaces with measured sampling floor. IoU: 50000-point Monte Carlo.",
            "CAD validity and 10% width editability measured by actual OpenCascade construction for every successful candidate.",
            "Exploratory paired bootstrap intervals do not establish real-world superiority or comparison to unrun upstream neural baselines.",
        ],
    }
    if any(a["failures"] for a in agg.values()):
        summary["warning"] = (
            "One or more cases failed. Inspect per-case errors; do not treat successful-case means as all-case performance."
        )
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (out / "test_manifest.json").write_text(json.dumps(cases, indent=2) + "\n")
    lines = [
        f"# Compact learned proposal experiment v2 · {args.split}",
        "",
        f"Fixed design; {count} objects. Source unchanged during run: {source_unchanged}.",
        "",
        summary["design_history"],
        "",
        "| Method | IoU ↑ | Chamfer mm ↓ | Extent MAE mm ↓ | CAD valid | Editable | Candidates | Inference s ↓ |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for method, a in agg.items():
        if a["completed"]:
            lines.append(
                f"| {method} | {a['volumetric_iou_mean']:.3f} | {a['chamfer_mm_mean']:.3f} | {a['external_dim_mae_mm_mean']:.3f} | {a['cad_valid_rate']:.1%} | {a['editable_rate']:.1%} | {a['candidate_count_mean']:.1f} | {a['runtime_seconds_mean']:.3f} |"
            )
        else:
            lines.append(f"| {method} | Failed all cases | | | | | |")
    lines += ["", "## Paired effects", ""]
    for comp in paired:
        lo, hi = comp["bootstrap_95_percentile_ci"]
        lines.append(
            f"- {comp['comparison']}, {comp['metric']}: {comp['mean']:+.4f}, exploratory paired bootstrap 95% interval [{lo:+.4f}, {hi:+.4f}]."
        )
    lines += ["", "## Limitations", ""] + ["- " + s for s in summary["limitations"]]
    lines += ["", "## Worst compact-geometric cases", ""]
    for r in sorted(
        [r for r in rows if r["method"] == "compact_geometric" and "error" not in r],
        key=lambda r: r["volumetric_iou"],
    )[:5]:
        lines.append(
            f"- Seed {r['seed']}: {r['truth_family']} → {r['predicted_family']}, IoU {r['volumetric_iou']:.3f}, Chamfer {r['chamfer_mm']:.3f} mm, missing-side pattern {r['partial']}."
        )
    (out / "REPORT.md").write_text("\n".join(lines) + "\n")
    print(json.dumps(agg, indent=2))


if __name__ == "__main__":
    main()
