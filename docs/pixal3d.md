# Pixal3D (`raven38/pixal3d.cpp`) and Blender MCP polycount reduction

This optional workflow uses [`raven38/pixal3d.cpp`](https://github.com/raven38/pixal3d.cpp) (`trellis-cli`) to generate the initial 3D mesh from reference image(s), then uses **Blender MCP** (`tools.blender.execute_blender_code`) or headless Blender to reduce polycount and normalize orientation, scale, and ground contact before running Workshop's standard `build`, `check`, `review`, and `page` pipeline.

## 1. Environment & GGUF model sets

Build `trellis-cli` from `raven38/pixal3d.cpp` (enable `-DGGML_NATIVE=ON -DGGML_AVX2=ON` for CPU execution on Intel Core i5/i7) and download the `Q8_0` model set(s) from Hugging Face into separate directories (five shared files have identical names to the flow sets and cannot share one folder):

- Single-view (`sv`, ~7.54 GiB): [`raven38/pixal3d-sv-q8_0-v1`](https://huggingface.co/raven38/pixal3d-sv-q8_0-v1)
- Multi-view (`mv`, ~7.54 GiB): [`raven38/pixal3d-q8_0-v1`](https://huggingface.co/raven38/pixal3d-q8_0-v1)

Configure paths via environment variables (or a standard Trellis Studio install):

- `LOWPOLY_PIXAL3D_BIN`: path to `trellis-cli` (`trellis-cli.exe` on Windows)
- `LOWPOLY_PIXAL3D_MODELS_SV`: directory containing the 9 single-view GGUF files
- `LOWPOLY_PIXAL3D_MODELS_MV`: directory containing the 9 multi-view GGUF files
- `LOWPOLY_PIXAL3D_THREADS`: physical performance core (P-core) count for CPU runs

Check configuration with:

```sh
lowpoly doctor --pixal3d
lowpoly ASSET pixal3d status
```

### Native Windows CPU build (recommended over the portable release)

The published Windows runtimes are built with `GGML_NATIVE=OFF`, so they do not use AVX2/FMA and run ~2–3× slower on Intel i5/i7. A native MinGW build is worth it for repeated CPU runs. All-portable toolchain (no install, lives on any drive):

1. Download the winlibs x86_64 release (GCC + CMake + Ninja in one zip) and extract it.
2. Shallow-clone the release tag with submodules:
   ```sh
   git clone --depth 1 --branch v0.10.1-desktop-alpha --recurse-submodules --shallow-submodules https://github.com/raven38/pixal3d.cpp.git pixal3d-src
   ```
3. Configure CPU-only with native arch and without WebP (MinGW curl has no CA certs for the FetchContent download; PNG fallback is used anyway since runs pass `--webp off`):
   ```sh
   cmake -S pixal3d-src -B pixal3d-src/build -G Ninja -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=ON -DTRELLIS_WEBP=OFF
   cmake --build pixal3d-src/build --target trellis-cli -j 2
   ```
4. The exe still needs MinGW runtime DLLs beside it: `libgomp-1.dll`, `libdl.dll` (required by libgomp — missing it fails with `STATUS_DLL_NOT_FOUND`), `libgcc_s_seh-1.dll`, `libstdc++-6.dll`, `libwinpthread-1.dll`. Verify with `trellis-cli.exe --help` (exit 0). Note: a self-test can falsely pass when the toolchain `bin/` is on PATH — retest from a clean shell.

Measured reference (i5-6500, 4C/4T, Q8 single-view, `--res 1024`): SS-flow step ≈ 17 min native vs ≈ 30 min portable; full 1024 cascade projects to 1.5–3 days. Budget wall-clock accordingly or move generation to stronger hardware.

### Native Linux CPU build

GCC and CMake from the distribution are enough (tested with GCC 11.4 and CMake 3.22 on Ubuntu 22.04; Ninja is optional). The default configuration is CPU-only:

```sh
git clone --depth 1 --branch v0.10.1-desktop-alpha --recurse-submodules --shallow-submodules https://github.com/raven38/pixal3d.cpp.git pixal3d-src
cmake -S pixal3d-src -B pixal3d-src/build -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=ON -DTRELLIS_WEBP=OFF
cmake --build pixal3d-src/build --target trellis-cli -j
```

The build takes about a minute and writes `pixal3d-src/build/trellis-cli`; no runtime libraries need copying. Run Workshop from an installed package (`pip install -e .`) rather than the system Python: Ubuntu 22.04's `python3-pil` 9.0 lacks `Image.Resampling`, and `pixal3d prep` fails with an `AttributeError`.

Measured reference (i7-8850H laptop, 6C/12T at ≈2.2 GHz sustained, `--threads 6`, Q8 single-view, `--res 1024`, Station Rest House front view): one complete run took 28.9 h and peaked at 3.9 GiB resident.

| Stage | Measured |
| --- | --- |
| SS flow, 12 steps | ≈ 6.3 min per step (mean of 7 steps), about 2.7× faster than the i5-6500 native build |
| 512 shape flow, 12 steps | 62 min; ≈ 5.2 min per guided step, ≈ 2.6 min for the last four unguided steps |
| 1024 shape flow, 17,928 tokens | 14.6 h; ≈ 80 min per guided step, ≈ 40 min for the last four |
| 1024 shape decode | 18 min; 7.45 M voxels, 15 M-triangle raw mesh |
| 1024 texture flow, 12 unguided steps | ≈ 38 min per step |
| PBR decode | 28 min |
| Remesh, UV bake and GLB write | 23 min, measured with `--decim 50000` (undecimated 25 M-triangle mesh) |

Steps took two to three times as long once other CPU-heavy jobs shared the machine, so generate on an otherwise idle machine.

## 2. Prepare RGBA inputs and generate `inputs/pixal3d_raw.glb`

Pixal3D requires clean RGBA cutouts. Workshop extracts the reference view (or four canonical views `front`, `right`, `back`, `left`) from `asset.json` and writes centered square RGBA PNGs under `inputs/pixal3d/`:

```sh
# Single-view (uses the front reference or the front crop of a sheet set)
lowpoly ASSET pixal3d prep --mode sv --view front
lowpoly ASSET pixal3d run --mode sv --gpu -1 --atlas 1024 --seed 42

# Multi-view (requires front, right, back, left views)
lowpoly ASSET pixal3d prep --mode mv
lowpoly ASSET pixal3d run --mode mv --gpu -1 --atlas 1024 --seed 42
```

A reference declared with any other view (for example a `turnaround` sheet) is never used whole as the front view. Declare a sheet set with a crop box (`[left, top, right, bottom]` in sheet pixels) for each view instead; otherwise `prep` stops with an error:

```json
"sets": {"sheet": {"image": "ref/turnaround.png", "views": {"front": {"box": [0, 0, 600, 512]}}}}
```

`pixal3d run` passes `--webp off` so embedded textures are lossless PNGs, and leaves decimation to `trellis-cli`'s Pixal3D quadric simplify (1M faces). `--decim N` selects `trellis-cli`'s legacy cluster grid of size `N` instead; it is not a face budget, and large values leave the mesh undecimated (≈ 25 M triangles, with UV charting abandoned after 300 s). The run writes `inputs/pixal3d_raw.glb` atomically, and caches the result in `inputs/pixal3d_meta.json` by input and parameter SHA-256.

## 3. Reduce polycount in Blender MCP (or headless Blender)

Pixal3D outputs high-density meshes in `[-0.5, 0.5]³` facing `-Z` instead of glTF's `+Z` front. Use Blender MCP exclusively for post-generation decimation and normalization:

1. Generate the Blender Python decimation script for the asset's declared triangle budget and height:
   ```sh
   lowpoly ASSET pixal3d mcp-script --budget 1500 --height 1.0 --node Crate
   ```
2. Run that script in live Blender via `tools.blender.execute_blender_code` and inspect the decimated result with `tools.blender.look`, or run it headlessly via:
   ```sh
   lowpoly ASSET pixal3d decimate --budget 1500 --height 1.0 --node Crate
   ```

This step rotates the mesh `180°` to face `+Z`, welds close vertices, applies planar + UV-preserving collapse decimation down to `budget`, scales to `height` in metres, grounds the lowest vertex at `Y = 0`, and writes `inputs/pixal3d_lowpoly.glb`, `inputs/pixal3d_atlas.png`, and `inputs/pixal3d_lowpoly.json`.

## 4. Load the reduced mesh in `gen.py` and run Workshop checks

In `gen.py`, load `inputs/pixal3d_lowpoly.glb` through `lowpoly_workshop.pixal3d.load_glb_node`:

```python
from pathlib import Path
from lowpoly_workshop.kit.atlas import Atlas
from lowpoly_workshop.pixal3d import load_glb_node, make_decal_atlas

HERE = Path(__file__).resolve().parent
# Option A: flat palette cells sampled from Pixal3D's baked texture
ATLAS = Atlas({"body": ("#609776", "R"), "trim": ("#3a4150", None)})
# Option B: preserve Pixal3D's baked UV texture as a decal cell
# ATLAS = make_decal_atlas(HERE / "inputs/pixal3d_atlas.png", cell="surface")

def params(variant=None, overrides=None):
    return dict(overrides or {})

def build(p):
    return load_glb_node(
        HERE / "inputs/pixal3d_lowpoly.glb",
        node_name="Crate",
        atlas=ATLAS,
        mode="palette",  # or "decal" with make_decal_atlas
    )
```

Then run the normal Workshop pipeline:

```sh
lowpoly ASSET build
lowpoly ASSET check
lowpoly ASSET review
lowpoly ASSET page
```

## 5. Bake the generated colours onto hand-built LODs

Decimation keeps the generated shape but loses its detail: below a few thousand triangles the generated mesh no longer simplifies cleanly, and flat colours per face cannot carry windows, trims or tiles. For game LODs, model the low-poly shapes in `gen.py` and bake only the generated colours onto them:

```sh
lowpoly ASSET pixal3d bake
lowpoly ASSET pixal3d bake --variant 2 3 --fit-variant 2 --size 2048
```

The source is `inputs/pixal3d_raw.ply` (the vertex-coloured dense mesh `trellis-cli` writes beside its `.glb`), else `inputs/pixal3d_raw.glb` with its base-colour texture; `--source` picks another file. The bake

1. maps the generated mesh onto the LOD named by `--fit-variant` (default: the first baked output), first by bounds, then by a per-axis scale and offset that maximise front and side silhouette overlap, and uses that one mapping for every LOD;
2. gives every authored polygon its own chart in a `--size`² atlas, all at one texel density;
3. colours each texel from the first generated surface met coming in from outside along the polygon's normal, falling back to the nearest generated point facing the same way.

It writes, per output, `out/pixal3d_bake/<output>_bake.png` and `<output>_baked.glb` (one flattened, textured mesh), plus `preview.png` and `bake.json` with the fit, the texel density and the share of texels hit from outside. It does not change `gen.py` or the asset's own outputs.

Model the LODs to the generated shape: authored detail that the generated mesh also shows (window frames, posts) appears twice, once as geometry and once in the texture, so flat walls work best on a baked LOD.

Measured on the Station Rest House (i7-8850H, sharing the CPU with a `trellis-cli` run), from the 15 M-triangle `.ply` at `--size 1024`: silhouette IoU 0.85, 76–83 % of texels hit from outside, 38 min for all four LODs at 4.2 GiB peak. Texel density falls with polygon count — 26 texels/m on the 44-triangle far LOD, 18 on LOD2 (1,400), 13 on LOD1 (6,448), 7 on LOD0 (39,524). At 7 texels/m, LOD0's thin trims and bevels get charts smaller than a texel and show as dark lines; bake only the low LODs, or raise `--size`.
