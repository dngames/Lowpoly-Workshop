# Reproducible builds and model validation

Read this before the first build and before handing over an asset. Use the loop:
build -> measure -> inspect -> make a targeted correction -> repeat affected checks.
Numeric checks and visual review provide different evidence; an asset needs both.
This is workflow guidance, not a claim that the CLI implements every check below.

## Establish the build environment

- Use the kit's tested Blender **4.5 LTS** series. Record the exact Blender patch version,
  Blender's embedded Python version, host Python version, kit revision and asset parameters
  with the results. The setup script resolves a patch within the series; that alone does not
  pin an exact executable. Reuse the recorded version for a reproducibility comparison.
- Run the self-test on a new machine or after changing Blender. Verify release/API claims
  against official documentation before upgrading, then test the builder, exporter and renderer.
- Prefer the kit CLI. Its Blender launcher already uses background mode, factory startup and
  `--python-exit-code 1`, and checks the process result. A custom launcher must preserve this
  behaviour: put the exit-code option before `--python`, and script arguments after `--`.
  A render or output file left by an earlier run is not evidence that this build succeeded.
- Prefer `bpy.data` and `bmesh` for geometry work where practical. Operators can work headlessly,
  but may require selection, active-object, mode or editor context. Keep supported import,
  export and render operators; establish their context explicitly and test in background mode.
- When inspecting modifiers, inspect the evaluated mesh. An evaluated object's `to_mesh()`
  result is temporary: release it with `to_mesh_clear()` in a `finally` block, or deliberately
  copy it to a persistent mesh when baking. It does not replace the source mesh automatically.

## Keep units and parameters explicit

Author geometry in metres with glTF axes (+Y up, facing +Z), converting to Blender axes once
at the existing bridge. Use named parameters with units for proportions, thickness and clearance.
Keep the distinction between generator/rig degrees and consumer radians explicit.

Scene unit settings alone do not prove exported scale; their effect depends on the operation and
exporter. Measure the exported GLB in metres, including its node transforms. Assert the required
dimensions, support origin, parents and pivots against the asset contract. A wall-top animal,
swimmer or flyer has its own support convention; do not force every asset onto ground zero.

## Audit geometry at the right stage

Use `extra_checks` for asset-specific checks and audit the actual exported file as well as the
generator. Where modifiers are involved, also inspect evaluated geometry before export.

| Evidence | What to check |
|---|---|
| Build identity | Tool versions, source revision, parameter set and current output paths |
| Contract | Exported dimensions, axes, root/node names, parents, pivots and rest transforms |
| Geometry | Finite coordinates, triangle counts including children/paint, loose vertices, degenerate faces and unexpected boundaries |
| Surface | Winding, normals, material assignments, UVs, palette/mask channels and tint tags |
| Overlaps | No z-fighting at the output's `view_m` (`kit/surfaces.py`); hidden overlaps and back-to-back pairs listed; GPU vertices per position; piece shots looked at |
| Motion | Signed ranges, local root attachment, clearances and any required ground contacts |
| Preservation | Unchanged roots/variants keep their parsed geometry, materials and transforms |

Choose tolerances from the asset's scale and smallest intentional feature. Length tolerances use
metres; triangle-area tolerances use square metres. A universal area cutoff of `1e-4 m²` can reject
valid tiny eyes, fins or butterfly faces. Do not delete small faces merely to reduce an audit count.

Interpret mesh diagnostics rather than turning every count into a universal zero requirement:

- Check primitive shells for closure before hidden-face cleanup. Intended cards or hidden
  boundaries after conservative cleanup need explicit treatment. Printable-solid requirements
  do not describe every game mesh.
- Consistent winding across adjacent faces does not by itself prove outward orientation of a
  whole shell. Check orientation separately where a closed solid is required.
  `kit.organic.surface_orientation(faces)` checks directed edge pairs and positive signed volume
  for each original closed solid, before hidden-face cleanup. A reversed pool wall can pass
  undirected edge closure while disappearing from inside the pool.
- A raw self-BVH overlap count is not a self-intersection verdict. Blender 4.5 already filters
  identical triangles and shared-edge pairs in self-overlap. Know which pairs the implementation
  reports, use an appropriate triangle-level test, and distinguish intended joint overlap from
  an unwanted exposed intersection. Shared vertices and coplanar contacts still need care.
- Preserve capped overlaps between independently moving parts. Never globally weld or remesh
  an articulated asset just to make a generic manifold/intersection report green.

## Coplanar overlaps and depth resolution

