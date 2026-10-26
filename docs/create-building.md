# Create a building: Tiny Tour's Station Rest House

Build an actual Tiny Tour asset with the standalone Workshop: the **Yuzu Station Rest House**, a two-storey building with a hipped roof, front gable, covered terrace, benches and framed windows.

## Start with the original 2D design

![Original Tiny Tour Station Rest House design sheet, with six views.](images/station-rest-house-original.png)

This historical AI-generated design sheet was the original modelling input. It is copied byte-for-byte from Tiny Tour; the original prompt is bundled beside it. “Original” means the design input, not a mesh render or a claim that the sheet was hand-drawn. The provider/model is not recorded here.

## Compare the exported result

![Actual exported views of the Station Rest House, including its simpler LOD2.](images/create-building.png)

This is a first-party Tiny Tour example included at the repository owner's request under Workshop's MIT license. The source's `provenance.json` identifies the Tiny Tour commit and file hashes, plus the small portability changes. The original sheet and prompt are included; game textures, fitted cameras and runtime placement code are excluded. The sheet is registered in `asset.json`, copied into new example projects and displayed in their review viewer. These pictures are rendered from the Workshop export, not captured from the game.

The low-poly result preserves the broad roof, facade and terrace arrangement. It simplifies the reference’s curved roof tiles, timber framing, stone courses, bevels and painted surface finish. Compare these differences explicitly; this is not an exact reconstruction or automatic image-to-mesh result.

## Build and open it

From a source checkout, with Workshop installed and Blender configured:

```sh
python scripts/building_example.py work/station-rest-house
lowpoly serve work/station-rest-house/out/page --port 8000
```

Open **http://127.0.0.1:8000**. Select a detail level and inspect front, side, back and quarter views. The helper creates an editable project, builds/checks all four GLBs, renders sixteen declared views plus six component diagnostics, then generates the local viewer and source bundle. Use an empty destination. Add `--source-only` to the first command to edit before building.

The source is bundled in `lowpoly_workshop/assets/examples/station-rest-house`; copying that folder into an empty project also works with the normal CLI.

## Understand the construction

The main wall footprint is **14 × 9 m**, with a roof about **8 m high** and a wider terrace/roof overhang. Ridge trim slightly exceeds 8 m. Coordinates use metres, **+Y up**, **+Z toward the street**, and a base-centred origin.

Read `gen.py` in this order:

- `box()` creates closed wall, terrace, post and bench solids.
- `roof()` constructs a closed hipped roof, with optional ridge trim.
- The front gable penetrates the main roof; the terrace canopy is a separate closed sloping solid.
- Four posts meet the canopy underside. Three benches sit on the terrace.
- `window()` keeps facade openings in place while removing frames and bars as detail decreases. The glass uses an opaque palette colour; it is not a transparent interior window.
- Hidden interior faces are removed after the complete assembly is built.

Edit the `COLORS` palette to change plaster, wood or roof colour. Edit the architectural dimensions and window arrays in `build()` for a different layout; keep dependent supports, roof intersections and terrace furniture aligned. This is editable modelling source, not a general-purpose house-width slider. `inputs/construction.json` holds the identity and budget metadata; changing its height field alone does not resize the geometry.

## Keep identity across detail levels

| Level | Triangles | Treatment |
|---|---:|---|
| LOD0 | 685 | Window frames/bars, ridge trim and full benches |
| LOD1 | 517 | Simpler windows and roof trim; full benches |
| LOD2 | 201 | Thin window faces and bench proxies; terrace and chimney retained |
| Far | 28 | Roof and wall silhouette; furniture, openings and terrace omitted |

The original detail policy and geometry are retained. The far proxy is deliberately sparse; it does not preserve every nearby feature. Workshop exports all four models but does not choose engine switching distances or wire them into Tiny Tour.

## Check, inspect and package

After editing:

```sh
lowpoly work/station-rest-house build
lowpoly work/station-rest-house check
lowpoly work/station-rest-house review
lowpoly work/station-rest-house page
lowpoly work/station-rest-house package
```

The checks verify export geometry, node names/pivots, budgets and UVs. Source checks examine individual closed structural primitives **before** hidden-face removal, plus support/bench counts. The cleaned assembled building is not declared to be a single watertight solid; thin LOD2 window faces are intentional. Regressions check facade positions across the three nearer levels, post/canopy reach, bench seating, scale and detail reduction.

Inspect roof intersections, facade depth, canopy supports and benches from multiple views. Successful checks are useful evidence, not artistic acceptance. Any engine import and LOD switching still need review in that engine.

## Reproduce the pictures

After building the project:

```sh
python scripts/building_visuals.py work/station-rest-house
```

This composes existing actual-export images into `docs/images/create-building.png`. Its evidence JSON records the Tiny Tour source commit, adapted source/spec hashes, checked status, triangle counts and model/image hashes.
