"""Learned-artifact integrity and provenance checks, not a surrogate for evaluation."""

import hashlib
import json
from pathlib import Path
import numpy as np
import pytest
from objectdna.inference import FEATURE_NAMES, load_ranker, learned_score

ROOT = Path(__file__).resolve().parents[1]


def test_ranker_is_finite_transparent_and_matches_manifest():
    model = load_ranker()
    assert model is not None, "Generate model: python scripts/train.py"
    assert model["features"] == FEATURE_NAMES
    for key in ("mean", "scale", "weights"):
        values = np.asarray(model[key])
        assert values.shape == (len(FEATURE_NAMES),)
        assert np.isfinite(values).all()
    assert (np.asarray(model["scale"]) > 0).all()
    assert np.linalg.norm(model["weights"]) > 0
    manifest = json.loads((ROOT / "models/training_manifest.json").read_text())
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    assert hashlib.sha256(canonical).hexdigest() == model["training_manifest_sha256"]
    train = {c["seed"] for c in manifest["train_cases"]}
    assert not train.intersection(range(9000, 9048))
    assert len(train) == manifest["train_count"]
    assert all(len(c["scan_sha256"]) == 64 for c in manifest["train_cases"])


def test_linear_pairwise_score_direction_is_explicit():
    # This is an implementation contract: larger harmful feature -> larger score.
    model = {"mean": [0.0] * 11, "scale": [1.0] * 11, "weights": [1.0] + [0.0] * 10}
    assert learned_score(np.array([0.01] + [0.0] * 10), model) < learned_score(
        np.array([0.1] + [0.0] * 10), model
    )


def test_saved_benchmark_measures_all_objects_in_both_paired_methods():
    path = ROOT / "results/synthetic-v1/cases.json"
    if not path.exists() or not (path.parent / "summary.json").exists():
        pytest.skip("Run python scripts/benchmark.py to verify retained evaluation artifacts")
    rows = json.loads(path.read_text())
    summary = json.loads((path.parent / "summary.json").read_text())
    by_method = {}
    for row in rows:
        by_method.setdefault(row["method"], set()).add(row["seed"])
        if "error" not in row:
            assert 0 <= row["volumetric_iou"] <= 1
            assert row["chamfer_mm"] >= 0
            assert row["runtime_seconds"] >= 0
            assert isinstance(row["cad_valid"], bool)
            assert isinstance(row["editable"], bool)
    assert len(by_method["learned_refined"]) == summary["test_cases"]
    assert (
        by_method["geometric_refined"]
        == by_method["learned_refined"]
        == by_method["learned_unrefined"]
        == by_method["learned_no_proposal"]
    )
    assert not by_method["learned_refined"].intersection(range(1000, 1180))


def test_proposal_json_integrity_and_bounded_parameter():
    from objectdna.proposal import load_proposal, predict_thickness
    from objectdna.geometry import sample_surface

    model = load_proposal()
    if model is None:
        pytest.skip("Run python scripts/train_proposal.py")
    manifest = json.loads((ROOT / "models/proposal_manifest.json").read_text())
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    assert hashlib.sha256(canonical).hexdigest() == model["training_manifest_sha256"]
    train = {c["seed"] for c in manifest["train_cases"]}
    dev = {c["seed"] for c in manifest["development_cases"]}
    assert not train & dev and not (train | dev) & set(range(9000, 9048))
    spec = {
        "family": "enclosure",
        "parameters": dict(width=60.0, depth=40.0, height=25.0, thickness=3.0),
        "holes": [],
    }
    predicted = predict_thickness(
        sample_surface(spec, 1200, 123), [60.0, 40.0, 25.0], "enclosure", model
    )
    assert np.isfinite(predicted) and 0.02 * 25 <= predicted <= 0.4 * 25
    assert (
        predict_thickness(sample_surface(spec, 1200, 123), [60.0, 40.0, 25.0], "block", model)
        is None
    )


def test_compact_experiment_preserves_fresh_split_and_mode_provenance():
    directory = ROOT / "results/compact-test-v2"
    if not (directory / "summary.json").exists():
        pytest.skip("Run python scripts/benchmark_compact.py --split test")
    summary = json.loads((directory / "summary.json").read_text())
    rows = json.loads((directory / "cases.json").read_text())
    assert summary["source_unchanged_during_run"] is True
    assert set(summary["seeds"]).issubset(set(range(10000, 10048)))
    assert not set(summary["seeds"]) & set(range(9000, 9048))
    for method in ("dense_geometric", "compact_geometric", "compact_ranker"):
        method_rows = [r for r in rows if r["method"] == method]
        assert len(method_rows) == summary["test_cases"]
        for row in method_rows:
            assert "error" not in row
            assert row["candidate_mode"] == (
                "dense" if method == "dense_geometric" else "learned_compact"
            )
            assert row["candidate_count"] > 0
            assert row["cad_valid"] and row["editable"]
            assert 0 <= row["volumetric_iou"] <= 1
