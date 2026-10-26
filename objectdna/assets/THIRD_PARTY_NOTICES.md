# Third-party notices

Original ObjectDNA code, procedural data and trained weights use the MIT license. Bundled Google physical-scan derivatives remain CC BY 4.0, with notices and processing provenance in `data/real`.

The distributable workbench bundles Three.js (including OrbitControls) and Vite's module-preload runtime. Their original notices are retained at `web/public/licenses/`, copied into the production build and portable wheel:

- Three.js: MIT, full notice in `licenses/three-MIT.txt` in the served workbench.
- Vite: MIT and included third-party notices, full upstream file in `licenses/vite-LICENSE.md`.

Python libraries and build/test dependencies are installed separately from the pinned requirements. Their licenses remain with their distributions; no Python dependency binaries are bundled in ObjectDNA's source archive or wheel. CadQuery's Apache 2.0 and OpenCascade's applicable terms are distinct from ObjectDNA's MIT source license.

Optional pretrained systems are not bundled or downloaded by default. Code, checkpoint and dataset terms differ; see `docs/UPSTREAM_LICENSES.md`. In particular, the application license does not relicense noncommercial checkpoints from other projects.
