# Timing source snapshot

`source/` retains all captured reconstruction/model bytes, timing runner and imported training helper, plus the locked quality summary and model training manifests. Declared digests in `summary.json` and extra import/manifest digests in `supplemental_source_versions.json` match the snapshot.

With the same dependencies active, enter `results/timing-v2/source` and run `python scripts/benchmark_timing.py`. The program writes new timing results below the snapshot. It checks source/model identity against the included quality summary before timing. This is a performance repeat of locked settings, not another quality test or tuning step.
