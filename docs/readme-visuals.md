# README visuals

The README leads with the historical 2D design input, then the actual model. Image provenance is explicit:

- `images/station-rest-house-original.png`: the unchanged Tiny Tour six-view design sheet. The original prompt, source commit and image hash are bundled under `assets/examples/station-rest-house/ref` and `provenance.json`. This was historical AI-generated design art used as modelling input; it is not a mesh render. The provider/model is not recorded here.
- `images/station-rest-house-remodel.png`: old versus remodelled actual-export views, with separate source/model/image hashes. Reproduce with `python scripts/building_comparison.py OLD_PROJECT NEW_PROJECT`.
- `images/create-building.png`: current textured building views. The standalone project registers its original in `asset.json` and shows it in the viewer. See [building walkthrough](create-building.md).
- `images/character-design-notes.svg`, `starter-design-notes.svg`, `repair-design-notes.svg`: newly authored explanatory construction diagrams for procedural examples. They were made after those models. No historical 2D originals existed, so these are never described as originals or used as proof of reference matching. Regenerate with `python scripts/design_diagrams.py`.
- `images/create-character.png` and `create-character-high.png`: actual procedural character exports, shown after their written-brief/construction notes. The denser model is not a demonstration of detailed sculpted clothing or reference fidelity.

The remaining illustrations are:

- `images/workshop-starters.png`: a contact sheet of the five bundled starters, built, checked and rendered from their **actual GLB exports** in textured quarter view. These are small teaching models, not a production-art gallery.
- `images/workshop-flow.svg`: an editable explanatory diagram. Its icons describe stages; they are not screenshots of an automatic image-to-mesh feature.
- `images/fringe-comparison.png`: the existing reproducible flat-versus-wrapped repair demonstration. See [repair demonstrations](repair-demos.md).

Regenerate the starter image from a source checkout with dependencies and `KIT_BLENDER` configured:

```sh
python scripts/readme_visuals.py /path/to/empty/scratch
```

The script writes isolated starter projects to the empty destination and the image/evidence to `docs/images/`. Override the latter with `--images /path/to/images`. It builds, checks, imports and renders the real exports. The evidence records relative source/output paths, generator/GLB/review-image hashes, and the contact-sheet hash. It records no artistic approval.

The building’s historical sheet is the explicitly included Tiny Tour reference. Other diagrams and models are procedural; their reproduction needs no external reference downloads or new image-generation calls. Text is laid out with DejaVu Sans or Windows Arial when available, otherwise Pillow's bundled font. Image bytes can differ across Blender/platform/font versions; inspect the result after regeneration.

The flow diagram is plain SVG and can be edited directly. Its accessible title/description and the README alt text preserve the reading order when the graphic is unavailable.

- `images/station-rest-house-reference-check.png` and `station-rest-house-shape-preview.png`: unchanged original design crops beside clay and painted renders of the same rebuilt GLB. Reproduce using `scripts/render_building_reference.py` followed by `scripts/building_reference_comparison.py PROJECT`. Cameras and source/export/image hashes are in the adjacent evidence JSON; framing is not a calibrated overlay.
