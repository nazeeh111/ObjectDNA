# Current-source workbench captures

`walkthrough.mp4` is the selected silent demonstration: H.264, 1440 × 1000, 4 fps, 149 frames, 37.25 seconds (1,375,622 bytes). It samples actual browser frames while exercising the real local backend. Captured waits and action pacing are not a performance benchmark. The final browser script completed thirteen checks with zero JavaScript page errors. One HTTP 422 console message is the expected malformed-import rejection. A separate direct API request also verifies that uncalibrated metric export is rejected.

`workbench-demo.gif` is a small README preview derived from the first 12 seconds of that actual recording: 800 × 556, 4 fps, 48 frames, 717,723 bytes. Link the preview or a still image to the full MP4 or its release attachment. Both selected media files were fully decoded with FFmpeg without errors.

The walkthrough shows reconstructed bracket geometry, source/CAD overlays, keyboard camera controls, a dimension rebuild preserving untouched parameter precision and keyboard focus, reset, compact learned proposals, a processed physical cereal-carton scan and actual STEP download, an unsupported flared tray, relative-scale export restrictions, in-place reference calibration, failed-import recovery, and bore-feature navigation. No displayed result was replaced by a mock response.

Selected current screenshots:

- `workbench.png`: the live scan-to-CAD engine applied to the explicitly synthetic bracket fixture.
- `feature-tree.png`: the editable construction tree and source library.
- `dimension-edit.png`: a successful geometry rebuild after a width change.
- `real-cereal-scan.png`: the licensed physical-scan derivative and outer-envelope candidate.
- `real-failure-case.png`: the flared tray, clearly marked as a hypothesis requiring review.
- `workbench-mobile.png`: the final 390 px viewport, fitted geometry and readable quick-link backing plate.

`browser-report.json` retains the thirteen functional checks, measured initial metrics and tested JavaScript hash. The report distinguishes the full functional-run bundle from the final build. A later mobile-only CSS correction has separate rendering evidence in `mobile-report.json`; the final supplemental-axis role attribute is pixel-identical and received a fresh axe check. Neither change alters functional JavaScript behavior. That targeted check covers geometry projection, horizontal overflow, quick-link contrast and keyboard parameter navigation. `accessibility-report.json` records zero reported violations in axe's WCAG-tagged checks for the desktop workbench and export dialog, along with manual-review items. Automated checks are scoped evidence rather than a complete accessibility conformance claim.

Reproduce against a running local server with `npm run test:ui -- --record` and `npm run test:a11y` in `web/`. Use installed Google Chrome locally; set `OBJECTDNA_BROWSER=chromium` for Playwright's installed Chromium in CI. `npm run demo:preview` derives the small GIF with the free FFmpeg CLI. Raw frame captures and failed trials remain in ignored `web/.cache/browser-runs` or in the task-local work folder, outside the distributable repository. The video is sampled and silent; full decode and representative-frame inspection are separate from normal-speed audiovisual judgment.

Physical scan material is Google LLC, 2020, CC BY 4.0. See `data/real/provenance.json` for original sources, transformations and attribution. UI, synthetic fixtures, scripts and original branding use the repository's MIT license.
