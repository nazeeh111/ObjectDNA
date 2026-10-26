# ObjectDNA experiments

ObjectDNA's measured ML contribution is a learned proposal model that reduces bounded CAD search. The separate learned evidence ranker is retained as an experimental negative result. These local experiments do not establish unrestricted CAD recovery or superiority to the upstream neural systems.

## What is trained

The wall-thickness proposal model is a 102→48→24→1 ReLU neural network. It consumes three normalized coordinate histograms, relative extents and a candidate-family indicator, then predicts log(thickness / minimum extent). Family indicators condition competing proposals; they do not supply the true object family at inference. Parameters remain constrained and inferred. The model is trained on 600 procedural bracket/enclosure scans (seeds 2000–2599), with internal early stopping and a separate 60-case development set (4000–4059). It reached the fixed 1,000-iteration limit, so optimizer convergence is not claimed. Known-family development thickness MAE was 0.386 mm versus 1.544 mm for the training-median thickness-ratio baseline. This conditional proposal metric is distinct from full reconstruction accuracy.

A linear pairwise logistic ranker was trained on 180 other procedural objects, 4,218 CAD candidates and 32,856 mirrored preferences (seeds 1000–1179). It uses observed surface residuals, reverse coverage, three orthographic raster discrepancies and operation complexity. Training labels use hidden synthetic geometry; inference receives no ground truth. The CAD kernel validates the resulting program outside the learned model. Numeric weights and provenance are inspectable JSON, with no executable model pickle.

## V1: retain the negative result

The first fixed final-quality split used 48 objects with seeds 9000–9047. The learned ranker plus refinement obtained mean volumetric IoU 0.9212 versus 0.9280 for geometric ranking plus refinement. Adding the learned thickness proposal to a dense thickness search produced no meaningful full-pipeline gain. Refinement itself improved the learned pipeline from 0.9032 to 0.9212 IoU.

These outcomes were not relabeled as a success. The [v1 report](synthetic-v1/REPORT.md), all case measurements, model bytes and replayable source snapshots are retained. The learned ranker remains available for research and ablation, with its regression documented.

## V2: learned proposals replace dense search

After the v1 diagnostic, the v2 design was fixed before a fresh final test: generate three thickness proposals per bracket/enclosure family at 0.85, 1.0 and 1.15 times the trained prediction, then apply the same geometric ranking and analytic refinement. Block and observed bore proposals remain unchanged. No model was retrained or tuned on either final test. A 12-case development feasibility run preceded the fresh 48-case final split, seeds 10000–10047.

| Fixed final v2 method | Mean IoU | Mean Chamfer mm | External dimension MAE mm | Initial proposals | Family | Valid CAD | Editable |
|---|---:|---:|---:|---:|---:|---:|---:|
| Dense geometric search + refinement | 0.92850 | 0.86855 | 0.36764 | 23.71 | 47/48 | 48/48 | 48/48 |
| Learned compact proposals + geometry + refinement | 0.92935 | 0.86899 | 0.36558 | 7.25 | 47/48 | 48/48 | 48/48 |
| Compact proposals + learned ranker + refinement | 0.92540 | 0.87818 | 0.41696 | 7.25 | 48/48 | 48/48 | 48/48 |

The compact geometric path generates 69.4% fewer initial proposals while obtaining similar aggregate shape accuracy on this fixed synthetic set. Both modes then score three additional family-refinement candidates, so total scoring falls from 26.71 to 10.25 candidates on average, a 61.6% reduction. This supports a bounded search-efficiency contribution, not an accuracy or universal reconstruction breakthrough. The learned ranker again reduced mean geometric accuracy. Read the [v2 report](compact-test-v2/REPORT.md) for paired intervals and failure cases.

The quality benchmark overlapped native cold-import tests and browser capture, so its absolute wall times are load-sensitive. A separate [locked timing repeat](timing-v2/REPORT.md) uses the same fixed models, settings and scans after heavyweight owned work finishes. It requests one BLAS/OpenMP thread, excludes warmup, randomizes object/method order and reports medians of three repeats per case. It does not alter shape-quality results. The completed 48-case, three-repeat run measured 0.1771 s dense versus 0.1054 s compact (means of per-case medians), a **1.68× speedup**, with exploratory paired bootstrap 95% interval [1.60, 1.76]. Source and models were unchanged during the run.

## Definitions and limits

- Chamfer is the symmetric mean unsquared nearest-neighbor distance between independent 7,000-point surface samples. The v2 mean same-solid sampling floor is 0.7827 mm. Sampling noise limits interpretation of very small changes.
- Volumetric IoU uses 50,000 Monte Carlo points over union bounds. It measures overlap of known synthetic solids, not occupancy inferred from an unknown real scan.
- External dimension error compares recovered width, depth and height with generated ground truth. Thickness error is reported separately and conditionally on matching supported family. No physical caliper metrology is implied.
- CAD validity and editability require actual OpenCascade construction and a successful 10% width edit, with dimensional readback, for every successful candidate.
- Hole-count accuracy in the raw summaries is conditional on matching the true block family. Unconditional correct family plus bore-count success is 12/16 true blocks for all three v2 methods.
- Runtime covers reconstruction, excluding cold imports, CAD validation/export and benchmark-only ground-truth metrics. It is not total UI or manufacturing latency.
- Paired bootstrap intervals are exploratory variability estimates across authored synthetic cases, not calibrated sensor uncertainty or guarantees for real objects.
- All training and synthetic evaluation share a bounded orthogonal single-solid grammar. Fillets, arbitrary surfaces, arbitrary pose, complex bores, assemblies, mechanical function and unseen internal dimensions remain outside the verified model scope.
- Upstream neural baselines were studied but not locally reproduced. Their published scores and ObjectDNA's local synthetic scores are not comparable experiments.

## Reproduce

```sh
python scripts/train_proposal.py --output runs/models/proposal.json
python scripts/train.py --output runs/models/ranker.json
python scripts/benchmark.py --models runs/models --out runs/synthetic-v1
python scripts/benchmark_compact.py --models runs/models --split test --out runs/compact-test-v2
python scripts/benchmark_timing.py --models runs/models --quality-report runs/compact-test-v2/summary.json --out runs/timing-v2
python scripts/plot_benchmark.py --results runs/compact-test-v2 --timing-results runs/timing-v2 --out runs/figures/compact-v2
```

These commands write a new training and evaluation run. Existing model, companion manifest/card, report and figure targets are preserved; choose a fresh path on subsequent runs. Training outputs stay together in `runs/models`. To evaluate the bundled weights instead, omit `--models` and still choose fresh report directories. Timing checks that its selected weights and current source match the selected quality report.

Training manifests retain per-object parameters, seeds and scan hashes. Benchmark folders retain per-case outputs, source/model hashes and frozen replayable source. Use the dependency lock and environment instructions in the repository README.

The first three cases were independently replayed from each frozen source snapshot after production source changed. All 15 v1 method-results and all 9 v2 method-results reproduced exact CAD specifications and identical retained shape/dimensional metrics (maximum absolute difference zero), plus matching CAD validity and editability. This verifies same-environment snapshot replay, not cross-platform bitwise reproducibility. See `replay-verification.json`.
