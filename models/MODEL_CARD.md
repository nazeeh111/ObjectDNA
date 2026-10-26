# ObjectDNA evidence ranker v1

This CPU-trained, linear pairwise logistic ranker orders bounded CAD candidates using eleven approximate template-residual, reverse-coverage, orthographic raster and complexity features. It is an original engineering experiment, not a claim of a new state of the art or an unconstrained CAD generator.

Training: 180 procedural solids, 4218 candidates, 32856 mirrored preferences. Shapes use seeds 1000–1179; the first final evaluation uses fixed disjoint seeds 9000–9047. A later fixed compact-search experiment uses fresh final seeds 10000–10047; neither final set enters model fitting. Training labels use hidden synthetic solid geometry; inference does not have access to these labels. The generator shares the supported CAD grammar, so this is an in-distribution synthetic test.

Reproduce into a new bundle: `python scripts/train.py --output runs/models/ranker.json`. Pass `--models runs/models` to evaluation runners to select a directory containing both newly trained model JSON files. Model stores numeric coefficients in JSON and never runs model-supplied code. The JSON scores are ordering values, **not probabilities or calibrated confidence**. Training parameters were fixed before held-out evaluation.

Training data SHA-256: `cbbed3599419b07f48eee90ca68cbd6e82407bd613c95ad366cf3400511e46f7`. Per-case seeds, parameters, scan hashes and settings are in `training_manifest.json`. Wall-clock training time on this machine: 254.7 s.

Limitations: fixed families, orientation, noise and missing-side pattern; no material/function inference; no guaranteed hidden geometry; no independently verified real-part dimensional ground truth. Validate real capture performance separately. Geometry validation is a hard CadQuery check outside this trained ranker.

## Held-out result: experimental, not the default

The ranker reduced aggregate geometric accuracy in both experiments. On the [48-object v1 test](../results/synthetic-v1/REPORT.md), learned ranking plus refinement achieved mean IoU 0.9212 versus 0.9280 for fixed geometric scoring plus refinement. On the [fresh 48-object v2 test](../results/compact-test-v2/REPORT.md), compact proposals with the learned ranker achieved IoU 0.9254 and Chamfer 0.8782 mm, versus IoU 0.9293 and Chamfer 0.8690 mm with the geometric score.

All v2 methods produced valid, width-editable solids, demonstrating that kernel validity does not establish reconstruction accuracy. Learned ranker scores remain experimental; geometric scoring is the production default. Original failures, ablations, and frozen source/model snapshots are retained in the [experiment index](../results/EXPERIMENTS.md). No upstream neural system was run as a comparison baseline, and no state-of-the-art claim follows from this bounded experiment.
