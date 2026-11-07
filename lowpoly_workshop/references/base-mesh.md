# Start from an existing base mesh

A project can start from a low-poly mesh that already exists (any GLB) instead of generating one. Workshop normalises the file, records where it came from, loads it into `gen.py` as editable nodes, and keeps the rest of the pipeline (build, check, review, texture, bake, LODs) unchanged. Generating a mesh from images with [Pixal3D](pixal3d.md) stays available as an option for projects that have no base.

```
target-look views → base import → remodel in gen.py → build / check / review → texture, bake, LODs
```

## Licence and provenance first

A base mesh belongs to its author. Before using one, read its licence, and record the licence and credit line when you import it:

```sh
lowpoly work/hero base import ~/Downloads/model.glb --licence CC-BY-4.0 --credit "Name of the author" --source-url https://example.org/the-model-page
```

- The ledger (`inputs/base/<name>.json`) keeps the licence id, the credit line, the source URL, the file's sha256 and every import parameter. Import warns when `--licence` is missing.
- Never commit a third-party base mesh, or renders and thumbnails made from it, to a repository whose licence you cannot apply to them. Workshop's own repository holds only first-party fixtures. Keep third-party bases in the consuming project's own `inputs/`, in a repository where the base's licence allows them.
- `lowpoly ASSET package` zips the whole project folder, including `inputs/`. If the base's licence does not allow redistribution, remove `inputs/base/<name>_source.glb` (keep the ledger) before packaging or sharing, and keep the credit line with anything you publish.
- A model's licence may not cover derivatives, commercial use or redistribution of the original. The ledger records what you were told; it does not check it.

## 1. Target-look views

If the finished model should match a look that the base does not have, plan and collect reference views first (`lowpoly ASSET references plan`, then `run` or `import`; see [references](references.md)). The base supplies shape and proportions; the views supply the target look. Generated views are design proposals, not recovered facts.

## 2. Import the base

```sh
lowpoly ASSET base import PATH [--name base] [--source-url URL] [--licence ID] [--credit TEXT]
                         [--front +z|-z|+x|-x] [--height METRES] [--budget TRIANGLES]
                         [--drop-plinth | --drop-node NAME ...] [--separate-nodes] [--replace]
```

Write `--front=-z` or `--front -z`; both work. Examples:

```sh
# a prop that faces +X, 1.2 m tall
lowpoly work/crate base import crate.glb --front +x --height 1.2 --licence CC0-1.0 --credit "A. Maker"
# a miniature on a display plinth: remove the plinth, keep the figure's parts as separate nodes
lowpoly work/knight base import knight.glb --height 0.9 --drop-plinth --separate-nodes --licence CC-BY-4.0 --credit "A. Maker"
# the plinth is not recognised: name its node instead
lowpoly work/knight base import knight.glb --drop-node Base --separate-nodes
# a mesh over the triangle budget (needs Blender)
lowpoly work/rock base import rock.glb --budget 1500
```

The import writes, under `inputs/base/`:

| File | Content |
| --- | --- |
| `<name>_source.glb` | the source file, copied byte for byte; the original is never modified |
| `<name>_lowpoly.glb` | the normalised mesh |
| `<name>_lowpoly.json` | the report: bounds, triangle counts, colour sources, dropped nodes, skin, animations, warnings |
| `<name>.json` | the ledger: original name (and project-relative path when inside the project), sha256, licence, credit, URL, import time, tool version, every parameter, triangle counts before and after, and history |

Nothing is written unless the whole import succeeds. The import time is the current UTC time, or `SOURCE_DATE_EPOCH` when set, for reproducible runs. `lowpoly ASSET base status` prints the ledger and says whether the stored source still matches its hash.

Re-importing the same file with other parameters is fine; the ledger keeps the licence and credit and appends a `reimported` event. A different file under the same `--name` is refused until you pass `--replace`, which records a `replaced` event with the previous hash, licence and credit. The new file does not inherit the old licence.

### What normalising does

