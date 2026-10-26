# Physical scan examples

These are 12,000-point area-weighted samples from **processed physical scan meshes** in Google Scanned Objects. They are not raw camera/depth data and were never used for training. Copyright 2020 Google LLC., [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). [Google describes its physical structured-light acquisition here](https://research.google/blog/scanned-objects-by-google-research-a-dataset-of-3d-scanned-common-household-items/).

| Input | Intended use | Known limitations |
| --- | --- | --- |
| `cereal_box.xyz` | Fit the outside cuboid envelope of a cereal carton. | Bowed cardboard, folds, and seams are not ideal planes. The solid block is only an envelope; cardboard thickness, contents, and internal cavities are unknown. |
| `porcelain_tray.xyz` | Expose bounded-grammar failure on a real tray. | Walls flare outward, corners are rounded, and the underside has feet. A rectangular uniform-wall enclosure cannot represent it faithfully. |

Coordinates are in **millimetres**, converted from SDF/Gazebo SI metre coordinates. The original scan orientation is retained (z up, coordinates near centered in x/y). A maximum-extent reference or declared units establishes the imported scale; no caliper ground truth is supplied. Scan residuals do not establish physical dimensional accuracy. The dataset's published OBJ meshes are simplified; the sampled points inherit that processing.

The thumbnails are source renders supplied with the dataset, not photographs captured by ObjectDNA. See `provenance.json` for source URLs, archive/mesh/XYZ hashes, and exact transformations. `*_metadata.pbtxt` and `*_model.config` preserve the original Google license/author notices.

Recreate the samples from the reviewed source archives:

```sh
python scripts/fetch_real.py --out runs/real-scans
python scripts/real_demo.py --data-dir runs/real-scans --out runs/real-v1
```

The fetch command caches the source archives in the OS temporary directory, validates reviewed SHA256 values, samples with NumPy seed `20261025`, and writes a new scan bundle into `runs/real-scans`. The demo reads that bundle and writes new reports and CAD exports into `runs/real-v1`; it uses bundled model weights unless `--models` selects a newly trained pair. Existing output directories are preserved, so use fresh paths for repeat runs. Separate runs deterministically reproduce the point coordinates with the locked numerical environment; committed sample and provenance bytes remain unchanged. The corresponding public sources are [cereal carton](https://app.gazebosim.org/GoogleResearch/fuel/models/Vans_Cereal_Honey_Nut_Crunch_11_oz_box) and [porcelain tray](https://app.gazebosim.org/GoogleResearch/fuel/models/Threshold_Tray_Rectangle_Porcelain).
