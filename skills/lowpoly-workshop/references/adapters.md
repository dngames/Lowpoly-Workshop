# Game integration

Keep engine contracts in profiles/per-output overrides and small staging adapters. The core knows glTF units/axes, generic nodes/sockets, masks/materials and declared relations. It does not depend on skin IDs, asset directories or runtime skeleton names.

Only generic portable/mobile profiles are bundled. Put consumer-specific triangle budgets, texture-mask meanings, node conventions and staging scripts in the consuming project, outside this package. Choose RGB or RGBA mask encoding through the documented per-output contract and atlas options.

For another game: choose required units/origin/socket axes; override output budgets/topology/material policy; supply a skeleton through skin(nodes,p) when needed; copy verified outputs through a target-aware adapter; run that game's checks and review actual lighting/motion. Mask conversion to WebP belongs to an adapter that understands data channels/alpha.

Blender 4.5 and bundled Three.js loading are tested. Other engines' glTF workflows, PBR materials, collision, LODs, retargeting and physics are not certified by this preview and remain adapter work.

## Generic policy overrides

Start from portable or mobile and declare a per-output contract for your consuming project. For example, `"contract": {"budget": 2345, "mask_channels": "RGBA"}` changes the triangle limit and mask encoding without needing a named consumer profile. Construct the generator atlas with `mask_channels="RGBA"` too, and assign cells to whichever R/G/B/A channels the consumer uses. Channel meanings, exact budgets, runtime node naming and staging remain in that consuming project. These options are unchanged from the original portable API.
