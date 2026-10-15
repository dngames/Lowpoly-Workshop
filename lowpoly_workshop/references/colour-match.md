# Colour match

Silhouette fitting scores shape, not colour: a teal jacket and a green one fit equally well. `lowpoly ASSET colour` compares each atlas cell with the reference pixels it covers through the solved cameras, and suggests a palette value where they disagree.

```sh
lowpoly work/rider fit all --grid
lowpoly work/rider colour
lowpoly work/rider colour front_sheet --tolerance-ab 8
```

It needs solved cameras (`fit`) and no Blender. It is advice for review: it never fails a build, check or package.

## Which pixels count

A drawing and its model never line up exactly. A reference pixel counts towards a cell only where all of these hold:

- **Visible:** the cell is the nearest surface there.
- **Facing:** the surface faces the camera. Trust fades in from `facing_low` (0.25) to `facing_high` (0.6), because grazing faces smear a few pixels over a large area.
- **Away from edges:** at least `edge_px` (3) inside the model's silhouette, the reference's foreground and every boundary between cells. Edges are where drawing and model disagree by a pixel or two and colours mix.
- **Not ink:** when the palette declares `_line_class`, pixels darker than `ink_lum` (40, the fitter's ink threshold) are skipped. Dark parts drawn above that still count.

Each view writes `out/colour/<set>_<view>_trust.png`: white where the reference was used, black where it was not. When a result looks wrong, look there first. It shows whether the camera missed the part or the tests turned it away.

## How it judges

The comparison runs in CIE Lab with weighted medians, so a few stray pixels do not move it.

- **Hue and saturation decide.** References are lit and the atlas is not. Diffuse shading scales linear light, so each reference pixel is first scaled to the atlas pixel's luminance, which removes shading and leaves only hue and saturation. A cell is `review` when that a/b distance exceeds `tolerance_ab` (12).
- **Lightness is relative.** The median lightness shift over all trusted pixels is reported as the reference lighting and removed. A cell is also `review` when its remaining shift exceeds `tolerance_l` (25). With a single seen cell, lightness cannot be judged.
- **Unseen is not a match.** A cell with fewer than `min_pixels` (40) trusted pixels is `unseen`. Add a view that shows it, or judge it by eye.

Flat cells under review get a `suggest` hex: the reference's hue and saturation at the atlas lightness, plus the relative shift. Decal cells are compared but get no suggestion; repaint the decal instead. Suggestions are never written back. Copy one into `ATLAS` in `gen.py` only after looking at the swatches and the trust map.

## Settings

Put defaults in `asset.json`, override per run on the command line:

```json
"colour_match": {"tolerance_ab": 10, "edge_px": 4}
```

| Setting | First adjustment |
|---|---|
| `tolerance_ab` | Lower for flat-colour sheets, raise for painterly or photographic references. |
| `tolerance_l` | Raise when the reference has strong cast shadows. |
| `edge_px` | Raise when outlines or anti-aliasing tint small cells. |
| `facing_low` / `facing_high` | Raise both if slightly angled faces pick up neighbouring colours. |
| `min_pixels` | Lower for small parts drawn at low resolution. |
| `ink_lum` | Lower when near-black parts are skipped as ink. |

## Outputs

- `out/colour/colour.json`: settings, lighting shift, trusted pixels per view and cell, and per cell `palette`, `model`, `reference`, `d_ab`, `d_l`, `status` and `suggest`.
- `out/colour/swatches.png`: per cell, the atlas colour above the reference colour, with a green (ok), red (review) or grey (unseen) bar.
- `out/colour/<set>_<view>_trust.png`: the trust map.

## Limits

- Cast shadows, coloured light and strong white balance shifts move hue. If every cell is under review in the same direction, check the reference's lighting before changing the palette.
- Inferred references are design proposals. Compare against originals first and report generated sets separately.
- A wrong shape is not a colour mistake: a cell that covers the wrong drawn part reports the colour of that part. Fix the fit first.
- Passing does not prove the texture reads right in the game. Review the target runtime.

The trust tests follow the "Pixel Match" projection idea from [AssetFurnace (image-to-3dlab)](https://github.com/Bingeljell/image-to-3dlab/blob/main/docs/pixel-match.md), which paints generated meshes from their source pictures. Here they measure a palette instead of painting a texture. No code was copied.
