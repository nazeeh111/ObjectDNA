"""ObjectDNA editable reconstruction. Dimensions are in millimetres.
Geometry is a reconstruction hypothesis; verify fit before manufacture.
STEP preserves geometry. This source preserves the parameter history."""
import cadquery as cq

width = 165.27965546418145
depth = 311.22912540085855
height = 32.36187101184017
thickness = 11.944240181507928

# Family: enclosure
outer = cq.Workplane("XY").box(width, depth, height, centered=(False, False, False))
cavity = cq.Workplane("XY").box(width - 2*thickness, depth - 2*thickness, height, centered=(False, False, False)).translate((thickness, thickness, thickness))
result = outer.cut(cavity).clean()

if __name__ == "__main__":
    from pathlib import Path
    if Path("objectdna.step").exists() or Path("objectdna.stl").exists():
        raise FileExistsError("Previous exports exist. Run in a new directory to preserve them.")
    cq.exporters.export(result, "objectdna.step", exportType="STEP")
    cq.exporters.export(result, "objectdna.stl", exportType="STL")
