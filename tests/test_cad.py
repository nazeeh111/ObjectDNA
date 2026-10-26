from pathlib import Path

"""Independent analytic expectations for the bounded CAD grammar."""
import ast
import copy
import json
import math
import subprocess
import sys

import cadquery as cq
import numpy as np
import pytest

from objectdna.cad import (
    build_shape,
    cadquery_script,
    export_file,
    mesh_data,
    shape_stats,
    validate_spec,
)


def spec(family="bracket"):
    return {
        "family": family,
        "parameters": {"width": 60, "depth": 40, "height": 30, "thickness": 4},
        "holes": [],
    }


@pytest.mark.parametrize("family", ["bracket", "enclosure", "block"])
def test_single_solid_analytic_volume_and_bounds(family):
    s = spec(family)
    expected = {
        "bracket": 60 * 40 * 4 + 60 * 4 * (30 - 4),
        "enclosure": 60 * 40 * 30 - (60 - 8) * (40 - 8) * (30 - 4),
        "block": 60 * 40 * 30,
    }[family]
    stats = shape_stats(s)
    assert stats["validity"] and stats["solid_count"] == 1
    assert stats["volume_mm3"] == pytest.approx(expected, rel=1e-9)
    assert stats["bounds_mm"]["min"] == pytest.approx([0, 0, 0], abs=1e-6)
    assert stats["bounds_mm"]["size"] == pytest.approx([60, 40, 30], abs=1e-6)


def test_edit_rebuild_changes_real_geometry():
    original = spec("enclosure")
    revised = copy.deepcopy(original)
    revised["parameters"]["width"] = 72
    revised["parameters"]["thickness"] = 5
    before, after = shape_stats(original), shape_stats(revised)
    assert original["parameters"]["width"] == 60
    assert after["bounds_mm"]["size"] == pytest.approx([72, 40, 30], abs=1e-6)
    assert after["volume_mm3"] == pytest.approx(72 * 40 * 30 - 62 * 30 * 25, rel=1e-9)
    assert after["volume_mm3"] != before["volume_mm3"]


def test_bore_geometry_and_editability():
    s = spec("block")
    s["holes"] = [{"x": 15, "y": 20, "radius": 3}, {"x": 45, "y": 20, "radius": 5}]
    shape = build_shape(s).val()
    assert not shape.isInside((15, 20, 15))
    assert shape.isInside((30, 20, 15))
    assert shape.Volume() == pytest.approx(60 * 40 * 30 - math.pi * (3**2 + 5**2) * 30, rel=1e-8)
    s["holes"][0]["radius"] = 4
    assert shape_stats(s)["volume_mm3"] == pytest.approx(
        60 * 40 * 30 - math.pi * (4**2 + 5**2) * 30, rel=1e-8
    )


def test_mesh_matches_current_dimensions():
    s = spec("block")
    mesh = mesh_data(s)
    assert len(mesh["faces"]) >= 12
    assert all(len(face) == 3 and max(face) < len(mesh["vertices"]) for face in mesh["faces"])
    assert [max(v[i] for v in mesh["vertices"]) for i in range(3)] == pytest.approx(
        [60, 40, 30], abs=1e-6
    )


@pytest.mark.parametrize("family", ["bracket", "enclosure", "block"])
def test_fitting_sdf_agrees_with_independent_kernel(family):
    """The numerical fitter's shape must represent the exported physical solid."""
    from objectdna.geometry import sample_surface, sdf

    s = spec(family)
    if family == "block":
        s["holes"] = [{"x": 20, "y": 20, "radius": 5}]
    solid = build_shape(s).val()
    rng = np.random.default_rng(912)
    points = rng.uniform([-5, -5, -5], [65, 45, 35], (350, 3))
    distance = sdf(points, s)
    # Boundary ambiguity is excluded from strict inside/outside comparisons.
    keep = np.abs(distance) > 1e-5
    kernel_inside = np.array([solid.isInside(tuple(p)) for p in points[keep]])
    np.testing.assert_array_equal(distance[keep] < 0, kernel_inside)
    samples = sample_surface(s, n=100, seed=44)
    assert np.max(np.abs(sdf(samples, s))) < 1e-6
    boundary = cq.Compound.makeCompound(solid.Faces())
    distances = [boundary.distance(cq.Vertex.makeVertex(*p)) for p in samples]
    assert max(distances) < 1e-5


