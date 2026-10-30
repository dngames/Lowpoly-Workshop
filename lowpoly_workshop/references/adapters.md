# Game integration

Keep engine contracts in profiles/per-output overrides and small staging adapters. The core knows glTF units/axes, generic nodes/sockets, masks/materials and declared relations. It does not depend on skin IDs, asset directories or runtime skeleton names.

Only generic portable/mobile profiles are bundled. Put consumer-specific triangle budgets, texture-mask meanings, node conventions and staging scripts in the consuming project, outside this package. Choose RGB or RGBA mask encoding through the documented per-output contract and atlas options.

For another game: choose required units/origin/socket axes; override output budgets/topology/material policy; supply a skeleton through skin(nodes,p) when needed; copy verified outputs through a target-aware adapter; run that game's checks and review actual lighting/motion. Mask conversion to WebP belongs to an adapter that understands data channels/alpha.

Blender 4.5 and bundled Three.js loading are tested. Other engines' glTF workflows, PBR materials, collision, LODs, retargeting and physics are not certified by this preview and remain adapter work.

## Generic policy overrides

Start from portable or mobile and declare a per-output contract for your consuming project. For example, `"contract": {"budget": 2345, "mask_channels": "RGBA"}` changes the triangle limit and mask encoding without needing a named consumer profile. Construct the generator atlas with `mask_channels="RGBA"` too, and assign cells to whichever R/G/B/A channels the consumer uses. Channel meanings, exact budgets, runtime node naming and staging remain in that consuming project. These options are unchanged from the original portable API.

## Optional named-material vertex colours

An output can opt out of an image atlas with `"vertex_surfaces": {"body": "painted_body"}`.
Map every used palette cell to a material name. The exporter writes linear `COLOR_0`, UVs
and those names with no embedded image; the checker verifies the declared names and colour
data. Set a suitable `contract.max_materials` for multi-material outputs. Do not combine this
mode with `kit_mask`: atlas/mask outputs remain the default and retain their existing policy.

Image-free means no picture inside the file, not an untextured model: the material names are
where a consuming game applies its own tiling textures at runtime (wood, stone, plaster, roof),
while the names it treats as plain colour stay flat. Choose names the consumer textures for every
surface that should carry grain. Workshop renders show only the palette colours, not the game's
textures.

`"runtime_uv": true` additionally projects solid UVs in metres. Material names beginning
`decal_` require explicit local 0–1 face UVs. This follows the inherited V-down adapter
convention; verify it in the consuming renderer. The generic `kit.runtime_uv.face_uvs` helper
is also available separately. Material meanings, shader flags and per-engine conversion are
not inferred or bundled. Rebuild/check and inspect the actual exported model in the target.

For image-free outputs, optional `contract.view_m` conflict checks are conservative:
matching UVs cannot prove identical vertex/material colours, so coplanar overlaps are
reported for review rather than silently classified as identical paint.