For a camera with a 0.25 m near plane and a 24-bit depth buffer, two layers `g` metres apart
stay ordered to about `sqrt(g * 4.2e6)` m: 0.5 mm to 46 m, 1 mm to 65 m, 2.4 mm to 100 m. A patch,
decal or flush plank closer than that to a face of a different look flickers in the distance;
the same faces in the same colour and UV only cost triangles (hidden overlaps). Set `view_m` from
how far the asset is seen (a summit arch or a church tower: 150 m or more). Prefer painting the
detail into the atlas over a second layer. Two-sided cards (a mirrored pair over the same
corners) and faces on the ground facing down are not findings. Repeat these checks through the consuming engine’s material and camera settings.

## Closed-shell LODs: static organic props only

A static organic prop (a rock, a boulder or a group of them, a cliff of rounded masses) may take
its far levels from its LOD0 as **closed shells**: LOD0's geometry voxel-remeshed into one
watertight surface (overlapping and buried pieces become a union), decimated by edge collapse to
each level's triangle target, its bounds fitted back onto LOD0's (one reference envelope for every
far level), each face taking the colour and material of the nearest LOD0 face. The far levels then
keep LOD0's silhouette and size (no pop at a switch) and each is one closed surface (no holes, no
overlapping islands). `lowpoly ASSET shell-lods` is the implementation.

- **Never** for anything articulated, rigged or skinned, nor for parts that move against each
  other (wheels, limbs, doors, cloth): a remesh welds what must stay separate and destroys pivots,
  caps and joint overlaps. Those keep their authored levels.
- Not for hard-edged architecture or masonry: the remesh rounds its edges and corners away.
- Leave out what must not merge (grass tufts, decals, glow, cloth): shell only the solid body.
- Prove it on the shipped file: each far level welded by position has every edge between exactly
  two triangles, one connected piece, bounds inside LOD0's; triangle counts before and after.

## Write outputs atomically

Write every GLB, JSON report and package to a temporary file beside its target and rename it over
the target in one step (`lowpoly_workshop.kit.atomic.replacing` and `write_json`). An interrupted or failed run then leaves the previous file or the new one, never half
of one that a later step, a test or the game would read as valid. Blender's own `.blend` save
already works this way.
- Closure, attachment and appearance are separate checks. A closed hand can still float away
  from its wrist, and a remote contact cannot prove a local moving root is attached.

## Inspect a review sheet and the runtime

Review front, back, both sides, top and a useful three-quarter view, adapting the views to the
asset and available references. After fitting, run the best-view paint check (`lowpoly <asset> paint`, see [legacy-fitting.md](legacy-fitting.md)) and read every flagged face against the sheet. Label the output, pose and camera; use consistent framing for
before/after comparisons. Inspect silhouette, proportions, thickness, paint and exposed interiors.

Run `lowpoly <asset> coverage` after fitting to identify poorly observed surfaces and
review an independent camera. Recommendations are not reference evidence; preserve the
separation between observed coverage and hypothetical coverage after added cameras.
See [appearance-workflow.md](appearance-workflow.md) for masks, seams and relighting checks.

For articulated assets, include rest and motion extremes in the review sheet and sample the full
supported ranges numerically. Inspect held props and accessories in their supported states.
Then inspect the exported asset through the actual loader/material bridge, including normals,
back-face visibility, masks and runtime tint. Compare the game's motion with the audit's motion;
a lab using the intended contract cannot certify a consumer that applies different signs or names.

A passing numeric report does not forbid visual findings about topology: gaps, flying joints,
buried paint and exposed caps still need fixing. Sheet-fit scores also cannot prove anatomy or
runtime correctness. See [legacy-fitting.md](legacy-fitting.md) and [modelling.md](modelling.md).

## Make the smallest correction that fixes the cause

For a proportion or fit adjustment, change named parameters first and review the diff. Structural
problems need structural fixes: missing caps, wrong parents/pivots, broken topology, export errors
and material tags cannot always be repaired by tuning constants. Preserve the game contract and
unaffected variants; do not move a pivot to compensate for a consumer bug.

Rebuild after a change and rerun the affected numeric and visual checks. Fix the cause rather
than loosening an assertion. Report passes, failures, intentional exceptions and checks not run
separately, with triangle counts, measured contract values and the review images. Keep evidence
from the current build and state any remaining runtime mismatch explicitly.

Printing wall thicknesses, hole clearances, support angles and watertight-solid rules belong to
a separate printing brief. Add them only when a deliverable actually needs to be manufactured.
