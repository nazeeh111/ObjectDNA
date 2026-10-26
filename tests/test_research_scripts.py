"""Research commands must preserve published evidence and allow fresh destinations."""

from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest
from scripts._run_outputs import model_files, require_new_files, write_new_bundle

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = {
    "train.py": ("--output",),
    "train_proposal.py": ("--output",),
    "benchmark.py": ("--out", "--models"),
    "benchmark_compact.py": ("--out", "--models"),
    "benchmark_timing.py": ("--out", "--models", "--quality-report"),
    "real_demo.py": ("--out", "--models", "--data-dir"),
    "fetch_real.py": ("--out", "--cache"),
    "generate_samples.py": ("--out",),
    "plot_benchmark.py": ("--out", "--results"),
}


def run_script(name, *args):
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / name), *map(str, args)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=45,
    )


@pytest.mark.parametrize("name", SCRIPTS)
def test_research_command_help_has_explicit_output(name):
    result = run_script(name, "--help")
    assert result.returncode == 0, result.stderr
    for flag in SCRIPTS[name]:
        assert flag in result.stdout


@pytest.mark.parametrize("name", SCRIPTS)
def test_research_command_preserves_existing_output(name, tmp_path):
    out = tmp_path / "prior-evidence"
    out.mkdir()
    sentinel = out / "KEEP.txt"
    sentinel.write_bytes(b"original research bytes\x00\xff")
    before = {p.name: p.read_bytes() for p in out.iterdir()}
    if name.startswith("train"):
        target = out / ("proposal.json" if name == "train_proposal.py" else "ranker.json")
        target.write_bytes(b"prior numeric model")
        before[target.name] = target.read_bytes()
        args = ["--output", target]
    else:
        args = ["--out", out]
    result = run_script(name, *args)
    assert result.returncode == 2, (name, result.stdout, result.stderr)
    assert "preserved" in result.stderr and "fresh" in result.stderr
    assert {p.name: p.read_bytes() for p in out.iterdir()} == before
    assert "training data" not in result.stdout and "Generating proposal" not in result.stdout


@pytest.mark.parametrize(
    "name,filename,manifest",
    [
        ("train.py", "ranker.json", "training_manifest.json"),
        ("train_proposal.py", "proposal.json", "proposal_manifest.json"),
    ],
)
def test_training_preserves_companion_manifest_before_work(name, filename, manifest, tmp_path):
    (tmp_path / manifest).write_text("prior manifest")
    result = run_script(name, "--output", tmp_path / filename)
    assert result.returncode == 2 and "preserved" in result.stderr
    assert (tmp_path / manifest).read_text() == "prior manifest"
    assert not (tmp_path / filename).exists()
    assert set(p.name for p in tmp_path.iterdir()) == {manifest}


def test_model_bundle_writes_both_components_without_touching_other_model(tmp_path):
    parser = argparse.ArgumentParser()
    (tmp_path / "proposal.json").write_text("unrelated proposal model")
    files = {
        tmp_path / "ranker.json": "ranker weights",
        tmp_path / "training_manifest.json": "matching manifest",
        tmp_path / "MODEL_CARD.md": "card",
    }
    write_new_bundle(files, parser, "python scripts/train.py --output runs/new-models/ranker.json")
    assert all(p.read_text() == value for p, value in files.items())
    assert (tmp_path / "proposal.json").read_text() == "unrelated proposal model"
    with pytest.raises(SystemExit):
        write_new_bundle(files, parser, "fresh output")
    assert all(p.read_text() == value for p, value in files.items())


def test_model_filename_cannot_replace_its_own_manifest(tmp_path):
    parser = argparse.ArgumentParser()
    with pytest.raises(SystemExit):
        require_new_files(
            [
                tmp_path / "training_manifest.json",
                tmp_path / "training_manifest.json",
                tmp_path / "MODEL_CARD.md",
            ],
            parser,
            "fresh model path",
        )
    assert not list(tmp_path.iterdir())


def test_model_bundle_rollback_preserves_a_late_existing_companion(tmp_path, monkeypatch):
    parser = argparse.ArgumentParser()
    model = tmp_path / "ranker.json"
    manifest = tmp_path / "training_manifest.json"
    original_open = Path.open

    def racing_open(path, *args, **kwargs):
        if path == manifest and args and args[0] == "x":
            with original_open(manifest, "w") as other:
                other.write("other writer manifest")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", racing_open)
    with pytest.raises(SystemExit):
        write_new_bundle({model: "new model", manifest: "new manifest"}, parser, "fresh output")
    assert not model.exists()
    assert manifest.read_text() == "other writer manifest"


