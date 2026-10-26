# Frozen v2 source and model bytes

The `source/` folder includes the exact inference, geometry, learned proposal, CAD, benchmark and model bytes used in this fixed final run. The benchmark's `source_versions.json` digests match the saved files; imported helper scripts, package initializer and model training manifests have additional digests in `supplemental_source_versions.json`.

With the same dependencies active, enter `results/compact-test-v2/source` and run `python scripts/benchmark_compact.py --split test`. It writes new results under the frozen source folder. The snapshots preserve all imports needed by that command and keep editable package imports local to the snapshot.

Read `RUN_NOTES.md` for the concurrent-load timing limitation. Model quality and per-case geometry results were not changed by the later timing-only repeat.
