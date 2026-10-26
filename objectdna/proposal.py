"""Small learned CAD-parameter proposal network, with transparent numeric weights.

Predicts one wall thickness within the supported family grammar from normalized
coordinate histograms. Proposal is an inference, never a measurement. No unsafe
programs or pickles are loaded.
"""

from __future__ import annotations
import json
from pathlib import Path
import numpy as np

from .paths import asset_root

ROOT = asset_root()
FEATURE_VERSION = "xyz-histogram-32-family-v1"


def proposal_features(points, dims, family):
    dims = np.asarray(dims, float)
    values = []
    for axis in range(3):
        hist = np.histogram(
            np.clip(np.asarray(points)[:, axis] / dims[axis], 0, 1), bins=32, range=(0, 1)
        )[0].astype(float)
        values.extend(hist / max(hist.sum(), 1))
    values.extend(dims / max(dims))
    values.extend([float(family == f) for f in ("block", "bracket", "enclosure")])
    return np.asarray(values)


def load_proposal(path=None):
    path = Path(path) if path else ROOT / "models/proposal.json"
    if not path.exists():
        return None
    model = json.loads(path.read_text())
    if model["feature_version"] != FEATURE_VERSION:
        raise ValueError("Proposal feature version mismatch.")
    return model


def predict_thickness(points, dims, family, model=None):
    if family == "block":
        return None
    model = model or load_proposal()
    if model is None:
        return None
    value = (proposal_features(points, dims, family) - np.asarray(model["mean"])) / np.asarray(
        model["scale"]
    )
    for idx, (weight, bias) in enumerate(zip(model["weights"], model["biases"])):
        value = value @ np.asarray(weight) + np.asarray(bias)
        if idx < len(model["weights"]) - 1:
            value = np.maximum(value, 0)
    ratio = float(np.exp(float(np.asarray(value).reshape(-1)[0])))
    return float(np.clip(ratio, 0.02, 0.40) * min(dims))