def test_generated_samples_use_new_destination_and_keep_bundled_bytes(tmp_path):
    bundled = ROOT / "data/synthetic"
    before = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in bundled.iterdir() if p.is_file()
    }
    out = tmp_path / "new-samples"
    result = run_script("generate_samples.py", "--out", out)
    assert result.returncode == 0, result.stderr
    assert len(list(out.glob("*.xyz"))) == 3 and len(list(out.glob("*.truth.json"))) == 3
    assert {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in bundled.iterdir() if p.is_file()
    } == before
    again = run_script("generate_samples.py", "--out", out)
    assert again.returncode == 2


def test_custom_model_bundle_matches_bundled_reconstruction(tmp_path):
    from objectdna.inference import reconstruct
    from objectdna.samples import get_sample
    from objectdna.paths import asset_root

    for name in (
        "ranker.json",
        "proposal.json",
        "training_manifest.json",
        "proposal_manifest.json",
    ):
        (tmp_path / name).write_bytes((asset_root() / "models" / name).read_bytes())
    models = model_files(tmp_path, argparse.ArgumentParser(), ROOT)
    cloud = get_sample("bracket")[:1200]
    bundled = reconstruct(cloud, ranking="learned", candidate_mode="learned_compact")
    custom = reconstruct(
        cloud,
        ranking="learned",
        candidate_mode="learned_compact",
        ranker_path=models["ranker"],
        proposal_path=models["proposal"],
    )
    assert custom["spec"] == bundled["spec"]
    assert custom["metrics"] == bundled["metrics"]
    assert custom["provenance"]["learned_proposal"] is True
    assert custom["candidates"] == bundled["candidates"]
    manifest = tmp_path / "proposal_manifest.json"
    metadata = json.loads(manifest.read_text())
    metadata["train_count"] += 1
    manifest.write_text(json.dumps(metadata))
    with pytest.raises(SystemExit):
        model_files(tmp_path, argparse.ArgumentParser(), ROOT)


def test_explicit_missing_model_is_not_silent_fallback(tmp_path):
    from objectdna.inference import reconstruct
    from objectdna.samples import get_sample

    cloud = get_sample("bracket")[:300]
    with pytest.raises(ValueError, match="model file"):
        reconstruct(cloud, ranking="learned", ranker_path=tmp_path / "missing-ranker.json")
    with pytest.raises(ValueError, match="model file"):
        reconstruct(
            cloud,
            candidate_mode="learned_compact",
            proposal_path=tmp_path / "missing-proposal.json",
        )


def test_requested_proposal_weights_change_the_actual_candidates(tmp_path):
    import numpy as np
    from objectdna.geometry import normalize_points
    from objectdna.inference import candidates
    from objectdna.paths import asset_root
    from objectdna.samples import get_sample

    original_path = asset_root() / "models/proposal.json"
    original_bytes = original_path.read_bytes()
    model = json.loads(original_bytes)
    # A numerical fixture outputs log(0.3) regardless of the earlier hidden layers.
    # This makes the expected candidate dimensions independent of learned defaults.
    model["weights"][-1] = np.zeros_like(model["weights"][-1]).tolist()
    model["biases"][-1] = [float(np.log(0.3))]
    requested = tmp_path / "constant-proposal.json"
    requested.write_text(json.dumps(model))
    cloud, dims, _ = normalize_points(get_sample("bracket")[:1200])
    actual = candidates(cloud, dims, candidate_mode="learned_compact", proposal_path=requested)
    expected = np.array([0.255, 0.300, 0.345]) * min(dims)
    for family in ("bracket", "enclosure"):
        thicknesses = [row["parameters"]["thickness"] for row in actual if row["family"] == family]
        np.testing.assert_allclose(thicknesses, expected, rtol=1e-12)
    default = candidates(cloud, dims, candidate_mode="learned_compact")
    default_thicknesses = [
        row["parameters"]["thickness"] for row in default if row["family"] == "bracket"
    ]
    assert not np.allclose(default_thicknesses, expected)
    assert original_path.read_bytes() == original_bytes
