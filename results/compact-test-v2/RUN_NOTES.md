# Run conditions

This fixed quality run overlapped owned cold-import test subprocesses and browser demo capture. Wall-clock inference times increased substantially for some later cases. Every timing is retained, with no outlier removal. Shape, dimensional, validity and editability measurements remain the fixed per-case results.

Use `results/timing-v2/` for the subsequent timing-only repeat after heavyweight owned work finishes. That repeat keeps the same model bytes, geometry settings and evaluated scans, adds warmup, requests one BLAS/OpenMP thread, randomizes method/object order and reports three-repeat per-case medians. It does not retrain, tune, or change shape-quality results.

The v2 proposal design was fixed before the new test seeds 10000–10047 were evaluated. The earlier v1 diagnostic seeds 9000–9047 remain a negative result and were not reused for the v2 final-quality claim.
