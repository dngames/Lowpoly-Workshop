# Asset field reference

An asset declares its generator, exported files, reference views and review requirements. All paths are relative to the asset folder. This independent static-prop example contains no consumer project specification.

```json
{
  "schema_version": 2,
  "name": "example-prop",
  "title": "Example Prop",
  "kind": "static-prop",
  "profile": "portable",
  "generator": "gen.py",
  "out_dir": "out",
  "references": [],
  "outputs": [{
    "file": "out/model.glb",
    "kit_mask": "kit_mask.png",
    "clips": false,
    "contract": {"budget": 3000, "closed": ["Body"]}
  }],
  "sets": {},
  "poses": {},
  "relations": [],
  "review": {"views": ["front", "side", "below"], "modes": ["textured", "plain"]}
}
```

The generator must create the declared Body node; this is a field illustration, not a complete runnable project. Use `lowpoly new work/prop --kind static-prop` for a runnable starter. See contracts.md for current output/profile rules.

## Reference sets

Each entry in sets names a relative sheet image and its views. A view selects a measured crop box or grid cell and can provide camera hints. Set-specific variant, scale, palettes and node filters describe the reference presentation. Measure these values from your own permitted references rather than copying another project's sheet coordinates.

A camera vector starts with `[azimuth, elevation, roll, distance, pixels_per_metre, centre_x, centre_y]`; optional pose values follow. Azimuth zero looks toward the front, a quarter turn selects a side, and elevation changes vertical viewpoint. Camera distance and image scale must match the source perspective. See legacy-fitting.md for the fitting process.

## Palettes and classes

Fitting compares segmented class maps. Set palettes, class_names, default_class and cell_class from the current asset's reference colours and atlas cells. Use a small number of classes separating major regions; use the sheet measurement tools to inspect colour choices and background segmentation. No specific consumer palette or crop geometry is bundled here.
