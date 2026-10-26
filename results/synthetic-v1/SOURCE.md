# Versioned benchmark source

The `source/` directory retains the geometry, inference, proposal, exact CAD and benchmark/training sources, model bytes and training manifests for this v1 run. Their original source/model hashes are in `source_versions.json`. All nine recorded digests were checked against the saved copies.

The production CAD file received export overwrite guards while this benchmark was active. Its geometry, validity, tessellation and statistics were unchanged, and the benchmark process retained its already imported code. The saved original `source/objectdna/cad.py` matches the original recorded hash exactly.

To replay with the same dependencies active, enter `results/synthetic-v1/source` and run `python scripts/benchmark.py`. This writes a new nested `results/synthetic-v1` under the frozen source directory. The model training manifests are retained for integrity checks. CPU timing varies with machine and concurrent load. No test scores were used to tune v1.

V1 is retained as a negative result: the learned ranker regressed slightly from the geometric baseline, and adding learned proposals to a dense search did not help. The subsequent compact-proposal experiment uses a new test split.