@pytest.mark.parametrize("family", ["bracket", "enclosure", "block"])
def test_step_round_trip_in_fresh_process(tmp_path, family):
    target = export_file(spec(family), tmp_path / "part.step", "STEP")
    # A fresh process is a same-kernel readback, not independent CAD interoperability.
    script = "import cadquery as cq,json,sys; s=cq.importers.importStep(sys.argv[1]).val(); b=s.BoundingBox(); print(json.dumps({'valid':s.isValid(),'volume':s.Volume(),'solids':len(s.Solids()),'size':[b.xlen,b.ylen,b.zlen]}))"
    completed = subprocess.run(
        [sys.executable, "-c", script, str(target)], check=True, capture_output=True, text=True
    )
    stats = json.loads(completed.stdout.strip().splitlines()[-1])
    assert stats["valid"] and stats["solids"] == 1
    assert stats["size"] == pytest.approx([60, 40, 30], abs=1e-5)
    assert stats["volume"] == pytest.approx(shape_stats(spec(family))["volume_mm3"], rel=1e-7)


def test_source_script_runs_and_exports_current_edit(tmp_path):
    s = spec("block")
    s["parameters"]["height"] = 18
    s["holes"] = [{"x": 20, "y": 20, "radius": 4}]
    source = cadquery_script(s)
    ast.parse(source)
    py = export_file(s, tmp_path / "model.py", "PY")
    subprocess.run([sys.executable, str(py)], cwd=tmp_path, check=True, capture_output=True)
    solid = cq.importers.importStep(str(tmp_path / "objectdna.step")).val()
    assert solid.BoundingBox().zlen == pytest.approx(18)
    assert solid.Volume() == pytest.approx(60 * 40 * 18 - math.pi * 16 * 18)
    assert (tmp_path / "objectdna.stl").stat().st_size > 100
    json_path = export_file(s, tmp_path / "model.json", "JSON")
    assert json.loads(json_path.read_text())["parameters"]["height"] == 18


@pytest.mark.parametrize("value", [None, "40", float("nan"), float("inf"), -2, 0, True, 1e9])
def test_invalid_dimensions_rejected(value):
    s = spec()
    s["parameters"]["width"] = value
    with pytest.raises(ValueError):
        validate_spec(s)


@pytest.mark.parametrize(
    "bad",
    [
        None,
        [],
        {},
        {"family": "__import__('os')", "parameters": {}},
        {"family": ["block"], "parameters": {}},
    ],
)
def test_malformed_schema_rejected(bad):
    with pytest.raises(ValueError):
        validate_spec(bad)


def test_degenerate_cavity_and_bores_rejected():
    s = spec("enclosure")
    s["parameters"]["thickness"] = 20
    with pytest.raises(ValueError):
        build_shape(s)
    s = spec("block")
    s["holes"] = [{"x": 2, "y": 20, "radius": 3}]
    with pytest.raises(ValueError):
        validate_spec(s)
    s["holes"] = [{"x": 15, "y": 20, "radius": 3}, {"x": 18, "y": 20, "radius": 3}]
    with pytest.raises(ValueError):
        validate_spec(s)
    s["family"] = "bracket"
    with pytest.raises(ValueError):
        validate_spec(s)


def test_export_rejects_unknown_format_without_file(tmp_path):
    path = tmp_path / "bad.txt"
    with pytest.raises(ValueError):
        export_file(spec(), path, "EXEC")
    assert not path.exists()


def test_exports_preserve_existing_files(tmp_path):
    path = tmp_path / "model.py"
    path.write_bytes(b"important original")
    with pytest.raises(FileExistsError):
        export_file(spec(), path, "PY")
    assert path.read_bytes() == b"important original"
    source = cadquery_script(spec())
    # Execute authored main body with a stub exporter so the safeguard is independently exercised.
    import types
    from unittest.mock import patch

    (tmp_path / "objectdna.step").write_bytes(b"previous STEP")
    old = Path.cwd()
    import os

    try:
        os.chdir(tmp_path)
        with pytest.raises(FileExistsError):
            exec(compile(source, "downloaded.py", "exec"), {"__name__": "__main__"})
    finally:
        os.chdir(old)
    assert (tmp_path / "objectdna.step").read_bytes() == b"previous STEP"