In this order: pose a skinned mesh at its rest pose; drop what you asked to drop; turn the model so that `--front` points to +Z; scale so the model is `--height` metres tall (without `--height` the file's scale is kept, so it must already be in metres); put the lowest point on Y = 0; centre X and Z on the bounding box. Workshop's convention is metres, +Y up, +Z forward, left side +X. Orientation and scale vary by source, so look at the report and a render before you trust them.

This part is plain numpy and needs no Blender.

### Reduce only when needed

If the mesh has more triangles than `--budget`, it is reduced with headless Blender (the same reduction code the Pixal3D path uses, in `lowpoly_workshop/reduce.py`). A mesh within budget never starts Blender. When reduction is needed and Blender cannot be found, the import stops with a message and writes nothing: install Blender 4.5 and set `KIT_BLENDER`, or raise `--budget`.

With `--separate-nodes` the budget is shared between the nodes in proportion to their size. Reduction keeps the shape only: colours are re-attached from the nearest source triangle as per-triangle vertex colours, and a base-colour texture is dropped. If the base is textured, use [`base bake`](#5-texture-bake-and-lods) onto your own LODs instead of reducing it. Without `--budget` nothing is reduced; compare the final count with your asset's contract budget.

### Dropping parts

- `--drop-node NAME ...` drops the glTF nodes with those names and everything below them. An unknown name is an error that lists the mesh nodes.
- `--drop-plinth` removes a display base, and is deliberately conservative. It looks for the lowest glTF node, then the lowest connected piece of geometry, that is at most 30 % of the model's height, at least three times wider than tall, carries everything else on its top face (within 5 % of the height) and is not overhung. It refuses, and writes nothing, when the model is a single piece, when more than one piece reaches the lowest level, or when the lowest piece does not look like a base. The message says why; fall back to `--drop-node` or edit the mesh.

Everything dropped is listed in the report (`nodes_dropped`) and in the ledger's triangle counts.

### Skinned meshes

glTF ignores the node transform of a skinned mesh: the vertices are placed by `sum(weight * jointWorld * inverseBind) * vertex` at the rest pose. Workshop does exactly that, then drops the skin and the animations. The report records the skinned primitive, skin and joint counts and the animation names (for example `Walk`, `Idle`), so you know what was discarded. Re-rig in the generator with its `skin(nodes, p)` hook (see [contracts](contracts.md)), or in the consuming game. Morph targets are ignored (the base shape is used).

## 3. Remodel in `gen.py`

Load the normalised mesh with `load_glb_node` (it is also importable from `lowpoly_workshop.pixal3d`, where it first lived):

```python
from pathlib import Path
from lowpoly_workshop.base_mesh import load_glb_node, propose_palette, palette_cells
from lowpoly_workshop.kit.atlas import Atlas

HERE = Path(__file__).resolve().parent
BASE = HERE / "inputs/base/knight_lowpoly.glb"

# Start from the base's own colours (rename the cells and give them kit channels as you like).
ATLAS = Atlas(palette_cells(propose_palette(BASE, cells=8), channels=("R", "G")))

def params(variant=None, overrides=None):
    return dict(overrides or {})

def build(p):
    nodes = load_glb_node(BASE, node_name="Knight", atlas=ATLAS, mode="palette", separate_nodes=True)
    nodes.pop("Sword", None)          # drop a part
    # nodes["Head"] = ...             # or replace it with a part of your own
    return nodes
```

Colours come from, in priority order:

1. the base-colour texture through `TEXCOORD_0`;
2. the vertex colours `COLOR_0` (float, normalized ubyte or ushort; RGB or RGBA). glTF stores them linear: they are averaged per triangle in linear light, converted to sRGB, and multiplied by the material's `baseColorFactor` when there is one;
3. the material's `baseColorFactor` alone.

In `palette` mode each triangle takes the nearest flat palette cell by that colour. A mesh with none of these takes the first flat cell. In `decal` mode the texture coordinates are used as before.

`propose_palette(path, cells=8)` clusters the area-weighted triangle colours (median cut, then a few k-means passes) and returns `[{"name", "hex", "share"}]`, largest first, with names such as `dark_red` or `light_grey`. `lowpoly ASSET base palette --cells 8` prints the same list. The proposal is a starting point; merge or rename cells to fit your material plan.

`separate_nodes=True` gives one Workshop node per glTF mesh node, named after it (letters, digits, `_` and `-`; duplicates become `Head`, `Head_2`; unnamed nodes `Knight_3`). Without it the whole mesh is one node. Then build, check and review as usual:

```sh
lowpoly work/knight build
lowpoly work/knight check
lowpoly work/knight review
```

## 4. Build, check, review

Nothing differs from a project built from scratch. Workshop checks the generator's actual export, not the base file, so a base that is open, doubled or inside out shows up in the topology checks like any other mesh. Inspect the export from the usual views before you accept it. A hand-edited base is your own work; the ledger still records what it started from.

## 5. Texture, bake and LODs

Model each LOD in `gen.py`, then transfer the base's colours onto them:

```sh
lowpoly work/knight base bake
lowpoly work/knight base bake --source work/knight/inputs/base/knight_source.glb --variant 2 3 --fit-variant 2 --size 2048
```

The default source is `inputs/base/<name>_lowpoly.glb`. `--source` may be the original base. When it is the stored `<name>_source.glb`, its front and dropped nodes are taken from the ledger; for any other file give `--front`, and `--drop-node` or `--drop-plinth`, yourself (`--front=-z`). Colours are sampled from the base-colour texture, else `COLOR_0` (linear, converted to sRGB), else the material colour.

The bake itself is the one described in [Pixal3D](pixal3d.md#5-bake-the-generated-colours-onto-hand-built-lods): it fits the dense source to the LOD, gives every authored polygon its own chart, lines up facades, and writes `out/base_bake/<output>_bake.png`, `<output>_baked.glb`, `preview.png` and `bake.json`. The record names the source relative to the project, or by file name only when it lies outside.

## Limits

- Only binary `.glb` files, uncompressed (no Draco or meshopt); decompress first. Sparse accessors are not read.
- Materials beyond the base colour (transmission, clearcoat and other `KHR_materials_*`) are ignored and listed in the report.
- A skinned mesh is flattened to its rest pose; use a pose-correct re-rig afterwards.
- The plinth detection is a heuristic with deliberately narrow rules.
- Blender is needed only for reduction. That path (`reduce_mesh.py` running `reduce.py`) is covered by tests with a stand-in for Blender; run `lowpoly selftest --blender` and one real over-budget import on a machine with Blender 4.5 before relying on it.
