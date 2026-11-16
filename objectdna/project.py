"""Bounded, data-only normalized-source projects; saved claims are not validation."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile

import numpy as np
from scipy.spatial import cKDTree
from .geometry import validate_points, sdf, sample_surface

MAX_PROJECT_BYTES = 25 * 1024 * 1024
MAX_HISTORY = 128
SCHEMA = "objectdna.project/v1"


def _dump(value):
    try:
        data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")
    except (TypeError, ValueError, RecursionError, OverflowError) as exc:
        raise ValueError("Project must contain finite JSON data.") from exc
    if len(data) > MAX_PROJECT_BYTES:
        raise ValueError("Project exceeds the 25 MiB limit.")
    return data


def _unique_pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("Duplicate project property.")
        out[key] = value
    return out


def _points(value):
    if type(value) is not list or not 80 <= len(value) <= 6000:
        raise ValueError("Project needs 80–6,000 normalized XYZ points.")
    for row in value:
        if type(row) is not list or len(row) != 3 or any(type(v) not in (int, float) for v in row):
            raise ValueError("Project coordinates must be numeric XYZ values.")
    return validate_points(value, max_points=6000)


def points_digest(points):
    array = np.ascontiguousarray(points, dtype="<f8")
    return hashlib.sha256(len(array).to_bytes(8, "little") + array.tobytes()).hexdigest()


def _transform(value, units):
    required = {"rotation", "translation", "pca_center", "scale", "pca_alignment", "input_units", "calibrated", "reference_extent_mm", "removed_points"}
    if type(value) is not dict or set(value) != required:
        raise ValueError("Invalid normalization transform.")
    def vector(row):
        return type(row) is list and len(row) == 3 and all(type(v) in (int, float) for v in row)
    if (type(value["rotation"]) is not list or len(value["rotation"]) != 3
        or not all(vector(row) for row in value["rotation"]) or not vector(value["translation"])):
        raise ValueError("Transform needs numeric 3D rotation and translation.")
    rotation = np.asarray(value["rotation"], dtype=float)
    translation = np.asarray(value["translation"], dtype=float)
    center = value["pca_center"]
    if rotation.shape != (3, 3) or translation.shape != (3,) or not np.isfinite(rotation).all() or not np.isfinite(translation).all():
        raise ValueError("Transform needs finite 3D rotation and translation.")
    if not np.allclose(rotation.T @ rotation, np.eye(3), rtol=0, atol=1e-7) or not np.isclose(np.linalg.det(rotation), 1, rtol=0, atol=1e-7):
        raise ValueError("Transform rotation must be proper and orthonormal.")
    if type(value["pca_alignment"]) is not bool or type(value["calibrated"]) is not bool:
        raise ValueError("Transform flags must be Boolean.")
    if value["pca_alignment"]:
        if not vector(center):
            raise ValueError("PCA center must have numeric XYZ values.")
        center = np.asarray(center, dtype=float)
        if center.shape != (3,) or not np.isfinite(center).all():
            raise ValueError("PCA center must be finite and three-dimensional.")
    elif center is not None or not np.allclose(rotation, np.eye(3), rtol=0, atol=1e-7):
        raise ValueError("Unaligned transforms must have an identity rotation and no PCA center.")
    if value["input_units"] not in ("mm", "m", "unknown"):
        raise ValueError("Invalid input units.")
    scale = value["scale"]
    if isinstance(scale, bool) or not isinstance(scale, (int, float)) or not np.isfinite(scale) or not 0 < scale <= 1e12:
        raise ValueError("Transform scale must be finite and positive.")
    ref = value["reference_extent_mm"]
    if ref is not None and (isinstance(ref, bool) or not isinstance(ref, (int, float)) or not np.isfinite(ref) or not 0.1 <= ref <= 100000):
        raise ValueError("Invalid reference extent.")
    if ref is None and value["input_units"] in ("mm", "m") and scale != 1:
        raise ValueError("Known input units without a reference require unit normalization scale 1.")
    calibrated = value["input_units"] != "unknown" or ref is not None
    if value["calibrated"] != calibrated or units != ("mm" if calibrated else "relative"):
        raise ValueError("Units disagree with the normalization transform.")
    removed = value["removed_points"]
    if type(removed) is not int or not 0 <= removed <= 200000:
        raise ValueError("Invalid removed-point count.")
    return copy.deepcopy(value)


def make_project(result):
    from .cad import validate_spec
    points = _points(result["source_points"])
    units = result["units"]
    if units not in ("mm", "relative"):
        raise ValueError("Invalid project units.")
    provenance = copy.deepcopy(result.get("provenance", {}))
    if type(provenance) is not dict or len(_dump(provenance)) > 65536:
        raise ValueError("Project provenance exceeds its bound.")
    _transform(provenance.get("transform"), units)
    source_hash = provenance.get("source_sha256")
    if source_hash is not None and (type(source_hash) is not str or len(source_hash) != 64 or any(c not in "0123456789abcdef" for c in source_hash)):
        raise ValueError("Invalid recorded original source digest.")
    history = result.get("project_history")
    if history is None:
        history = [{"kind": "inferred", "spec": result["spec"]}]
    if type(history) is not list or not 1 <= len(history) <= MAX_HISTORY:
        raise ValueError("Project edit history exceeds its bound.")
    clean_history = []
    for i, entry in enumerate(history):
        if type(entry) is not dict or set(entry) != {"kind", "spec"} or entry["kind"] != ("inferred" if i == 0 else "edited"):
            raise ValueError("Invalid project edit history.")
        spec = entry["spec"]
        if (type(spec) is not dict or set(spec) != {"family", "parameters", "holes"}
            or type(spec.get("parameters")) is not dict
            or set(spec["parameters"]) != {"width", "depth", "height", "thickness"}
            or type(spec.get("holes")) is not list
            or any(type(hole) is not dict or set(hole) != {"x", "y", "radius"} for hole in spec["holes"])):
            raise ValueError("Project specs must contain only supported geometry data.")
        clean_history.append({"kind": entry["kind"], "spec": validate_spec(spec)})
    if clean_history[-1]["spec"] != validate_spec(result["spec"]):
        raise ValueError("Current specification differs from edit history.")
    if provenance.get("ranking") not in ("geometric", "learned") or provenance.get("candidate_mode") not in ("dense", "learned_compact") or type(provenance.get("learned_proposal")) is not bool:
        raise ValueError("Invalid recorded model identity.")
    version = provenance.get("ranker_version")
    if version is not None and (type(version) not in (int, str) or len(str(version)) > 128):
        raise ValueError("Invalid recorded ranker version.")
    models = {"ranking": provenance.get("ranking"), "ranker_version": provenance.get("ranker_version"),
              "learned_proposal": provenance.get("learned_proposal"), "candidate_mode": provenance.get("candidate_mode"),
              "weight_digests": None}
    project = {"schema": SCHEMA, "units": units, "normalized_points": points.tolist(),
               "normalized_points_sha256": points_digest(points), "provenance": provenance,
               "models": models, "history": clean_history}
    project["project_sha256"] = hashlib.sha256(_dump(project)).hexdigest()
    _dump(project)
    return project


def decode_project(data):
    if type(data) is not bytes or not 0 < len(data) <= MAX_PROJECT_BYTES:
        raise ValueError("Project must be a nonempty JSON file at most 25 MiB.")
    try:
        project = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_pairs,
                             parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON is forbidden.")))
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("Project must be valid data-only JSON.") from exc
    if type(project) is not dict or set(project) != {"schema", "units", "normalized_points", "normalized_points_sha256", "provenance", "models", "history", "project_sha256"} or project["schema"] != SCHEMA:
        raise ValueError("Unknown project version or properties.")
    claimed = project["project_sha256"]
    digest = hashlib.sha256(_dump({k: v for k, v in project.items() if k != "project_sha256"})).hexdigest()
    if type(claimed) is not str or claimed != digest:
        raise ValueError("Project content digest differs from its recorded identity.")
    history = project["history"]
    if type(history) is not list or not history or type(history[-1]) is not dict or "spec" not in history[-1]:
        raise ValueError("Project history is missing.")
    candidate = make_project({"source_points": project["normalized_points"], "units": project["units"],
                              "provenance": project["provenance"], "project_history": history,
                              "spec": history[-1]["spec"]})
    if project["normalized_points_sha256"] != candidate["normalized_points_sha256"]:
        raise ValueError("Normalized source-point digest differs from the project.")
    if _dump(project["models"]) != _dump(candidate["models"]):
        raise ValueError("Model identity summary differs from recorded provenance.")
    return candidate


def restore_project(project):
    """Recompute geometric evidence. Callers serialize CAD kernel access."""
    from .cad import validate_spec, mesh_data, shape_stats
    project = decode_project(_dump(project))
    cloud = validate_points(project["normalized_points"], max_points=6000)
    spec = validate_spec(project["history"][-1]["spec"])
    obs = np.abs(sdf(cloud, spec))
    diag = np.linalg.norm([spec["parameters"][k] for k in ("width", "depth", "height")])
    rev = cKDTree(cloud).query(sample_surface(spec, 5000, 77))[0]
    metrics = {"observed_rmse_mm": float(np.sqrt(np.mean(obs**2))) if project["units"] == "mm" else None,
               "chamfer_mm": float((obs.mean() + rev.mean()) / 2) if project["units"] == "mm" else None,
               "observed_support": float(np.mean(obs < diag * .012)),
               "surface_coverage": float(np.mean(rev < diag * .025)), "accepted": False,
               "volumetric_iou": None, "dimensional_error_mm": None}
    metrics.update(shape_stats(spec))
    provenance = copy.deepcopy(project["provenance"])
    provenance.update(project_reopened=True, normalized_points_sha256=project["normalized_points_sha256"], edited=len(project["history"]) > 1)
    return {"spec": spec, "source_points": cloud.tolist(), "units": project["units"], "project_source_sha256": project["project_sha256"],
            "metrics": metrics, "mesh": mesh_data(spec), "residuals": obs.tolist(),
            "project_history": project["history"], "provenance": provenance,
            "candidates": [], "runtime_seconds": None,
            "uncertainty": [{"feature": "Initial construction", "status": "inferred", "detail": "Recorded initial hypothesis; its original inference was not rerun."}] + ([{"feature": "Edited dimensions", "status": "user specified", "detail": "Saved edits are design intent, not new observations."}] if len(project["history"]) > 1 else []) + [{"feature": "Source provenance", "status": "unknown", "detail": "Project data and source provenance are not authenticated; review the source overlay."}],
            "warnings": ["Geometry and residuals were recomputed; saved acceptance and candidate rankings were not trusted."]}


def encode_project(result):
    return _dump(make_project(result)) + b"\n"


def write_exclusive(path, data):
    """Publish one complete owned file without replacing a preexisting path."""
    path = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".objectdna-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
