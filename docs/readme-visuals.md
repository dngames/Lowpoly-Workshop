# README visuals

The README uses three different kinds of illustration:

- `images/workshop-starters.png`: a contact sheet of the five bundled starters, built, checked and rendered from their **actual GLB exports** in textured quarter view. These are small teaching models, not a production-art gallery.
- `images/workshop-flow.svg`: an editable explanatory diagram. Its icons describe stages; they are not screenshots of an automatic image-to-mesh feature.
- `images/fringe-comparison.png`: the existing reproducible flat-versus-wrapped repair demonstration. See [repair demonstrations](repair-demos.md).

Regenerate the starter image from a source checkout with dependencies and `KIT_BLENDER` configured:

```sh
python scripts/readme_visuals.py /path/to/empty/scratch
```

The script writes isolated starter projects to the empty destination and the image/evidence to `docs/images/`. Override the latter with `--images /path/to/images`. It builds, checks, imports and renders the real exports. The evidence records relative source/output paths, generator/GLB/review-image hashes, and the contact-sheet hash. It records no artistic approval.

No original game art, external reference downloads or image-generation calls are involved. Text is laid out with DejaVu Sans or Windows Arial when available, otherwise Pillow's bundled font. Image bytes can differ across Blender/platform/font versions; inspect the result after regeneration.

The flow diagram is plain SVG and can be edited directly. Its accessible title/description and the README alt text preserve the reading order when the graphic is unavailable.
