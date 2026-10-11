# Testing and compatibility

Python 3.10+ / Blender 4.5; bundled Three.js 0.186.1. Local target: Windows, Python 3.12, Blender 4.5.14. CI config covers Windows/Linux, Python 3.10/3.12; configuration alone is not a passed remote run. VALIDATION.md records observed results.

```sh
python -m unittest discover -s tests -v
python -m unittest discover -s scripts -p 'test_*.py' -v
lowpoly selftest
lowpoly selftest --blender
```

Tests cover topology, wrapped fringe, attachment frames, posed contact/gaps, containment/support rays, decal underside/distortion, stable skin weights, reference immutability/provider requests, path containment, templates, cache and release manifests.

Blender selftest exports all starters, validates nodes/pivots/empties/geometry/budgets/masks/closed shells, exports a generic skeleton with finite posed roundtrip, renders an actual-export underside, and checks UV survival through duplicate-face removal. It writes under TEMP; set TEMP/TMP to the task scratch drive.

scripts/test_viewer.mjs takes a local review URL and screenshot folder. It requires Playwright separately and checks controls, browser errors and absence of external requests.

Limits: finite contact/collision sampling, visual skin-weight quality, artistic similarity and semantic texture mistakes need judgement. Neural image-to-mesh, engine retargeting/physics are absent. Image transport is tested with mocks unless a separate live call is recorded.
