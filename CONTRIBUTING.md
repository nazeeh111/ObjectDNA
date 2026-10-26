# Contributing to ObjectDNA

Small, reproducible improvements to reconstruction quality, import reliability, CAD editing, and the workbench are welcome. For a new shape family or a changed learning method, start with a concrete failing case and the evidence that would establish an improvement.

## Development

Use Python 3.12 and the repository's tested dependency list. Node 22.12+ is needed for frontend work.

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pip install --no-deps -e .
ruff check objectdna scripts tests tools
ruff format --check objectdna scripts tests tools
pytest -q
```

For workbench changes, build with `npm ci --ignore-scripts` and `npm run build` in `web/`. Start `objectdna serve` in another terminal, then run `npm run test:ui` in `web/` with Google Chrome installed. Inspect the current rendered result and cover the states affected by your change. See [architecture](docs/ARCHITECTURE.md) for the coordinate convention and module boundaries.

Keep a pull request focused. Explain the concrete problem, the resulting behavior, the checks performed, and any remaining limitation. Include a small input or reproducible command when it helps someone verify the change. Only share scans and assets you have permission to redistribute.

## Geometry and evidence

Observations, inferred construction, and unknown geometry must remain distinct. A valid CAD solid can still model the wrong object. Fit support and ranking scores are not calibrated probabilities, tolerances, or guarantees of manufacturability.

A new CAD operation needs independent analytic checks, a meaningful dimension edit, and export readback. Preserve existing exports when an import, reconstruction, or edit fails. Keep numeric specifications bounded; imported files and model outputs must not introduce arbitrary Python execution.

## Learning and evaluation

Use object-disjoint training, development, and final-test sets. Candidate rows from one object belong to the same split. Record source/model/data hashes, seeds, settings, sample counts, units, and per-object outcomes. Compare the same observations and candidate budget where the experiment requires it; separate proposal quality from end-to-end reconstruction quality.

Preserve negative results. If a final test influences the next design, treat it as diagnostic and use a fresh final set. Research scripts default to fresh `runs/` outputs and reject existing targets. Choose a new directory for another run. Evaluation uses bundled weights unless you pass `--models DIR`; new training outputs do not silently replace release models. Report failed cases, denominators, runtime exclusions, and unavailable real ground truth. The [experiment index](results/EXPERIMENTS.md) documents the existing protocols.

## Licensing and attribution

Original contributions use the repository's MIT license. New data, images, code, and weights need traceable provenance and compatible terms. A repository's code license does not automatically cover its checkpoints or datasets. Retain Google Scanned Objects' CC BY 4.0 notices when using the bundled scan derivatives; update [third-party notices](THIRD_PARTY_NOTICES.md) when adding a distributed dependency or asset.

Verify staged release resources with `python scripts/build_assets.py --check`. After changing bundled models, data or the workbench, stage a fresh `--out` directory and preserve the previous asset stage before replacing `objectdna/assets`. Portable wheels are checked with `python tools/check_wheel.py dist/objectdna-0.1.0-py3-none-any.whl`.
