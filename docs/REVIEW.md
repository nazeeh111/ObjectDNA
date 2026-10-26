# Independent review evidence

Focused verification on 2026-10-25 using the local ObjectDNA Python 3.12 environment. All three import/export findings below are resolved in the reviewed source. This is a bounded review, not a certification of unrestricted reconstruction or CAD interoperability.

## Findings and resolutions

- **Malformed PLY validation, resolved.** A truncated header (`ply\nformat ascii 1.0\n`) previously raised `IndexError`; an unsupported `property nonsense x` raised `KeyError`. The mesh import boundary now translates parser failures into `ValueError`. Independent direct calls returned the clear malformed-file message for both exact inputs. Independent FastAPI TestClient uploads returned HTTP 422 with that message for both inputs, rather than HTTP 500.
- **NPY allocation bound, resolved.** A 128-byte NPY header declaring shape `(10**12, 3)` previously reached a request for a 24 TB NumPy allocation before point-count validation. The current reader validates the header, real numeric dtype, bounded XYZ shape and exact payload length before reading the array. Independently verified that the same header raises the explicit before-allocation `ValueError` while `numpy.frombuffer` is patched to fail if reached. Earlier independent C- and Fortran-order numeric roundtrips also passed; the retained numeric/truncation regression test passed in the focused run below.
- **Export preservation, resolved.** Generated Python previously wrote fixed STEP/STL filenames without checking existing outputs. The generated script now refuses to run if either target exists; `export_file` also refuses an existing destination. Independent temporary-file checks preserved sentinel bytes for all four direct export formats and for either existing generated-script STEP/STL target. These focused file-preservation checks used a stub CAD kernel and observed zero exporter calls. They establish the guards, not geometric validity or STEP interoperability.

## Checks independently run

`python -m pytest -q tests/test_inference.py -k 'malformed_ply or huge_npy or npy_numeric or pickle'`

Result: **5 passed, 8 deselected**. Separate direct-parser, HTTP 422, NPY-before-buffer-read and export-preservation probes also passed. No application source was modified by the reviewer.

The broader source review found the learned proposal/ranker roles, disjoint synthetic seed splits, score direction, bounded grammar, relative-scale export restriction and stated physical-scan limitations consistent with their descriptions. Benchmark source versions identify both learned model files. Final held-out benchmark results and full CAD tests were not independently rerun in this focused verification. Packaging was handled separately by the release process.

## Exact source identity

SHA-256 values read immediately after these checks:

| File | SHA-256 |
|---|---|
| `objectdna/io.py` | `3b826f0af9457b73124ef2c80d3eecbe3db5a3d8a23f289bfb13f7a1902dffa0` |
| `objectdna/cad.py` | `331473beb26499e427028f2a2b6cb81a5f6e6f8f64db00fbb78870965d34540b` |
| `objectdna/api.py` | `d730f38dd26d3d3bca7d181895cc2bfe57042b382a3c37577b26c6ba886ee8ba` |
| `tests/test_inference.py` | `d4eec5af519340664d4071f28813c75808b4600b0cac9498f212b6216dbe201c` |


## Publication audit

A later release audit also fixed duplicate-point denoising, the default scale of raw JSON point arrays, and COUNT-aware PCD column parsing. The expanded import/inference suite passed 22 tests and the API suite passed four tests, including exact CAD edits/exports and relative-scale export blocking. Historical source hashes above identify the earlier review revision; retained benchmark snapshots remain unchanged. The CSG fitting residual is an approximate implicit distance near unions/cuts, distinct from the separately defined sampled Chamfer metric.
