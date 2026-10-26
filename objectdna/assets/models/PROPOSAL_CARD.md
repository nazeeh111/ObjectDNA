# Learned wall-thickness proposal

A small 102→48→24→1 ReLU neural network predicts a bounded wall-thickness CAD parameter from three normalized coordinate histograms, relative extents and candidate-family indicators. Candidate-family conditioning is part of the model input, not a known object label. The selected geometric score or experimental learned ranker chooses among all family proposals.

Trained locally on 600 procedural scans, seeds 2000–2599. Separate development scans use seeds 4000–4059. The first final benchmark used seeds 9000–9047. After that diagnostic, the fixed compact-search design was evaluated on fresh final seeds 10000–10047. Neither set entered fitting, early stopping, or development measurements. Weights and biases are inspectable JSON. Reproduce into a new bundle: `python scripts/train_proposal.py --output runs/models/proposal.json`. Evaluation uses the bundled release weights unless `--models runs/models` explicitly selects newly trained models.

Development known-family thickness MAE: 0.386 mm. Training-median thickness-ratio baseline MAE: 1.544 mm. This measures proposal quality with a supplied family, not full reconstruction accuracy. Full-pipeline results and ablations belong in the benchmark.

The component does not learn unrestricted CAD programs or hidden mechanical function. It only proposes uniform wall thickness for two supported orthogonal families; candidate geometry remains inferred and requires verification. Training and development data share the authored grammar. No real-scan accuracy follows from this development result. Training took 93.0 s on the local CPU.

The optimizer reached the fixed 1,000-iteration limit and emitted a convergence warning. These measured development results do not establish optimizer convergence.

## Full-pipeline result and limits

The [fresh v2 test](../results/compact-test-v2/REPORT.md) compared a fixed compact proposal set against dense search, using the same geometric score and refinement. On 48 held-out synthetic objects, initial candidates fell from 23.71 to 7.25 on average (69.4% fewer), with mean IoU 0.92935 compact versus 0.92850 dense and 48/48 valid, width-editable solids. Both additionally scored three refined candidates per case; total candidate scoring fell by 61.6%.

A separate [warmed timing repeat](../results/timing-v2/REPORT.md) measured a 1.68× speedup, excluding cold imports, exact CAD validation/export, and UI latency. Small shape-metric differences do not establish an accuracy gain. The same-solid sampled Chamfer floor and Monte Carlo IoU noise limit fine comparisons. This is an in-distribution search-efficiency result, not independently measured real-part accuracy.

Adding the proposal to the already dense v1 search did not materially improve reconstruction. That [negative result](../results/synthetic-v1/REPORT.md) is retained. The [experiment index](../results/EXPERIMENTS.md) connects all splits, settings, per-case outputs, and frozen source/model snapshots. The model bytes and training manifest remain unchanged across those evaluations.
