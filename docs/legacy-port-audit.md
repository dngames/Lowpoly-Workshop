# Legacy kit parity audit

This audit compares the older owner-maintained embedded kit (through its October 2026
coverage/review update) with Workshop 0.3.0. It concerns reusable algorithms and modelling
lessons, not consumer artwork or runtime staging. New Workshop validation, templates,
RGBA masks, skinning, path containment and guided-review contracts remain authoritative.

## Restored reusable capabilities

| Older capability | Standalone location / command |
|---|---|
| Confidence-aware observation planning and independent review | `lowpoly ASSET coverage`; `kit.coverage` |
| Best supplied-reference paint-class diagnostics | `lowpoly ASSET paint`; `kit.paintcheck` |
| Component-coloured diagnostic shots | `lowpoly ASSET pieces`; `kit.pieces` |
| Distance-dependent coplanar conflict classification | `kit.surfaces`; optional output `contract.view_m` in exported checks |
| Closed economical animal bodies, fins, ears and wings | `kit.animal`, `kit.wildlife`; no consumer models bundled |
| Directed-edge and positive-volume primitive orientation | `kit.organic.surface_orientation`; use on each original solid before cleanup |
| Named-material vertex-colour export and physical/full-cell UVs | Optional `vertex_surfaces` / `runtime_uv`; generic palette/material policy with no consumer IDs; atlas mode remains the default |
| Optional CPU palette/silhouette diagnostics | `render_engine: "raster"` for generator render commands; never actual-export acceptance |
| Static organic closed-shell LOD preparation | `lowpoly ASSET shell-lods`; explicitly opted-in static organic source only |
| Atomic JSON, rigid GLB and skeletal GLB output | `kit.atomic`; exporters retain the previous file on failed replacement |
| Concave-profile ear clipping and opt-in gradient/blue sheet masking | `kit.mesh.triangulate_profile`, `sheet_bg_mode`; default border masking unchanged |
| Official bpy module launcher | `lowpoly_workshop/blender_module.py`; supports thread/factory/error/script flags |
| Batch-local helper import isolation and portable rebuild lessons | `build-validation.md`; asset-specific helper module names |
| Evaluated Blender geometry, axis/scale, normals, closure, depth and review lessons | `build-validation.md`, `modelling.md`, `appearance-workflow.md` |

The primitive orientation helper audits one original closed solid, not an arbitrary collection
of overlapping objects. A deliberately inverted cavity surface is part of its wall construction,
not a standalone positive-volume solid. General closed-node topology policy is unchanged.

`paint` reports disagreement with supplied reference classes; unseen/inferred neighbours and
single-class palettes are not evidence that colours are correct. `pieces` labels connected
triangle groups, not anatomical correctness. The optional depth conflict check assumes the
near-plane/depth-buffer example documented in `build-validation.md`; adapters must choose an
appropriate viewing distance and verify their actual renderer.

## Shell LOD hook

Use only for static organic masses, never architecture, articulated objects, skinning or moving
mechanisms. The project must have `kind: "static-prop"`, no active clips, `geometry_sources`,
and a generator `raw_sources()` hook returning dictionaries:

```python
{"key": "organic_mass", "static_organic": True, "faces": source_faces,
 "targets": [200, 80, 32], "voxels": 48}
```

The Blender command writes `inputs/shells.json`, with source hashes, bounds-preserving closed
triangle levels and palette-cell IDs. Read that cache from the generator. Supply source faces
independently of that cache so the first run can build. Export each cached level and verify
closure, budget, bounds and palette after export. The shell does not preserve decals, arbitrary
UV paint or moving nodes; do not pass those sources to it.

## Deliberate consumer boundaries

Consumer-specific runtime material IDs, shader tags, model/route registries, exact rider rigs,
asset staging, game photographs/reference sheets and approved production models are **not**
portable kit content. The generic named-material/vertex-colour mechanism is restored as an opt-in export mode.
The actual material-ID dictionary and interpretation of shader tags still belong to the
consumer adapter; no consumer IDs are bundled.
These are explicit integration boundaries, not unreported missing core features.

Cycling-specific joint suites are represented by generic posed contact, clearance and support
relations plus actual-export review. Existing generic skeletal weight/roundtrip checks remain;
legacy rigid-only checks do not replace them. Current wrapped patches/host-normal frames and
reference provenance likewise supersede earlier ad hoc per-model scripts.

No original consumer art, model files, private audit screenshots, service credentials or external
Trompe code were imported. The owner-authorised inherited helpers retain the project MIT terms.

## Older consumer modules reviewed, not copied

`bike_sockets`, `crowd`, `spectator`, `villager`, `rider_joints` and `rider_lod` encode a
particular consumer's node/skeleton names, costumes, proportions or geometry recipes. Their
reusable joint, support, host-normal, closed-shell and painted-detail techniques are covered by
the generic helpers and modelling/build-validation guides. They remain consumer adapters or
models, not dependencies of this standalone package. This audit does not claim source-level
compatibility with those consumer model generators.
