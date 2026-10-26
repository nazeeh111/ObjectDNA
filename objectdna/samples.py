"""Original procedural fixtures, explicitly synthetic, never labeled physical scans."""

from .geometry import simulate_scan
from pathlib import Path
import numpy as np
from .paths import asset_root

REAL = asset_root() / "data/real"
SPECS = {
    "bracket": {
        "family": "bracket",
        "parameters": dict(width=80.0, depth=50.0, height=44.0, thickness=5.0),
        "holes": [],
    },
    "enclosure": {
        "family": "enclosure",
        "parameters": dict(width=90.0, depth=65.0, height=35.0, thickness=4.0),
        "holes": [],
    },
    "drilled-block": {
        "family": "block",
        "parameters": dict(width=72.0, depth=48.0, height=24.0, thickness=4.0),
        "holes": [dict(x=21.0, y=24.0, radius=5.0), dict(x=51.0, y=24.0, radius=5.0)],
    },
}
DESCRIPTIONS = {
    "bracket": "80 × 50 × 44 mm L-section with simulated scanner noise.",
    "enclosure": "Open box with a 4 mm wall, sampled from authored geometry.",
    "drilled-block": "Two observed cylindrical bores in a machined-block fixture.",
}


def list_samples():
    fixtures = [
        dict(
            id=k,
            name={
                "bracket": "L-section bracket",
                "enclosure": "Open enclosure",
                "drilled-block": "Drilled block",
            }[k],
            description=DESCRIPTIONS[k],
            family=v["family"],
            source_kind="synthetic",
        )
        for k, v in SPECS.items()
    ]
    for id, name, desc, family in [
        (
            "cereal_box",
            "Physical scan · cereal box",
            "Google Scanned Objects. Exterior envelope only; hidden shell and contents unknown.",
            "block",
        ),
        (
            "porcelain_tray",
            "Physical scan · flared tray",
            "Outside-grammar stress case: flared walls, rounded corners and feet.",
            "enclosure",
        ),
    ]:
        if (REAL / f"{id}.xyz").exists():
            fixtures.append(
                dict(
                    id=id,
                    name=name,
                    description=desc,
                    family=family,
                    source_kind="physical scan (processed mesh)",
                )
            )
    return fixtures


def get_sample(id):
    if id in ("cereal_box", "porcelain_tray") and (REAL / f"{id}.xyz").exists():
        return np.loadtxt(REAL / f"{id}.xyz")
    if id not in SPECS:
        raise ValueError("Unknown sample identifier.")
    return simulate_scan(
        SPECS[id], seed=100 + list(SPECS).index(id), n=2400, noise=0.0008, outliers=0.005
    )
