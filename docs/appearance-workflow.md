# Coverage and controlled painting

Use this alongside the geometry, animation and export checks. Appearance evidence does not
replace any of those contracts.

## Ask for the missing views

After fitting the reference cameras:

```bash
lowpoly <asset> coverage
lowpoly <asset> coverage turnaround --size 256 --budget 4
```

This writes `out/coverage/report.json` and, per set, `review-palette.png` and
`review-coverage.png`, plus previews of the suggested cameras. The report records a hash
of the input geometry and fitted cameras. Red means a triangle was not observed sufficiently in the fitted
views; green means some geometric observation exists. The score uses depth-tested visible
pixels, front-facing angle and projected pixel density (view scale and distance), with
reduced confidence near boundaries. Equivalent near-orthographic projections get equivalent
credit even when their fitted distance/focal-scale pairs differ. Coverage
is weighted by surface area rather than triangle count. Tiny details can fall below the
pixel threshold; internal and buried surfaces may legitimately stay red.

Suggestions greedily target unseen area, then substantially better observations. Below-object
cameras are deliberate diagnostics for undersides; they are not automatically suitable player
views. Review the suggestions against the asset's support and intended use. Obtain the missing
reference or inspect the actual mesh before accepting a correction. Suggestions do not invent
reference evidence and are never inserted into `cams/` automatically.

The review camera is chosen separately and excluded from the suggestions. It contributes no
coverage credit, fitting score, paint votes or parameter optimisation. Keep it separate when
iterating: if a correction is tuned against it, select a fresh independent camera. This is a
visual generalisation check, not an automatic aesthetic verdict. These diagnostic images use
the CPU palette renderer; inspect final lighting, masks, tint and normals in the game bridge.

Run per set/variant and audit supported motion extremes separately. A camera observing a
moving arm in one pose does not certify its attachment or hidden paint in another pose.

## Optional projection-painting workflow

This is guidance for a future painter or manual texture edit, not an implemented image-service
integration. The coverage command makes no image-generation requests and modifies no mesh,
UVs, atlas, fitted camera or accepted paint.

- **Start from fixed geometry.** Supply the actual render, depth/position, normals and part
  masks. Describe materials, palette and mark-making. Do not invite new objects or details
  requiring geometry. A painted recess or lamp is not a modelled recess or lamp.
- **Use semantic masks.** Keep plaster, roof, timber, cloth, skin and decals separate. Material
  names are useful labels, but confirm them against normals and mesh placement. Keep existing
  consumer surface names, UV units and mask channels intact.
- **Treat source views by confidence.** Prefer close, face-on observations. Downweight silhouette
  edges and depth discontinuities; reject occluded projections. Quality alone is not permission
  to repaint owner-approved regions: those need an explicit unlocked edit mask.
- **Preserve accepted pixels.** Begin corrections with the current texture rendered on the
  model. Limit generation to missing or explicitly unlocked regions. Composite accepted pixels
  back exactly outside the declared seam band, and record that band as edited. Detect unchanged
  clay/background so it does not get marked as completed paint.
- **Correct seams locally.** Estimate colour drift from trusted overlap near the seam, then fade
  the correction and feather only inside the allowed band. Avoid global colour matching that
  shifts the established palette. Pad UV gutters and inspect the result under mipmaps.
- **Separate colour from lighting.** Request neutral overcast illumination without cast shadows
  for albedo sources. Overcast images still contain soft shading; do not claim intrinsic albedo
  was recovered. Check the finished texture with opposite sun directions and neutral lighting
  through the actual runtime material. Retain only deliberate, documented painted shading.
- **Spend texture resolution where it is seen.** Give important player-facing surfaces suitable
  texel density, keep distant surfaces economical and respect the game's shared atlases and
  memory budget. Do not replace modular tiled materials with a unique giant level atlas by
  default.
- **Keep variants and LODs consistent.** Establish one accepted paint source, then transfer it
  to other LODs with verified UV/material correspondence. Audit seams, tint masks and feature
  placement across transitions; independent repainting can produce visible colour pops.
- **Save reproducible checkpoints.** Keep input renders, masks, prompts, source hashes, costs,
  accepted output and projection settings. Resume only matching inputs, preserve rollback,
  and run a small dry comparison before a large paid batch.

Estimated image normals compared with mesh normals may help flag invented geometry. They are
an optional, fallible review aid: stylized paint and image inference can disagree with a correct
mesh. Do not automatically remodel or reject an asset from this signal.

## Source and scope

These workflow ideas were informed by [Trompe](https://github.com/Patch-gg/trompe), reviewed at
revision `fd81fe4`: its camera planner, confidence-weighted atlas projection, local compositing,
and independent-view experiments. Our coverage implementation uses the kit's existing CPU
rasterizer and geometry; no external source code, image models or service dependency is imported.
The original experiment is small; its model rankings and scene-specific thresholds are not
universal acceptance rules for this kit.
