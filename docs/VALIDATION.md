# Release validation and verified scope

ObjectDNA 0.1.0 delivers the user-authorized verified subset: aligned point-cloud or processed-mesh reconstruction into a bounded, editable single-solid CAD grammar. The complete arbitrary-object/photo/assembly vision exceeds the available local, CPU-first development and physical-measurement evidence. No unsupported stage is presented as functioning.

## Product evidence

| Requirement | Current evidence |
|---|---|
| Point clouds and scan import | Finite numeric XYZ/CSV/PTS, ASCII PCD, PLY, STL, OBJ, and checked numeric NPY imports; malformed-input tests; browser import/recovery checks. |
| Brackets, enclosures, machined blocks | Three authored CAD families; noisy/missing-side synthetic acquisition; independent implicit CSG field versus exact-solid occupancy and face checks. |
| Editable CAD and exports | Actual CadQuery single-solid validity, nontrivial width edits, through-bore occupancy, generated source execution, fresh-process STEP readback. STEP/STL/CadQuery/evidence exports. |
| Workbench | Thirteen end-to-end browser checks; live WebGL mesh and source overlay, feature tree, controls, exact rebuild, export, unknown-scale rejection, failure recovery and resized mobile geometry fit. |
| Real object demonstration | Google physical scan derivatives, processed mesh → points → CAD → actual browser STEP download → valid STEP readback with matching bounds. Cereal outer-envelope hypothesis plus flared-tray failure. No independent caliper truth. |
| Original trained contribution | 600-scan thickness network and 180-object pairwise ranker. Transparent JSON weights, source/data/model hashes, cards and procedural reproduction scripts. |
| Controlled evaluation | Two disjoint 48-object final synthetic sets, v1 negative result retained, fresh v2 compact-proposal comparison, refinement/proposal/ranker ablations, per-case outputs and failures. |
| Runtime evidence | Separate warmed single-thread 48-object × 3-repeat timing study after heavyweight owned tasks ended; randomized order; all raw timings retained. |
| Reproducibility | Frozen-source replay of 24 method-results exactly matched retained CAD specs and geometry metrics using the tested dependency versions. This is not cross-platform bitwise reproducibility. |
| Portable distribution | Independently extracted wheel serves bundled workbench and five samples, finds both trained models and validates every staged asset hash, runs compact inference, exports valid STEP. |
| Presentation | Original identity, actual current-source desktop/mobile/real-case screenshots, a silent sampled-screen walkthrough, benchmark figures, README, architecture, model cards, licenses and attribution. |
| Tests and CI | Local source, browser, wheel, CLI and independent review evidence. GitHub Actions exercises Linux and macOS source tests, staged resources and the portable wheel; Linux also runs the browser workflow. Inspect the repository workflow badge for current hosted status. |

## Measured results

Fresh synthetic test: compact proposals used 7.25 initial candidates versus 23.71 for dense search. Including three refined candidates in each mode, total scoring fell by 61.6%. Mean IoU was 0.92935 versus 0.92850; sampled unsquared Chamfer 0.86899 versus 0.86855 mm; external generated-dimension MAE 0.36558 versus 0.36764 mm. Both selected the correct family on 47/48 cases and produced valid, width-editable solids on 48/48. Unconditional correct family plus bore-count success was 12/16 true blocks.

The quiet timing repeat measured 0.10538 s compact versus 0.17711 s dense, a 1.68× ratio of mean per-case medians. Cold imports, CAD validation/export and UI latency are excluded. Original ranker results regressed; geometric scoring is the release default and learned scoring remains experimental.

The inference UI's surface discrepancy combines approximate analytic CSG fitting residual and sampled reverse distance. It is distinct from benchmark Chamfer over two independent 7,000-point samples. Same-solid sampling floor and Monte Carlo IoU definitions are retained in the experiment reports.

## Independent checks and material limits

The focused independent review found and verified fixes for preallocation NPY bounds, malformed mesh error handling and export preservation. See [REVIEW.md](REVIEW.md). The portable-wheel check also reopened the actual browser-downloaded physical cereal-box STEP and verified one valid solid with bounds matching the shown candidate. Readback uses the same kernel, not a second CAD application.

VGGT image inference is an optional, unvalidated bridge requiring separately installed source and licensed local weights. Video frame extraction is a local FFmpeg helper. No pretrained VGGT, CAD-Recode, cadrille or PartCrafter inference was executed or used as a benchmark. Their reported scores are never compared directly with ObjectDNA's local grammar tests. Part-level modeling, arbitrary pose, free-form surfaces, fillets, threads, hidden cavities, mechanical fit/function, materials and manufacturing tolerances remain outside verified scope.

The real samples have no ground-truth CAD or independent measured dimensions. Real volumetric IoU and dimensional accuracy are explicitly null. The carton is an envelope, with unknown interior/shell; the tray is outside the supported grammar. A support threshold or valid CAD result is not a physical accuracy certificate.

The final video is H.264, 1440 × 1000, 149 frames at 4 fps, 37.25 seconds, silent. Full decode and representative current-source screenshots were checked; no sound or normal-speed audiovisual approval is implied. Capture pacing is not runtime evidence.

Exact result artifacts: [experiments](../results/EXPERIMENTS.md), [real demos](../results/real-v1/REPORT.md), [wheel check](../results/wheel-validation.json), [replay check](../results/replay-verification.json), and [browser report](assets/browser-report.json).

## Final local check receipt

The full current Python suite completed with **88 passed** and 16 upstream deprecation warnings, in 162.45 seconds. A subsequent resource/hash test passed after adding the original Three.js and Vite license notices to the unchanged frontend build. The final frontend JS/CSS content hashes remain the same as the captured workbench. Complete test output is in `results/test-report.txt`; final wheel and media checks are recorded separately.


## Publication hardening

The public release also validates COUNT-aware PCD import, quantized/duplicate scan input, unknown scale for raw point arrays, exact preservation of untouched dimensions, keyboard controls, retained-upload calibration, safe fresh research outputs and custom numerical model paths. Thirteen current browser checks passed. WCAG-tagged automated audits report zero violations in the workbench and export dialog; canvas/glyph checks still require scoped visual review and do not establish full accessibility conformance. Runtime fitting residuals use an approximate analytic CSG field, distinct from sampled Chamfer and independent dimensional error.
