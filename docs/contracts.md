# Project contract, schema version 2

Projects contain asset.json, gen.py, optional ref/ and cams/, and generated out/. Configured paths must stay inside the project, including symlinks. Python validation runs before generator import. See the bundled JSON schema and starter examples.

## Coordinates and nodes

Metres, +Y up, +Z forward, +X toward the model's left. Face points and pivots use **world rest coordinates**. Each node has parent, pivot, faces and optional orthonormal rot. Faces are `(points, atlas_cell, explicit_uv_or_None, thin_flag)`, wound outward. Parents are validated/sorted; empty socket nodes survive export.

Generators provide `ATLAS`, `params(variant=None, overrides=None)` and `build(p)`. Optional hooks: extras(p, scale), clips(nodes, p), skin(nodes, p), show_scenes(asset), fit_scene(set, view, extra, asset), fit_extra(set, view), extra_checks(asset, report). Core module docstrings define their data. Keep inputs within the project for portable bundles/cache.

## Outputs and profiles

Outputs contain file, optional variant/scale/nodes/exclude/origin/kit_mask/clips/contract. File ends in .glb; blend and atlas companions are emitted beside it. Origin subtracts a named node's pivot for accessory-local output. Node selection preserves declared parents/empties.

Profile selects portable or mobile. Per-output contract overrides: budget, pivot_tolerance, max_materials, square_atlas, mask_channels, ground, closed, pivots, sweep, attach. A relaxed policy does not add PBR authoring; the default material workflow is an opaque atlas; opt-in named-material vertex colours are described in adapters.md.

Closed lists intended watertight solid nodes. Hollow containers can have watertight wall/floor material with inward cavity walls and an open mouth. Do not cap intentional openings arbitrarily. Thin flags do not excuse holes in a declared closed node.

Default RGB mask: three exclusive recolour regions, black unchanged. RGBA requires both `Atlas(..., mask_channels='RGBA')` and a matching profile/contract. A is a fourth region, not transparency. The adapter assigns channel meanings.

## Relations and poses

Poses map names to node Euler angles `[rx,ry,rz]` in degrees or 3×3 matrices. Relations run at rest and each declared pose; optional poses filters them. Every relation declares a/b nodes and type:

- connected: contact/overlap within max_gap, optionally min_fraction of sampled surface points. For joints/cuffs.
- clear: reject detected crossings/containment and require sampled min_gap. For accessory clearance.
- fit: explicit samples in node a's world-rest coordinates, direction toward b, allowed min/max ray distances. For shell fit.
- support: the same explicit ray check for soles/pedals, hips/saddle, wheels/ground or supported props.

Relations use source geometry at declared poses. Exported surfaces are independently compared against the generator. Mesh crossing and sampled separation/contact use finite sampling/tolerances, **not continuous collision proofs**. Prefer explicit rays for critical contacts. Declare purposeful overlap at joints rather than forcing universal clearance.

## Texture regions

Atlas packs padded palette/decal cells and explicit decal UVs. A node may declare:

```python
node['decal_regions'] = {'face': {'normal': [0,0,1], 'min_dot': .3, 'max_anisotropy': 4}}
```

This catches a face decal leaking onto a chin/underside or excessive UV distortion. Collapsed decal UVs and atlas overlap fail. Distortion thresholds are opt-in because stylized projection may be intentional. Inspect actual textured/checker undersides too.

## Review

Review accepts size, views, modes and regions. Views: front/back/side/quarter/top/below. Modes: textured/plain/checker/wireframe. A region has name, nodes or world-rest bounds `[[min],[max]]`, optional views/margin/isolate. Node bounds follow each pose; explicit bounds stay fixed. Context stays visible unless isolation is requested.

Review imports each actual GLB and applies declared rigid node poses without changing exports. Skinned pose review is separate in Blender/the game. Skeletal export verifies a finite posed roundtrip, not universal deformation quality.

See [guided review](guided-review.md) for optional feature declarations, automatic exported-model close-ups, saved four-stage acceptance, evidence staleness and legacy compatibility.
