"""ObjectDNA editable reconstruction. Dimensions are in millimetres.
Geometry is a reconstruction hypothesis; verify fit before manufacture.
STEP preserves geometry. This source preserves the parameter history."""
import cadquery as cq

width = 200.1053982815199
depth = 54.06630371038161
height = 279.38741197533386
thickness = 5.552604972800001

# Family: block
result = cq.Workplane("XY").box(width, depth, height, centered=(False, False, False))
result = result.clean()

if __name__ == "__main__":
    from pathlib import Path
    if Path("objectdna.step").exists() or Path("objectdna.stl").exists():
        raise FileExistsError("Previous exports exist. Run in a new directory to preserve them.")
    cq.exporters.export(result, "objectdna.step", exportType="STEP")
    cq.exporters.export(result, "objectdna.stl", exportType="STL")
