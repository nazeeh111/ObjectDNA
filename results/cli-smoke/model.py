"""ObjectDNA editable reconstruction. Dimensions are in millimetres.
Geometry is a reconstruction hypothesis; verify fit before manufacture.
STEP preserves geometry. This source preserves the parameter history."""
import cadquery as cq

width = 80.0747208875494
depth = 50.18196632759827
height = 44.14765182799306
thickness = 5.181228266560727

# Family: bracket
base = cq.Workplane("XY").box(width, depth, thickness, centered=(False, False, False))
wall = cq.Workplane("XY").box(width, thickness, height, centered=(False, False, False))
result = base.union(wall).clean()

if __name__ == "__main__":
    from pathlib import Path
    if Path("objectdna.step").exists() or Path("objectdna.stl").exists():
        raise FileExistsError("Previous exports exist. Run in a new directory to preserve them.")
    cq.exporters.export(result, "objectdna.step", exportType="STEP")
    cq.exporters.export(result, "objectdna.stl", exportType="STL")
