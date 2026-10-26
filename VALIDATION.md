# Validation

## 2026-10-26 — Station Rest House reference-geometry correction

- Rebuilt the body at 14 × 7 m and the roof as a continuous pitched irimoya with actual timber end gables, lower hip skirt and a closed front cross-gable. Clay comparisons separate the changed geometry from the unchanged material artwork.
- The full Blender selftest passes export/skeletal/UV roundtrips and actual-export guided rendering.
- All 134 unit regressions pass, including body depth, real timber faces, roof slope continuity and preventing hip tiles from bridging the timber boundary. All four portable and named-surface assets pass native checks, at 34,356 / 5,208 / 1,220 / 44 triangles.
- Tiny Tour's installed public asset passes 16 focused loader/package-model tests; lint, type checking and all three world checks pass. The broad feature lane was interrupted; no full lane or performance benchmark is claimed.
- The world viewer did not finish loading high textures within the bounded inspection; no successful in-game screenshot is claimed.
- The original six-view sheet remains unchanged. Comparison images show actual exported geometry with separately framed cameras, not fitted overlays or artistic acceptance.

## 2026-10-26 — textured Station Rest House remodel

- 132 core regressions pass, including painted texture variation, closed/outward tile relief, facade positions, canopy support reach and bench seating. Full Blender selftest passes export/skeletal/UV roundtrips and actual-export renders.
- The rebuilt portable asset passes all 36 native checks at 34,680 / 5,132 / 1,212 / 28 triangles with an embedded 2048-square painted atlas. Each structural primitive passes directed-edge/closed-volume orientation checks; the complete overlapping assembly is not asserted to be a single watertight solid.
- Original design input remains byte-identical. New material artwork, its prompt, packed pixels and provenance are included. The actual-export before/after panel records separate source/model/image hashes; no artistic approval is asserted.
- The separate Tiny Tour candidate uses its existing named-material and physical-UV contract because the runtime replaces imported materials. Three focused loader tests, targeted lint and typecheck pass in the consuming repository; the live world asset is not replaced.

## 2026-10-26 — reference-first example presentation

- The Station Rest House original six-view sheet and prompt are copied byte-for-byte from the recorded Tiny Tour commit. The image hash matches the registered original, docs copy, local viewer and source bundle.
- The reference-bearing building project rebuilds successfully, passes all 39 native checks, renders its declared views/diagnostics and packages the original image and prompt. Three architectural regressions pass. Geometry is unchanged.
- README/tutorial links, diagram SVG syntax and packaged reference synchronization pass. The three new explanatory SVGs are rendered and inspected locally. They are explicitly labelled as later notes for procedural exercises, not historical originals or evidence of reference matching.

## 2026-10-26 — Tiny Tour building example

- 131 core regressions pass, including architectural facade positions across detail levels, canopy support reach, bench seating and base/height limits. Full Blender selftest passes export/skeletal/UV roundtrips and actual-export rendering (headless EGL warnings do not prevent completion).
- All four adapted Station Rest House levels match the recorded Tiny Tour source geometry, palette cells, UVs, pivots and parent names exactly in an independent source comparison.
- The standalone building passes all 39 native checks at 685 / 517 / 201 / 28 triangles. The viewer, source bundle and 22 actual-export images (16 declared views plus six component diagnostics) are generated successfully.
- Picture evidence matches the adapted source and exports. This is the explicitly owner-requested first-party building exception; no reference sheet, game texture, runtime placement or artistic approval is imported.

## 2026-10-26 — high-detail character companion

- 128 core unit regressions pass, including the high-detail example's closed solid nodes, editable height/ground contact, and sampled gesture attachment/head clearance.
- The full Blender selftest passes export roundtrips, skeletal/UV checks and actual-export renders. Headless EGL warnings occur, but the pipeline completes.
- The original 21,162-triangle character passes all 77 native export checks. Twelve actual-GLB review images, the local viewer and checksummed source bundle are generated successfully.
- The source/spec and picture evidence hashes match the exported scratch project. The example remains a rigid-part stylized character; no sculpt, skeletal deformation, retopology or artistic acceptance is claimed.

## 2026-10-26 — character tutorial

- 123 core unit regressions pass, including closed character geometry, editable height/ground contact, and sampled greeting attachment/head clearance.
- Full Blender selftest passes export roundtrips, skeletal/UV checks and actual-export renders; headless EGL warnings did not prevent completion.
- The original trail-guide example builds and passes native export checks at 1,010 triangles. Its review contains 12 actual-export views across rest, half-raised and waving poses; page and source package generation complete.
- Tutorial pictures carry source/spec, exported GLB and image hashes. They record evidence, not artistic acceptance. The example uses rigid nodes, with no skinning, retargeting or target-game integration claim.

## 2026-10-26 — unreleased coverage and legacy parity update

Observed locally on Linux with host Python 3.12, the official Blender 4.5.15 bpy module
in its separate Python 3.11 environment, and the standalone Workshop launcher.

- 119 core unit regressions and 6 inherited regressions pass.
- Full Blender selftest passes: all starter exports, skeletal roundtrip, UV survival,
  actual-export renders, and guided feature evidence. EGL warnings occurred during
  headless rendering, but the render/check pipeline completed successfully.
- A synthetic static-organic shell smoke passes closure, outward orientation, budgets and
  source-bound preservation at 198 / 78 / 30 triangles. Articulated source is rejected.
- A mixed-output smoke passes atlas → named-material vertex-colour → atlas exports in one
  process, checks the image-free palette output and verifies cache reuse. All three
  actual GLBs produce component diagnostic images.
- A synthetic supplied-reference CLI regression runs coverage and paint diagnostics and
  verifies that project source, reference image and fitted camera hashes stay unchanged.
- The wheel builds, installs outside the checkout and passes its installed selftest;
  new modules import successfully. Packaged code/docs/notices match the checkout.
- Skill/package reference synchronization passes. No consumer artwork, model exports,
  production screenshots or service credentials were imported.

These are functional checks, not a comparative benchmark or artistic acceptance. No paid
image service, target-game integration or new remote CI result is claimed. Older consumer
bindings and the newer Workshop equivalents are documented in `docs/legacy-port-audit.md`.

## Historical validation — 2026-10-11

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
