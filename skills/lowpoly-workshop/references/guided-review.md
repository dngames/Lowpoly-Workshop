# Feature checklist and guided review

Guided review is optional in schema v2. Existing projects and approvals keep their legacy behaviour until `features` is nonempty or `workflow.enabled` is true. No provider or account is needed.

## Start and resume

```sh
lowpoly new work/crate --kind static-prop --guided
lowpoly work/crate all
lowpoly work/crate features list
lowpoly work/crate workflow next
```

All five starters support `--guided`. Their initial checklist describes an independent procedural design and labels it **inferred**. Replace those broad starter features with the important details of your intended asset. The tool does not identify image contents automatically.

`all` builds, checks and renders evidence; it does not accept a feature or stage. `workflow status` shows every stage, decision, outstanding finding and next action. `workflow next` prints a compact next step and command template; replace `ASSET` and `REVIEW_NOTE`. Inspect the evidence before running an acceptance command. Decisions are saved atomically in `out_dir/workflow.json` and included in asset bundles.

## Describe a feature

Add this to the `features` array in asset.json after registering `ref/front.png` as an original reference:

```json
{
  "id": "front-panel",
  "description": "Inset front panel with a narrow painted border",
  "stage": "appearance",
  "output": "out/model.glb",
  "nodes": ["Crate"],
  "basis": "observed",
  "evidence": [{"path": "ref/front.png", "view": "front", "box": [20, 20, 180, 180]}],
  "views": ["front", "quarter"],
  "modes": ["textured", "checker"],
  "poses": ["rest"],
  "required": true
}
```

The crop is `[left, top, right, bottom]` in image pixels, within the original image. Evidence must link a registered, existing reference. Original images remain unchanged. The page displays feature reference crops beside the checklist and provides a button to select its model close-ups.

`basis=observed` requires original evidence. Generated or rendered images cannot establish an observed feature. For invented/hidden structure, use `basis=inferred`, explain the design in `notes`, and optionally link supporting references. Acceptance approves that design choice; it never turns it into an observation. No arbitrary confidence percentage is treated as proof.

Feature ids are unique lowercase identifiers. Output must be a declared GLB. Nodes must exist in that export and include at least one mesh for framing. List all relevant parts together when checking a joint, support or accessory. These bindings are verified by `check`; they do not prove a feature is visually correct or a decal exists. For decals, bind the owning mesh and inspect its textured/checker images. Geometry/UV/contact rules remain in the existing output contract and relations.

Feature views, modes and poses must be explicit and nonempty. Poses are `rest` or names declared in asset.json. `review` automatically frames each feature from its exported mesh bounds and renders every requested combination. Context stays visible. The index records feature/node identity, source/export hashes and each PNG hash.

## Review in four stages

| Stage | Minimum whole-export evidence | Additional gate |
| --- | --- | --- |
| proportions | Plain front and side | Required features for this stage accepted |
| construction | Plain quarter and below | Current automated checks all pass |
| appearance | Textured front, back and side | Required appearance features accepted |
| motion-export | Plain quarter at rest and every declared pose | Current automated checks all pass |

All stages also require current build evidence and their required feature reviews. The renderer adds the minimum whole-export views/modes in guided mode even if review defaults are narrower. Feature-specific shots supplement these views. It renders declared rigid poses; it does not evaluate every instant of an animation or skeletal deformation. Define useful stress poses and relation checks yourself.

```sh
lowpoly work/crate features review proportions-1 --decision accepted --note "Inspected front and side proportions"
lowpoly work/crate workflow accept proportions --note "Silhouette matches the intended design"
lowpoly work/crate workflow next
```

For a defect, record `--decision repair --note "Border stretches at the lower corner"`, fix the generator/UVs, then rebuild/check/render and review again. Required features cannot be waived. Optional features (`required=false`) may be waived with a note and current evidence; they do not block a stage while pending. Optional decisions remain visible in the checklist.

Finish each earlier stage before accepting the next. Stage notes and feature decisions are reviewer assertions supported by evidence, not automated artistic scores. Run `approve --note ...` only after user/artist acceptance and runtime review; guided projects cannot obtain final approval until all four stages are current.

For `out_dir/skinned.glb`, motion-export also requires separately supplied deformation evidence:

```sh
lowpoly work/character workflow accept motion-export --note "Inspected skeletal stress poses in Blender" --evidence out/posed-character.png
```

Additional evidence files must be inside out_dir, exist, and remain unchanged. Describe what was actually inspected. Hashing a screenshot does not verify its contents or prove animation readiness. Automated skeleton roundtrip checks and visual deformation review remain separate responsibilities.

## Evidence changes and portability

Build records bind sources and GLB/atlas/mask companions. Feature/stage decisions bind current source, exports, render index and PNG contents; construction/final stages also bind check evidence. Later stages bind earlier acceptance decisions. Final guided approval binds the completed workflow. Editing/removing evidence or changing references, definitions, generator, kit code, exports or relevant decisions makes acceptance stale or blocks it. Re-rendering an old export cannot satisfy a stale build.

Invalidation is deliberately conservative: project/tool changes and a changed render index can invalidate several earlier reviews, even when the visible change is small. Notes/findings are retained so a reviewer can recheck them. The workflow is designed for one writer per asset; atomic saves avoid partial JSON but do not merge simultaneous reviewers' changes.

A copied/extracted bundle must be rebuilt and its evidence revalidated in its new environment. Internal build-cache records are not distributed. The offline page is a snapshot: regenerate with `page` after decisions or evidence change. It displays freshness and workflow state without recording browser-side approvals.

## Design reference and scope

The feature inventory and staged review design were informed by [img2threejs](https://github.com/img2threejs/img2threejs/tree/d508b596cb221f1509f6e50ab68fce275a5cfb44), particularly its detail inventory and ordered reviews. This is an independent implementation using Workshop's existing Blender/export pipeline; no img2threejs source code or assets are bundled.

Regional appearance metrics, anatomy-specific gates, material inference and silhouette-hull generation are future work. The current addition organises evidence and reviewer decisions; it does not automatically detect every visual defect.
