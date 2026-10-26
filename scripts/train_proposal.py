#!/usr/bin/env python3
"""Train a small wall-thickness proposal MLP; no held-out benchmark tuning."""

from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(name, "1")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
from objectdna.geometry import random_spec, simulate_scan, normalize_points
from objectdna.proposal import proposal_features, predict_thickness, FEATURE_VERSION
from _run_outputs import require_new_files, write_new_bundle


def make_rows(seeds):
    X = []
    y = []
    rows = []
    clouds = []
    for seed in seeds:
        rng = np.random.default_rng(seed)
        family = ("bracket", "enclosure")[seed % 2]
        truth = random_spec(rng, family)
        scan = simulate_scan(
            truth,
            seed + 30000,
            n=1200,
            noise=float(rng.uniform(0.0005, 0.0035)),
            partial=seed % 4 == 0,
            outliers=0.01,
        )
        cloud, dims, pose = normalize_points(scan, "mm")
        target = truth["parameters"]["thickness"]
        X.append(proposal_features(cloud, dims, family))
        y.append(np.log(target / min(dims)))
        rows.append(
            {
                "seed": seed,
                "family": family,
                "truth": truth,
                "scan_sha256": hashlib.sha256(scan.tobytes()).hexdigest(),
            }
        )
        clouds.append((cloud, dims, family, target))
    return np.asarray(X), np.asarray(y), rows, clouds


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=600)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "runs/models/proposal.json",
        help="New model JSON path; proposal_manifest.json and PROPOSAL_CARD.md are saved beside it.",
    )
    args = parser.parse_args()
    if not 60 <= args.count <= 600:
        parser.error("--count must be 60–600")
    args.output = args.output.expanduser()
    example = "python scripts/train_proposal.py --output runs/new-models/proposal.json"
    require_new_files(
        [
            args.output,
            args.output.parent / "proposal_manifest.json",
            args.output.parent / "PROPOSAL_CARD.md",
        ],
        parser,
        example,
    )
    from sklearn.neural_network import MLPRegressor

    start = time.perf_counter()
    print("Generating proposal training scans", flush=True)
    X, y, rows, _ = make_rows(range(2000, 2000 + args.count))
    mean = X.mean(0)
    scale = X.std(0)
    scale[scale < 1e-6] = 1
    network = MLPRegressor(
        hidden_layer_sizes=(48, 24),
        activation="relu",
        solver="adam",
        alpha=0.02,
        batch_size=64,
        learning_rate_init=0.001,
        max_iter=1000,
        early_stopping=True,
        validation_fraction=0.15,
        n_iter_no_change=50,
        random_state=177,
    )
    network.fit((X - mean) / scale, y)
    model = {
        "version": "thickness-proposal-v1",
        "feature_version": FEATURE_VERSION,
        "mean": mean.tolist(),
        "scale": scale.tolist(),
        "weights": [w.tolist() for w in network.coefs_],
        "biases": [b.tolist() for b in network.intercepts_],
        "output": "log(thickness/minimum_extent)",
        "bounds_ratio": [0.02, 0.40],
        "training_seed_range": [2000, 1999 + args.count],
        "description": "Learned bounded CAD wall-thickness proposal, not calibrated measurement.",
    }
    print("Evaluating fixed development scans (separate from final benchmark)", flush=True)
    _, _, dev_rows, clouds = make_rows(range(4000, 4060))
    errors = []
    baseline = []
    median_ratio = float(np.exp(np.median(y)))
    for cloud, dims, family, target in clouds:
        errors.append(abs(predict_thickness(cloud, dims, family, model) - target))
        baseline.append(abs(median_ratio * min(dims) - target))
    report = {
        "train_cases": rows,
        "development_cases": dev_rows,
        "reserved_final_test_seeds": [9000, 9047],
        "train_count": args.count,
        "development_count": 60,
        "mlp_architecture": [len(mean), 48, 24, 1],
        "iterations": network.n_iter_,
        "optimizer_status": "maximum iterations reached"
        if network.n_iter_ >= network.max_iter
        else "early stopping",
        "development_thickness_mae_mm": float(np.mean(errors)),
        "median_ratio_baseline_mae_mm": float(np.mean(baseline)),
        "development_improvement_mm": float(np.mean(baseline) - np.mean(errors)),
        "training_seconds": time.perf_counter() - start,
        "fixed_hyperparameters": network.get_params(),
        "limitations": "Only bracket/enclosure wall thickness is learned. Family-conditioned fixed grammar, coordinate histograms and synthetic acquisition. Final held-out shapes are not used in fitting or early stopping.",
    }
    report["dataset_sha256"] = hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()
    model["training_manifest_sha256"] = hashlib.sha256(
        json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    card = f"""# Learned wall-thickness proposal

A small 102→48→24→1 ReLU neural network predicts a bounded wall-thickness CAD parameter from three normalized coordinate histograms, relative extents and candidate-family indicators. Candidate-family conditioning is part of the model input, not a known object label. The ranker chooses among all family proposals.

Trained locally on {args.count} procedural scans, seeds 2000–{1999 + args.count}. Separate development scans use seeds 4000–4059. Final benchmark seeds 9000–9047 never enter fitting, early stopping or development measurements. Weights and biases are inspectable JSON. Reproduce: `python scripts/train_proposal.py --output runs/models/proposal.json`.

Development known-family thickness MAE: {report["development_thickness_mae_mm"]:.3f} mm. Training-median thickness-ratio baseline MAE: {report["median_ratio_baseline_mae_mm"]:.3f} mm. This measures proposal quality with a supplied family, not full reconstruction accuracy. Full-pipeline results and ablations belong in the benchmark.

The component does not learn unrestricted CAD programs or hidden mechanical function. It only proposes uniform wall thickness for two supported orthogonal families; candidate geometry remains inferred and requires verification. Training and development data share the authored grammar. No real-scan accuracy follows from this development result. Optimizer status: {report["optimizer_status"]}; this result does not assert convergence. Training took {report["training_seconds"]:.1f} s on the local CPU.
"""
    write_new_bundle(
        {
            args.output: json.dumps(model, indent=2) + "\n",
            args.output.parent / "proposal_manifest.json": json.dumps(report, indent=2) + "\n",
            args.output.parent / "PROPOSAL_CARD.md": card,
        },
        parser,
        example,
    )
    print(
        json.dumps(
            {
                k: v
                for k, v in report.items()
                if k not in ("train_cases", "development_cases", "fixed_hyperparameters")
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
