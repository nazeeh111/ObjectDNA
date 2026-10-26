# Compact learned proposal experiment v2 · dev

Fixed design; 12 objects. Source unchanged during run: True.

v1 fixed test exposed no improvement from adding learned proposals to an already dense search and a regression from its learned ranker. v1 retained as a negative result. v2 tests whether learned proposals replace dense search efficiently.

| Method | IoU ↑ | Chamfer mm ↓ | Extent MAE mm ↓ | CAD valid | Editable | Inference s ↓ |
|---|---:|---:|---:|---:|---:|---:|
| dense_geometric | 0.937 | 0.851 | 0.312 | 100.0% | 100.0% | 1.332 |
| compact_geometric | 0.937 | 0.851 | 0.312 | 100.0% | 100.0% | 0.960 |
| compact_ranker | 0.917 | 0.865 | 0.356 | 100.0% | 100.0% | 0.417 |

## Paired effects

- compact_geometric minus dense_geometric, chamfer_mm: +0.0000, exploratory paired bootstrap 95% interval [+0.0000, +0.0000].
- compact_geometric minus dense_geometric, volumetric_iou: +0.0000, exploratory paired bootstrap 95% interval [+0.0000, +0.0000].
- compact_geometric minus dense_geometric, runtime_seconds: -0.3724, exploratory paired bootstrap 95% interval [-1.2728, +0.3865].
- compact_ranker minus dense_geometric, chamfer_mm: +0.0140, exploratory paired bootstrap 95% interval [+0.0000, +0.0344].
- compact_ranker minus dense_geometric, volumetric_iou: -0.0200, exploratory paired bootstrap 95% interval [-0.0485, +0.0000].
- compact_ranker minus dense_geometric, runtime_seconds: -0.9154, exploratory paired bootstrap 95% interval [-2.2464, -0.0927].

## Limitations

- Synthetic in-distribution grammar, not unconstrained CAD or verified real-dimensional metrology.
- Proposal network was trained on seeds2000–2599; development4000–4059; final v2 test10000–10047 unused in training/development.
- V2 design changed after v1 diagnostic test9000–9047; that old set is never reused for a confirmatory claim.
- Runtime is production reconstruction wall time, excludes cold import and benchmark-only ground-truth/CAD checks; method order randomized per object.
- Chamfer: symmetric unsquared nearest-neighbor distance on independent 7000-point surfaces with measured sampling floor. IoU: 50000-point Monte Carlo.
- CAD validity and 10% width editability measured by actual OpenCascade construction for every successful candidate.
- Exploratory paired bootstrap intervals do not establish real-world superiority or comparison to unrun upstream neural baselines.

## Worst compact-geometric cases

- Seed 4006: bracket → bracket, IoU 0.804, Chamfer 0.897 mm, missing-side pattern False.
- Seed 4009: bracket → bracket, IoU 0.853, Chamfer 0.634 mm, missing-side pattern False.
- Seed 4003: bracket → bracket, IoU 0.922, Chamfer 0.461 mm, missing-side pattern False.
- Seed 4007: enclosure → enclosure, IoU 0.936, Chamfer 1.214 mm, missing-side pattern False.
- Seed 4004: enclosure → enclosure, IoU 0.947, Chamfer 1.207 mm, missing-side pattern True.
