"""Small, auditable CAD grammar backed by CadQuery / OpenCascade.

All lengths are millimetres. This module only builds authored operations from
validated numeric data. Uploaded Python is never evaluated. STEP stores analytic
geometry; JSON and generated Python retain editable design parameters.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import cadquery as cq

FAMILIES = ("bracket", "enclosure", "block")
MAX_DIMENSION = 10_000.0
MIN_DIMENSION = 0.01


def _length(value: Any, name: str, *, allow_zero: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite numeric length in mm")
    try:
        number = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite numeric length in mm") from exc
    low = 0.0 if allow_zero else MIN_DIMENSION
    if not math.isfinite(number) or number < low or number > MAX_DIMENSION:
        raise ValueError(f"{name} must be between {low:g} and {MAX_DIMENSION:g} mm")
    return number


def validate_spec(spec: dict) -> dict:
    """Return canonical numeric CAD data, rejecting degenerate operations.

    Non-geometric metadata is deliberately omitted from the returned value.
    Holes represent observed/confirmed through-bores along Z, not functionality.
    """
    if not isinstance(spec, dict):
        raise ValueError("CAD specification must be an object")
    family = spec.get("family")
    if family not in FAMILIES:
        raise ValueError(f"family must be one of {', '.join(FAMILIES)}")
    source = spec.get("parameters")
    if not isinstance(source, dict):
        raise ValueError("parameters must be an object")
    p = {name: _length(source.get(name), name) for name in ("width", "depth", "height", "thickness")}
    w, d, h, t = (p[name] for name in ("width", "depth", "height", "thickness"))
    if family == "bracket" and t >= min(d, h) - MIN_DIMENSION:
        raise ValueError("Bracket thickness must leave a positive interior in depth and height")
    if family == "enclosure" and (2 * t >= min(w, d) - MIN_DIMENSION or t >= h - MIN_DIMENSION):
        raise ValueError("Enclosure thickness must leave a positive open cavity")
    holes = spec.get("holes", [])
    if not isinstance(holes, list) or len(holes) > 16:
        raise ValueError("holes must be a list with at most 16 through-bores")
    if holes and family != "block":
        raise ValueError("Through-bores are currently supported only for blocks")
    clean_holes = []
    for i, hole in enumerate(holes):
        if not isinstance(hole, dict):
            raise ValueError(f"Hole {i + 1} must be an object")
        x = _length(hole.get("x"), f"Hole {i + 1} X", allow_zero=True)
        y = _length(hole.get("y"), f"Hole {i + 1} Y", allow_zero=True)
        r = _length(hole.get("radius"), f"Hole {i + 1} radius")
        if x - r < MIN_DIMENSION or x + r > w - MIN_DIMENSION or y - r < MIN_DIMENSION or y + r > d - MIN_DIMENSION:
            raise ValueError(f"Hole {i + 1} must leave at least {MIN_DIMENSION:g} mm of material at every side")
        for other in clean_holes:
            if math.hypot(x - other["x"], y - other["y"]) < r + other["radius"] + MIN_DIMENSION:
                raise ValueError("Through-bores must not overlap or touch")
        clean_holes.append({"x": x, "y": y, "radius": r})
    return {"family": family, "parameters": p, "holes": clean_holes}


def _build_clean(spec: dict) -> cq.Workplane:
    p = spec["parameters"]
    w, d, h, t = (p[name] for name in ("width", "depth", "height", "thickness"))
    if spec["family"] == "bracket":
        base = cq.Workplane("XY").box(w, d, t, centered=(False, False, False))
        wall = cq.Workplane("XY").box(w, t, h, centered=(False, False, False))
        result = base.union(wall).clean()
    elif spec["family"] == "enclosure":
        outer = cq.Workplane("XY").box(w, d, h, centered=(False, False, False))
        # Extend beyond the top to avoid coplanar cutter ambiguity.
        cavity = cq.Workplane("XY").box(w - 2*t, d - 2*t, h, centered=(False, False, False)).translate((t, t, t))
        result = outer.cut(cavity).clean()
    else:
        result = cq.Workplane("XY").box(w, d, h, centered=(False, False, False))
        for hole in spec["holes"]:
            bore = cq.Workplane("XY").center(hole["x"], hole["y"]).circle(hole["radius"]).extrude(h + 2).translate((0, 0, -1))
            result = result.cut(bore)
        result = result.clean()
    shape = result.val()
    if not shape.isValid() or len(shape.Solids()) != 1 or shape.Volume() <= 0:
        raise ValueError("CAD operations did not produce one valid positive-volume solid")
    return result


def build_shape(spec: dict) -> cq.Workplane:
    """Build one analytic solid, checking the kernel result."""
    return _build_clean(validate_spec(spec))


def mesh_data(spec: dict, tolerance: float = 0.1) -> dict:
    """Tessellate the current analytic model for a browser preview."""
    if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)) or not math.isfinite(tolerance) or tolerance <= 0:
        raise ValueError("Mesh tolerance must be finite and positive")
    vertices, triangles = build_shape(spec).val().tessellate(float(tolerance), 0.15)
    return {
        "vertices": [[float(v.x), float(v.y), float(v.z)] for v in vertices],
        "faces": [[int(i) for i in face] for face in triangles],
    }


def shape_stats(spec: dict) -> dict:
    """Return kernel validity, solid count, volume and bounding dimensions."""
    shape = build_shape(spec).val()
    bounds = shape.BoundingBox()
    valid = bool(shape.isValid())
    return {
        "validity": valid,
        "valid": valid,
        "volume_mm3": float(shape.Volume()),
        "solid_count": len(shape.Solids()),
        "bounds_mm": {
            "min": [float(bounds.xmin), float(bounds.ymin), float(bounds.zmin)],
            "max": [float(bounds.xmax), float(bounds.ymax), float(bounds.zmax)],
            "size": [float(bounds.xlen), float(bounds.ylen), float(bounds.zlen)],
        },
    }


def cadquery_script(spec: dict) -> str:
    """Generate self-contained, editable Python from sanitized numbers.

    This is authored source, never text returned by a generative model. Users
    can execute the downloaded script in their own CadQuery environment.
    """
    clean = validate_spec(spec)
    p = clean["parameters"]
    lines = [
        '"""ObjectDNA editable reconstruction. Dimensions are in millimetres.',
        "Geometry is a reconstruction hypothesis; verify fit before manufacture.",
        'STEP preserves geometry. This source preserves the parameter history."""',
        "import cadquery as cq",
        "",
    ]
    lines += [f"{name} = {value!r}" for name, value in p.items()]
    lines += ["", f"# Family: {clean['family']}"]
    if clean["family"] == "bracket":
        lines += [
            'base = cq.Workplane("XY").box(width, depth, thickness, centered=(False, False, False))',
            'wall = cq.Workplane("XY").box(width, thickness, height, centered=(False, False, False))',
            "result = base.union(wall).clean()",
        ]
    elif clean["family"] == "enclosure":
        lines += [
            'outer = cq.Workplane("XY").box(width, depth, height, centered=(False, False, False))',
            'cavity = cq.Workplane("XY").box(width - 2*thickness, depth - 2*thickness, height, centered=(False, False, False)).translate((thickness, thickness, thickness))',
            "result = outer.cut(cavity).clean()",
        ]
    else:
        lines += ['result = cq.Workplane("XY").box(width, depth, height, centered=(False, False, False))']
        for i, hole in enumerate(clean["holes"], 1):
            lines += [
                f"hole_{i}_x, hole_{i}_y, hole_{i}_radius = {hole['x']!r}, {hole['y']!r}, {hole['radius']!r}",
                f'bore_{i} = cq.Workplane("XY").center(hole_{i}_x, hole_{i}_y).circle(hole_{i}_radius).extrude(height + 2).translate((0, 0, -1))',
                f"result = result.cut(bore_{i})",
            ]
        lines += ["result = result.clean()"]
    lines += [
        "", 'if __name__ == "__main__":',
        '    from pathlib import Path',
        '    if Path("objectdna.step").exists() or Path("objectdna.stl").exists():',
        '        raise FileExistsError("Previous exports exist. Run in a new directory to preserve them.")',
        '    cq.exporters.export(result, "objectdna.step", exportType="STEP")',
        '    cq.exporters.export(result, "objectdna.stl", exportType="STL")',
        "",
    ]
    return "\n".join(lines)


def export_file(spec: dict, path: str | Path, format: str) -> Path:
    """Write STEP, STL, PY or JSON to the caller's explicit destination."""
    clean = validate_spec(spec)
    kind = str(format).upper()
    if kind not in {"STEP", "STL", "PY", "JSON"}:
        raise ValueError("Export format must be STEP, STL, PY or JSON")
    target = Path(path)
    if target.exists():
        raise FileExistsError(f"Export already exists: {target}. Choose a new destination.")
    if kind == "PY":
        target.write_text(cadquery_script(clean), encoding="utf-8")
    elif kind == "JSON":
        target.write_text(json.dumps(clean, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    else:
        cq.exporters.export(_build_clean(clean), str(target), exportType=kind)
    if not target.is_file() or target.stat().st_size == 0:
        raise ValueError("Export did not produce a nonempty file")
    return target
