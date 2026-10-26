# Compact learned proposal experiment v2 · test

Fixed design; 48 objects. Source unchanged during run: True.

v1 fixed test exposed no improvement from adding learned proposals to an already dense search and a regression from its learned ranker. v1 retained as a negative result. v2 tests whether learned proposals replace dense search efficiently.

| Method | IoU ↑ | Chamfer mm ↓ | Extent MAE mm ↓ | CAD valid | Editable | Initial candidates | Inference s ↓ |
|---|---:|---:|---:|---:|---:|---:|---:|
| dense_geometric | 0.928 | 0.869 | 0.368 | 100.0% | 100.0% | 23.7 | 0.764 |
| compact_geometric | 0.929 | 0.869 | 0.366 | 100.0% | 100.0% | 7.2 | 0.527 |
| compact_ranker | 0.925 | 0.878 | 0.417 | 100.0% | 100.0% | 7.2 | 0.724 |

## Paired effects

- compact_geometric minus dense_geometric, chamfer_mm: +0.0004, exploratory paired bootstrap 95% interval [-0.0009, +0.0023].
- compact_geometric minus dense_geometric, volumetric_iou: +0.0008, exploratory paired bootstrap 95% interval [-0.0008, +0.0030].
- compact_geometric minus dense_geometric, runtime_seconds: -0.2377, exploratory paired bootstrap 95% interval [-0.3942, -0.0856].
- compact_ranker minus dense_geometric, chamfer_mm: +0.0096, exploratory paired bootstrap 95% interval [+0.0032, +0.0174].
- compact_ranker minus dense_geometric, volumetric_iou: -0.0031, exploratory paired bootstrap 95% interval [-0.0083, +0.0013].
- compact_ranker minus dense_geometric, runtime_seconds: -0.0399, exploratory paired bootstrap 95% interval [-0.2984, +0.2719].

## Limitations

- Synthetic in-distribution grammar, not unconstrained CAD or verified real-dimensional metrology.
- Proposal network was trained on seeds2000–2599; development4000–4059; final v2 test10000–10047 unused in training/development.
- V2 design changed after v1 diagnostic test9000–9047; that old set is never reused for a confirmatory claim.
- Runtime is production reconstruction wall time, excludes cold import and benchmark-only ground-truth/CAD checks; method order randomized per object.
- Chamfer: symmetric unsquared nearest-neighbor distance on independent 7000-point surfaces with measured sampling floor. IoU: 50000-point Monte Carlo.
- CAD validity and 10% width editability measured by actual OpenCascade construction for every successful candidate.
- Exploratory paired bootstrap intervals do not establish real-world superiority or comparison to unrun upstream neural baselines.

## Worst compact-geometric cases

- Seed 10046: enclosure → enclosure, IoU 0.775, Chamfer 1.073 mm, missing-side pattern False.
- Seed 10024: bracket → bracket, IoU 0.780, Chamfer 0.622 mm, missing-side pattern True.
- Seed 10019: enclosure → enclosure, IoU 0.801, Chamfer 0.997 mm, missing-side pattern False.
- Seed 10040: enclosure → enclosure, IoU 0.824, Chamfer 0.929 mm, missing-side pattern True.
- Seed 10027: bracket → bracket, IoU 0.881, Chamfer 0.667 mm, missing-side pattern False.

## Run conditions and topology denominator

This quality run overlapped owned native cold-import tests and browser capture. Preserve all timings; use separate locked timing-v2 repeat for lower-load runtime estimates.

Hole-count accuracy is conditional on correct family and truth block; see its denominator. Correct family plus hole-count success is 12/16 for dense/compact and 12/16 for compact ranker. All primary shape/dimension/validity metrics cover all 48.

Candidate counts describe initial proposals. Both modes additionally score three family-refinement candidates; total average scoring is 26.71 versus 10.25 for dense versus compact (61.6% fewer).
