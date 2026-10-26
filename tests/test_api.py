import json
import pytest
from fastapi.testclient import TestClient
from objectdna.api import app
from objectdna.samples import get_sample

client = TestClient(app)


def test_reconstruct_edit_and_export_preserves_original():
    response = client.post(
        "/api/reconstruct", json={"sample_id": "bracket", "ranking": "geometric"}
    )
    assert response.status_code == 200, response.text
    r = response.json()
    assert r["mesh"]["faces"] and r["metrics"]["valid"]
    assert r["provenance"]["source_kind"] == "synthetic"
    spec = r["spec"]
    spec["parameters"]["width"] += 5
    e = client.post("/api/edit", json={"id": r["id"], "spec": spec})
    assert e.status_code == 200, e.text
    assert e.json()["id"] != r["id"]
    assert e.json()["metrics"]["volume_mm3"] > r["metrics"]["volume_mm3"]
    assert e.json()["provenance"]["edited"]
    original = client.get(f"/api/export/{r['id']}?format=json").json()
    assert original["spec"]["parameters"]["width"] < spec["parameters"]["width"]
    for ext in ("step", "stl", "py"):
        out = client.get(f"/api/export/{e.json()['id']}?format={ext}")
        assert out.status_code == 200 and len(out.content) > 100


def test_import_units_and_no_metric_export_without_calibration():
    points = get_sample("enclosure")
    data = "\n".join(" ".join(str(v) for v in p) for p in points)
    r = client.post("/api/import", files={"file": ("part.xyz", data)}, data={"units": "unknown"})
    assert r.status_code == 200, r.text
    assert r.json()["units"] == "relative"
    blocked = client.get(f"/api/export/{r.json()['id']}?format=step")
    assert blocked.status_code == 422 and "Calibrate" in blocked.text
    c = client.post(
        "/api/import",
        files={"file": ("part.xyz", data)},
        data={"units": "unknown", "reference_extent_mm": "90"},
    )
    assert c.status_code == 200 and c.json()["units"] == "mm"


def test_invalid_data_and_cross_origin_rejected():
    assert client.post("/api/reconstruct", json={}).status_code == 422
    assert client.post("/api/reconstruct", json={"sample_id": "nonexistent"}).status_code == 422
    assert client.post("/api/import", files={"file": ("bad.py", "print(1)")}).status_code == 422
    assert (
        client.post(
            "/api/reconstruct",
            headers={"origin": "https://unrelated.example"},
            json={"sample_id": "bracket"},
        ).status_code
        == 403
    )
    assert client.get("/api/export/missing").status_code == 404


def test_raw_json_arrays_require_explicit_absolute_scale():
    points = get_sample("bracket").tolist()
    relative = client.post(
        "/api/reconstruct", json={"points": points, "ranking": "geometric", "refine": False}
    )
    assert relative.status_code == 200, relative.text
    result = relative.json()
    assert result["units"] == "relative"
    assert not result["provenance"]["transform"]["calibrated"]
    for format in ("step", "stl", "py"):
        assert client.get(f"/api/export/{result['id']}?format={format}").status_code == 422
    calibrated = client.post(
        "/api/reconstruct",
        json={"points": points, "units": "mm", "ranking": "geometric", "refine": False},
    )
    assert calibrated.status_code == 200, calibrated.text
    assert calibrated.json()["units"] == "mm"
    assert calibrated.json()["provenance"]["transform"]["calibrated"]
