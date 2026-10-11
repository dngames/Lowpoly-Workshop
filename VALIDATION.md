# Validation - 2026-10-11

Version 0.3.0. Local environment: Windows, Python 3.12.14, Blender 4.5.14, bundled Three.js 0.186.1. Project, scratch, dependencies and generated output were on D:.

## Observed checks

- 77 core plus 6 inherited regressions passed. This includes 22 new guided-review regressions: saved progress, stage ordering, required/optional decisions, source/export/reference/image/check changes, stale builds, evidence containment, skinned-evidence requirements, CLI/page and legacy approval behaviour. Unit workflow records/images are synthetic fixtures, not artistic quality measurements.
- Full Blender selftest passed all five original starters, geometry roundtrip, names/pivots/sockets, budgets, atlas/masks, closed solids, generic skeletal reimport (8 bones/378 finite posed vertices), UV survival and actual-export posed renders.
- Guided Blender selftest built a real static prop, bound four features to exported geometry and rendered 18 images. Original-reference crop validation works inside Blender without installing Pillow into its bundled Python. Current build/render/check evidence was admitted; no artistic acceptance was recorded.
- A separate articulated guided fixture linked an original diagram crop to an arm feature and rendered 33 actual-export images, including declared poses and checker views.
- The offline Playwright viewer passed with two animation clips, feature selection/close-up navigation, reference crop display, view/material/socket controls, visible meshes, desktop/mobile layout, zero external requests and zero browser errors. Screenshots were inspected.

The release preparation also verifies a rebuilt extracted asset bundle, installed wheel, synchronized packaged docs, checksummed source/wheel archives, targeted privacy scan and remote CI. The release notes link the completed CI run and record distribution results.

## Compatibility and limits

The five starter generators and their default asset specs remain unchanged; guided mode is opt-in through `new --guided` or feature/workflow declarations. Both portable/mobile profiles and generic contract overrides remain available. Existing projects do not acquire staged-review requirements unless they opt in. A new build-cache source field may cause a one-time rebuild.

Acceptance remains a reviewer assertion. Hashes prove freshness, not the correctness of a screenshot or visual decision. Invalidation is conservative across project/tool changes and render-index changes. Declared rigid poses are sampled; skeletal deformation needs separate evidence. No regional appearance scoring, anatomy-specific gates, material inference or visual-hull generator was added.

No comparative product benchmark, paid live provider call, target-engine import or animation retargeting was performed. Private consumer data and local audit reports are excluded from distribution. Targeted scans do not prove the absence of unknown sensitive information.
