"""Owned synthetic data-only project controls; no stored models or scans."""

import copy, hashlib, json, math, os, subprocess, sys
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pytest
from fastapi.testclient import TestClient
from objectdna.api import app, STORE
from objectdna.project import (
    decode_project,
    encode_project,
    make_project,
    restore_project,
    write_exclusive,
)


def source():
    # Independently generated exact block-surface grid in normalized mm coordinates.
    points = []
    for axis, extent in enumerate((30.0, 20.0, 10.0)):
        other = [x for x in range(3) if x != axis]
        for side in (0.0, extent):
            for a in np.linspace(0, (30.0, 20.0, 10.0)[other[0]], 10):
                for b in np.linspace(0, (30.0, 20.0, 10.0)[other[1]], 10):
                    p = [0.0, 0.0, 0.0]
                    p[axis] = side
                    p[other[0]] = float(a)
                    p[other[1]] = float(b)
                    points.append(p)
    spec = {
        "family": "block",
        "parameters": {"width": 30.0, "depth": 20.0, "height": 10.0, "thickness": 2.0},
        "holes": [],
    }
    pose = {
        "rotation": np.eye(3).tolist(),
        "translation": [3.0, 4.0, 5.0],
        "pca_center": None,
        "scale": 1.0,
        "pca_alignment": False,
        "input_units": "mm",
        "calibrated": True,
        "reference_extent_mm": None,
        "removed_points": 0,
    }
    return {
        "source_points": points,
        "spec": spec,
        "units": "mm",
        "provenance": {
            "transform": pose,
            "source_sha256": hashlib.sha256(b"synthetic source").hexdigest(),
            "source_kind": "synthetic",
            "source_name": "synthetic.xyz",
            "ranking": "geometric",
            "ranker_version": None,
            "learned_proposal": False,
            "candidate_mode": "dense",
        },
    }


def test_project_exact_points_recompute_and_history():
    original = source()
    raw = encode_project(original)
    project = decode_project(raw)
    loaded = restore_project(project)
    assert loaded["source_points"] == original["source_points"]
    assert loaded["provenance"]["transform"] == original["provenance"]["transform"]
    assert loaded["provenance"]["source_sha256"] == original["provenance"]["source_sha256"]
    assert loaded["metrics"]["accepted"] is False and loaded["metrics"]["valid"]
    assert (
        abs(loaded["metrics"]["volume_mm3"] - 6000) < 1e-6
        and loaded["metrics"]["observed_rmse_mm"] < 1e-12
    )
    assert len(loaded["residuals"]) == 600 and loaded["mesh"]["faces"]
    assert (
        project["models"]["weight_digests"] is None and project["history"][0]["kind"] == "inferred"
    )


def test_invalid_corrupt_oversize_archive_and_transform():
    p = make_project(source())
    for mutate in ("stale", "nan", "rotation", "units", "spec", "history", "version", "model"):
        bad = copy.deepcopy(p)
        if mutate == "stale":
            bad["normalized_points"][0][0] += 1
        elif mutate == "nan":
            bad["normalized_points"][0][0] = float("nan")
        elif mutate == "rotation":
            bad["provenance"]["transform"]["rotation"][0][0] = 2
        elif mutate == "units":
            bad["units"] = "relative"
        elif mutate == "spec":
            bad["history"][0]["spec"]["parameters"]["width"] = -1
        elif mutate == "history":
            bad["history"].append({"kind": "inferred", "spec": bad["history"][0]["spec"]})
        elif mutate == "version":
            bad["schema"] = "objectdna.project/v999"
        else:
            bad["models"]["ranking"] = "forged"
        if mutate not in ("stale", "nan"):
            rebind(bad)
        with pytest.raises((ValueError, TypeError)):
            decode_project(json.dumps(bad).encode())
    with_metric = copy.deepcopy(p)
    with_metric["metrics"] = {"accepted": True}
    rebind(with_metric)
    with pytest.raises(ValueError):
        decode_project(json.dumps(with_metric).encode())
    for data in (b"PK\x03\x04junk", b'{"schema":1,"schema":2}', b"", b"x" * (25 * 1024 * 1024 + 1)):
        with pytest.raises(ValueError):
            decode_project(data)


def test_exclusive_publication_failure_and_retry(tmp_path):
    target = tmp_path / "project.json"
    data = encode_project(source())
    with patch("objectdna.project.os.link", side_effect=OSError("injected failure")):
        with pytest.raises(OSError):
            write_exclusive(target, data)
    assert list(tmp_path.iterdir()) == []
    write_exclusive(target, data)
    assert target.read_bytes() == data
    with pytest.raises(FileExistsError):
        write_exclusive(target, b"other")
    assert target.read_bytes() == data and list(tmp_path.iterdir()) == [target]


