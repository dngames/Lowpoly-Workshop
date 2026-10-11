# General modelling lessons

General techniques for reference-driven procedural assets. No consumer project specifications or measured production results are included.

## Contract and geometry
- **Spec beats sheet, but keep both.** Build the spec variant for the game and a sheet-proportioned
  variant to prove the design; report every place they differ (saddle height, wheelbase, rake).
- **Variant parameters leak.** Variants are defaults plus overrides; a new option added to the defaults
  for one variant silently changes the other. When adding a parameter, set it explicitly in every
  variant, then compare the old and new GLB vertex by vertex (positions and UVs) to prove nothing moved.
- **Moving parts need clearance by design.** Sweep every joint through its range (`contract.sweep`)
  and fix clashes in geometry: splay chainstays around a fat tyre, bend seat stays outward, keep a
  steerer coaxial with its head tube, shorten axle stubs to stop at the dropout. Exclude genuine real-world
  overlaps (toe overlap of pedal and front wheel) from the pairs instead of hiding them.
- **Raked axes.** If the game rotates a node about local +Y but the axis is tilted, give that node (and
  its children that turn with it) a rest rotation equal to the rake and put the pivot on the axis.
- **Proportions decide what fits.** Short character legs may not reach a normally
  proportioned vehicle: scale the bike to the rider (or the rider to the bike) by matching leg extension,
  and say so. Any version where the feet reach looks the same; only world size differs.
- **Flat plates under feet** look wrong: make soles part of the shoe loft so they follow its outline.

## Fitting
- Drawings contradict themselves across views; measure the contradiction (per-view preferred value)
  before deciding it is a modelling error.
- Seed iso/crouch poses sensibly (knees bent, root dropped); a pose solve from rest finds shallow minima.
- Classify JPEG sheets with a palette and a dark-ink class; threshold PNG sheets tighter.

## Blender and glTF
- Model in glTF axes and convert once (x, y, z) -> (x, -z, y). Export with `export_yup=True`.
- Build parents first and set `matrix_world` with an identity parent inverse; pivots stay exact.
- Clips: key every frame as local rotations computed from world matrices, put each clip on its own
  NLA track and keep a held one-frame "Stand" track active, otherwise the exported rest pose is the
  last keyed frame. Export with `NLA_TRACKS`, slide to zero, and turn off animation optimisation or
  constant channels (a held hip) disappear.
- A PNG writer in pure Python (`kit.atlas.write_png`) avoids Blender's image saving quirks; pack the
  atlas so the GLB embeds it.
- Weld vertices in render meshes or Freestyle outlines every polygon edge.
- Blender is not always on PATH: `setup_env.py --blender` installs one; `KIT_BLENDER` overrides.

## Hand-over
- Artifact hosts may refuse `.glb` and `.blend`: ship GLBs to the page as base64 scripts and the
  .blend files in the zip package.
- Give triangle counts per node, measured pivots, every check, fit scores per view, and the honest
  reason behind every remaining difference.
