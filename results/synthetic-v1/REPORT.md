# Synthetic benchmark v1

Actual local CPU run on 48 fixed held-out synthetic objects. No test tuning. Test bytes: `da09efa69f36a2151d2a2bd86fbb1d5e96e867ee2ae41326e46f50fc56a3c489`.

| Method | Chamfer mm ↓ | IoU ↑ | Extent MAE mm ↓ | Family | CAD valid | Editable | Inference s |
|---|---:|---:|---:|---:|---:|---:|---:|
| bbox | 2.962 | 0.516 | 0.683 | 33.3% | 100.0% | 100.0% | 0.000 |
| geometric_refined | 0.872 | 0.928 | 0.388 | 100.0% | 100.0% | 100.0% | 0.620 |
| learned_no_proposal | 0.881 | 0.921 | 0.465 | 100.0% | 100.0% | 100.0% | 0.731 |
| learned_unrefined | 0.911 | 0.903 | 0.683 | 100.0% | 100.0% | 100.0% | 0.638 |
| learned_refined | 0.881 | 0.921 | 0.465 | 100.0% | 100.0% | 100.0% | 0.921 |

## Measured paired effects

- learned_refined minus geometric_refined, chamfer_mm: +0.0097, exploratory paired bootstrap 95% interval [+0.0045, +0.0157].
- learned_refined minus geometric_refined, volumetric_iou: -0.0068, exploratory paired bootstrap 95% interval [-0.0113, -0.0031].
- learned_refined minus learned_unrefined, chamfer_mm: -0.0298, exploratory paired bootstrap 95% interval [-0.0420, -0.0186].
- learned_refined minus learned_unrefined, volumetric_iou: +0.0180, exploratory paired bootstrap 95% interval [+0.0128, +0.0243].
- learned_refined minus learned_no_proposal, chamfer_mm: +0.0000, exploratory paired bootstrap 95% interval [-0.0000, +0.0000].
- learned_refined minus learned_no_proposal, volumetric_iou: -0.0000, exploratory paired bootstrap 95% interval [-0.0000, +0.0000].

## Failure cases

- Seed 9037: bracket → bracket, IoU 0.716, Chamfer 1.036 mm, missing-side acquisition False, 0 predicted bores.
- Seed 9007: bracket → bracket, IoU 0.800, Chamfer 0.809 mm, missing-side acquisition False, 0 predicted bores.
- Seed 9047: enclosure → enclosure, IoU 0.803, Chamfer 1.183 mm, missing-side acquisition False, 0 predicted bores.
- Seed 9013: bracket → bracket, IoU 0.811, Chamfer 0.932 mm, missing-side acquisition False, 0 predicted bores.
- Seed 9020: enclosure → enclosure, IoU 0.830, Chamfer 1.085 mm, missing-side acquisition True, 0 predicted bores.

## Definitions and limitations

- Synthetic in-distribution grammar test, not unconstrained reconstruction.
- Chamfer is symmetric mean unsquared nearest-neighbor distance over two independent 7000-point surfaces. Sampling floor is measured separately.
- Volume IoU is a 50000-point Monte Carlo estimate over union bounds.
- External dimension error uses known generated extents, not fitted-surface distance. Thickness error conditional on family match and excludes solid blocks.
- CAD validity and editability measured by actual kernel construction and 10% width edit for every successful candidate.
- BBox baseline skips candidate ranking; runtime excludes shared preprocessing.
- No upstream neural model benchmark was run; no superiority claim is supported.

Environment: `{"machine": "arm64", "note": "Inference runtime excludes CAD validation and benchmark-only metric computation; cold import time excluded.", "numpy": "2.5.4", "platform": "macOS-26.6.2-arm64-arm-64bit", "processor": "arm", "python": "3.12.13", "thread_limit": "OMP/OPENBLAS/MKL=1 unless inherited"}`. Total benchmark time: 360.9 s. Per-case values, failures, specs and manifest are saved alongside this report.