def test_api_open_edit_save_reopen_export_and_bad_inputs():
    client = TestClient(app)
    bundle = encode_project(source())
    opened = client.post(
        "/api/project/open", files={"file": ("synthetic.json", bundle, "application/json")}
    )
    assert opened.status_code == 200, opened.text
    value = opened.json()
    assert value["metrics"]["valid"] and value["metrics"]["accepted"] is False
    spec = copy.deepcopy(value["spec"])
    spec["parameters"]["width"] = 31
    edited = client.post("/api/edit", json={"id": value["id"], "spec": spec})
    assert edited.status_code == 200, edited.text
    saved = client.get("/api/project/" + edited.json()["id"])
    assert saved.status_code == 200
    recorded = decode_project(saved.content)
    assert [h["kind"] for h in recorded["history"]] == ["inferred", "edited"]
    STORE.clear()
    assert client.get("/api/export/" + edited.json()["id"] + "?format=json").status_code == 404
    reopened = client.post(
        "/api/project/open", files={"file": ("session.json", saved.content, "application/json")}
    )
    assert reopened.status_code == 200, reopened.text
    assert (
        reopened.json()["spec"]["parameters"]["width"] == 31
        and reopened.json()["metrics"]["accepted"] is False
    )
    assert client.get("/api/export/" + reopened.json()["id"] + "?format=step").status_code == 200
    assert (
        client.post(
            "/api/project/open", files={"file": ("bad.zip", b"PK\x03\x04", "application/zip")}
        ).status_code
        == 422
    )


def test_relative_scale_remains_relative_and_metric_export_refused():
    original = source()
    original["units"] = "relative"
    original["provenance"]["transform"].update(input_units="unknown", calibrated=False)
    client = TestClient(app)
    r = client.post("/api/project/open", files={"file": ("p.json", encode_project(original))})
    assert r.status_code == 200, r.text
    assert r.json()["units"] == "relative" and r.json()["metrics"]["observed_rmse_mm"] is None
    assert client.get("/api/export/" + r.json()["id"] + "?format=step").status_code == 422


def test_meter_normalization_transform_is_not_applied_twice():
    from objectdna.geometry import normalize_points

    original = source()
    raw = np.asarray(original["source_points"]) / 1000 + np.array([0.003, 0.004, 0.005])
    normalized, _, pose = normalize_points(raw, units="m", align=False)
    assert pose["removed_points"] == 0
    independently = (raw * 1000 - np.asarray(pose["translation"])) * pose["scale"]
    np.testing.assert_allclose(normalized, independently, rtol=0, atol=1e-12)
    original["source_points"] = normalized.tolist()
    original["provenance"]["transform"] = pose
    opened = restore_project(decode_project(encode_project(original)))
    np.testing.assert_array_equal(opened["source_points"], normalized)
    assert opened["units"] == "mm" and opened["provenance"]["transform"]["input_units"] == "m"


def test_json_numeric_only_and_size_history_bounds():
    original = source()
    original["source_points"][0][0] = "0"
    with pytest.raises(ValueError):
        encode_project(original)
    original = source()
    original["source_points"][0][0] = True
    with pytest.raises(ValueError):
        encode_project(original)
    original = source()
    original["project_history"] = [{"kind": "inferred", "spec": original["spec"]}] + [
        {"kind": "edited", "spec": original["spec"]}
    ] * 128
    with pytest.raises(ValueError):
        encode_project(original)


def rebind(project):
    content = {k: v for k, v in project.items() if k != "project_sha256"}
    encoded = json.dumps(
        content, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")
    project["project_sha256"] = hashlib.sha256(encoded).hexdigest()
    return project


def test_bound_content_detects_stale_metadata_and_semantic_checks_survive_rebinding():
    project = make_project(source())
    changed = copy.deepcopy(project)
    changed["provenance"]["transform"]["translation"][0] += 1
    with pytest.raises(ValueError, match="content digest"):
        decode_project(json.dumps(changed).encode())
    changed = copy.deepcopy(project)
    changed["normalized_points"][0][0] += 1
    rebind(changed)
    with pytest.raises(ValueError, match="source-point digest"):
        decode_project(json.dumps(changed).encode())
    changed = copy.deepcopy(project)
    changed["provenance"]["transform"]["rotation"][0][0] = 2
    rebind(changed)
    with pytest.raises(ValueError, match="rotation"):
        decode_project(json.dumps(changed).encode())
    changed = copy.deepcopy(project)
    changed["history"][0]["spec"]["unexpected"] = "ignore-me"
    rebind(changed)
    with pytest.raises(ValueError, match="only supported geometry"):
        decode_project(json.dumps(changed).encode())


def test_transform_numeric_metadata_and_model_identity_strict():
    project = make_project(source())
    for mutator in (
        lambda p: p["provenance"]["transform"]["rotation"][0].__setitem__(0, True),
        lambda p: p["provenance"]["transform"]["translation"].__setitem__(0, "3"),
        lambda p: p["provenance"]["transform"].__setitem__("scale", 2),
        lambda p: p["provenance"].__setitem__("learned_proposal", 0),
        lambda p: p["models"].__setitem__("learned_proposal", 0),
    ):
        altered = copy.deepcopy(project)
        mutator(altered)
        rebind(altered)
        with pytest.raises((ValueError, TypeError)):
            decode_project(json.dumps(altered).encode())
