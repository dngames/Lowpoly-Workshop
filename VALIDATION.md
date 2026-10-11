# Validation — 2026-10-11

Version 0.2.2. Local environment: Windows, Python 3.12.14, Blender 4.5.14, bundled Three.js 0.186.1. Project, scratch, dependency and generated-output locations were on D:.

## Compatibility with the previous release

- Executable ASTs of all 37 non-version Python modules match the previous release after excluding docstrings. The only core-source edit is a documentation example; version metadata changed separately.
- All five starter generators/specs and both generic portable/mobile profiles are unchanged.
- Only consumer-specific profile/adapter data and documentation examples were removed or generalized. Generic per-output policy overrides remain supported.

## Observed checks

- 55 core and 6 inherited Python regressions passed, including synthetic reference fitting, topology, wrapped surfaces, attachment frames, posed contact/clearance/support, UV/decal rules, weights, reference/provider mocks, cache/approval staleness, path containment and archive checksums.
- Blender selftest rebuilt all five starters and passed node hierarchy, pivot/socket, geometry roundtrip, budget, atlas/mask and closed-shell checks.
- Skeletal export/reimport passed with 8 bones and 378 finite posed vertices. UV corners survived duplicate-face cleanup.
- Actual-export underside and articulated-pose renders passed; pose geometry differed as expected.
- An independent RGBA mask fixture passed its custom per-output budget and channel-policy checks, including fourth-channel data.
- Offline Playwright viewer passed with visible meshes, two animation clips, view/material/socket controls, desktop/mobile layout, zero external requests and zero browser errors. Screenshots were inspected.
- A checksummed generic asset bundle was extracted into a clean folder and rebuilt using its own bundled toolkit: build, checks, review, page and packaging passed.
- Installed wheel templates/geometry passed outside the source checkout. The MIT metadata, license files and bundled documentation were inspected.
- Source and wheel contents were scanned for known excluded consumer identifiers and personal paths; none were found in the sanitized artifacts. PNG copies have no EXIF metadata. This is a targeted audit, not a mathematical guarantee of absence.

## Limits

No comparative product benchmark, paid live image-provider call, Unity/Unreal/Godot import or animation retargeting was performed. Finite geometric/contact tests and sampled poses do not prove all animations or artistic quality. GitHub CI covers Windows/Linux and Python 3.10/3.12; consult the current release's linked run for its remote result. Local reports and private provenance details are excluded from distribution.
