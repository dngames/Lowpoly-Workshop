# Reproducible repair demonstrations

The first demonstration recreates a problem observed while making game characters: a flat fringe can look acceptable from the front but stand away from the head at the temples. It uses an original procedural head proxy, not the private game's character art. This is a synthetic illustration of a repair technique, not a comparison with another product or an automatic defect detector.

![Flat fringe and wrapped fringe, rendered from the exported GLBs](images/fringe-comparison.png)

Both models are closed meshes. A basic topology check can pass both. The before generator places a flat slab at the forehead; the after generator uses surface.wrapped_patch to project a grid onto the head and close its thickness. Front, side and underside views expose the difference. This deliberately shows a limit of automated checking: visual fit still needs review.

## Reproduce

From a source checkout with the dependencies installed and KIT_BLENDER configured:

```sh
python scripts/repair_demo.py work/fringe-demo
```

The destination must be empty. The script creates before/after generator projects, builds and checks their actual exports, renders matched views, and writes comparison.png and evidence.json. Evidence records the GLB hashes and underlying review indexes. It does not mark either asset visually approved. No image-generation service or reference download is used.

The image above is a deterministic procedural example rendered through Blender; it is not an AI-invented image of what the mesh should look like. A checked-in copy of the evidence accompanies it at images/fringe-evidence.json. The evidence paths are relative to the reproduced demo folder; the checked-in image and evidence do not include all build outputs. Rebuilds may differ in image bytes across Blender/platform versions.

## Other repair recipes

See [modelling](modelling.md) for connected/capped limbs, host-normal accessory alignment, shoes/support contacts, saddle fit, closed undersides and constrained decals. Those recipes address the corrections that motivated this kit. They are not all accompanied by published before/after demonstrations yet, and require project-specific declarations and visual acceptance.
