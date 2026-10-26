# Higher-density character construction: the trail guide

## Design input and provenance

This example began with a written brief and procedural code, **not an original 2D reference sheet**. The newly added diagram explains that brief; it was made after the model and is not evidence of reference matching.

![New explanatory 2D front/side construction notes, not historical concept art.](images/character-design-notes.svg)

## Exported result

This is a geometry-density exercise, not a detailed sculpted/cloth-textured character showcase. More triangles alone do not deliver that level of finish.

Use the same editable Workshop pipeline to build a smoother, more detailed stylized character. This original example has **21,162 triangles**, compared with 1,010 in the [low-poly walkthrough](create-character.md). Its explicit budget is 40,000 triangles; choose your own target for your intended use.

![Actual-export views of the high-poly guide: rounded face, side silhouette, backpack details and waving pose.](images/create-character-high.png)

## Build the example

From a source checkout, with Workshop installed and Blender configured:

```sh
python scripts/character_example.py work/trail-guide-high --detail high
lowpoly serve work/trail-guide-high/out/page --port 8000
```

Open **http://127.0.0.1:8000**. The helper creates an isolated editable project, builds and checks its GLB, renders its review poses, and generates a local viewer and source bundle. Use an empty destination. To edit before building, add `--source-only` to the first command.

Source is bundled under `lowpoly_workshop/assets/examples/trail-guide-high`. Copy that folder into an empty project if you prefer to use the normal CLI directly.

## Add form before adding density

The character keeps the low-poly guide's dimensions, palette, node hierarchy and metres/Y-up/+Z-front convention. Compare the two generators:

- **Smooth volumes:** 21 latitude rings form rounded heads, hands, cap and backpack; the head has 48 segments around its circumference. Positive end-ring radii keep caps closed without repeated pole vertices.
- **Face:** a shaped nose and ears give the silhouette depth; inner ears and projected eyebrows add expression. The separate thin eye, cheek and smile patches follow the head.
- **Clothing and pack:** a rounded backpack has a front pocket and straps passing over the shoulders. A narrow jacket zip, fasteners and sleeve cuffs add visible structure.
- **Hands and boots:** overlapping thumb forms, separate dark soles and light laces make the details readable from different views.

Open `gen.py` and change `height`, `body_width` or `pack_depth`, or edit the `ATLAS` palette. The 1.72 m default height includes the cap; geometry and pivots scale together and the soles remain at ground zero. Recheck edited designs rather than assuming all parameter combinations have been reviewed.

The extra geometry is authored directly in the generator. This example does not rely on a Blender subdivision modifier, displacement, a sculpt service or inferred reference images. A film sculpt may use millions of polygons; here “high-poly” describes the higher-detail companion to the small game character.

## Check shape and movement

```sh
lowpoly work/trail-guide-high build
lowpoly work/trail-guide-high check
lowpoly work/trail-guide-high review
lowpoly work/trail-guide-high page
```

Inspect front, side, back and quarter views, including the half-raised and waving poses. Check the cap silhouette, nose, ear attachment, backpack straps, soles and arm joints. The contract declares closed solid nodes, ground contact, shoulder/elbow/hip/ankle connections and hand-to-head clearance. Thin facial paint is deliberately excluded from solid closure checks.

The two-second **Greeting** clip raises the arm less steeply than the low-poly example to leave room for the smoother cap and added thumb. The unit regressions sample the clip for joint contact and hand/head clearance. The local viewer lets you play and scrub the exported animation.

This is a rigid-part stylized character. Its overlapping joints support this standing gesture; it is not a skinned anatomy mesh, facial rig or retopologized animation character. A successful check does not approve the design or prove every possible motion. For a game, set a runtime budget and verify the importer; a baking/retopology workflow would be a separate step.

## Package and reproduce the pictures

```sh
lowpoly work/trail-guide-high package
python scripts/character_visuals.py work/trail-guide-high --high
```

The project exports `guide.glb`, its editable Blender scene, atlas and mask, check results, twelve review images, local viewer and checksummed source bundle. The second command composes the actual-export pictures above into `docs/images/create-character-high.png`; the adjacent evidence JSON records source/spec, model and image hashes. Neither the example nor its pictures assert artistic approval.
