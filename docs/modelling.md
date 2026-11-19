# Modelling and repair recipes

Establish size, interaction and camera distance first. Preserve silhouette and structure; avoid geometry that merely copies drawn lighting. Keep useful dimensions in params. Separate moving nodes; share rings within a continuous shell.

## Joint gaps and support

Use kit.organic.closed_limb for a capped shell with shared elbow/knee rings and segment colours. Recess roots into torso/hips; overlap wrist/ankle cuffs with hands/shoes. Declare joint contacts and extreme poses. A closed limb does not guarantee shoulder attachment. For rigid seams, provide blended weights through skin(nodes,p), then inspect target-game deformation.

For shoes/pedals, cast several sole samples toward pedal tops with a small allowed offset. Move sole and ankle connection together. For hips/saddle, declare contact samples and adjust fit/seat offset without changing bike dimensions. The core assumes neither cycling nor humanoids.

## Wrapped hair and panels

A board across the forehead can match a front drawing and fail in profile. surface.wrapped_patch projects a grid around front **and temples** onto the host, offsets along its normals, adds thickness and closes perimeter faces. The wearable starter demonstrates this. Missing ray hits fail. Inspect front/profile/below and adjust coverage rather than just adding thickness to a flat plate.

surface.attachment_frame(normal,tangent) aligns local +Y to the actual host normal. Use the local shell normal and meaningful tangent for ears/fins/mounts. World-up is appropriate only when intended by the design. Stable socket axes make accessory swapping reproducible.

## Undersides and decals

Model chin/helmet undersides, soles, bases and cavity walls explicitly. Declare intended closed shells. Assign plain cells to hidden surfaces; constrain face/logo decals to their intended normal regions. Inspect below in textured/clay/checker modes.

character_cleanup.remove_internal_faces conservatively removes fully hidden faces in the same rigid node; never use another moving part as permanent occlusion. close_planar_ends handles small planar band seams, not arbitrary hole filling. Recheck budget and UV corners after cleanup.

## Static and hollow props

Place origins on useful support points; declare ground/support contacts and mount sockets. For hollow vessels/boats, model outer shell, inner wall, rim and floor thickness with correct winding. Intentional openings can coexist with watertight material. Separate mechanisms before animation. Engine collision proxies/physics belong in adapters.

## Isolate one character from a generated group

A generated scene can join a neighbor's shield to the intended character's arm and cape. In one repair, removing that shield opened both surfaces. The idle view also hid fragments that protruded during the attack. Treat the extracted figure as an intermediate asset and preserve the original mesh, reference and generation record so the cuts can be reviewed.

1. For future generation, keep the original composition as the design reference and prepare a separate input showing a single figure with both hands and gear visible. This input change was untested in the repair.
2. Inspect boundary edges immediately after the cut. Distinguish intentional openings from torn sleeve, cape or armor surfaces, then close the damaged areas and check their silhouettes. Inspect thin edge faces and small islands on both sides of the cut.
3. Replace fused gear when its intended shape is clear. Author a straight weapon and the rebuilt grip as separate parts, bind both to the same hand joint, and inspect the cuff, hand and shaft together. Inspect shields from the front and side to catch edge smearing and attachment gaps.
4. Trace imported textures through the GLB material bindings. Resolve the base color through the material's base-color texture reference. Confirm that the intended atlases appear on the exported model and still load when the editable Blender file is opened without access to the original working images.
5. Measure the support plane after geometry reduction. Review front, side, back and three-quarter views of the exported model. Inspect a wind-up or thrust that separates the moving gear from the torso and exposes the repaired surfaces. Record skeletal poses as deformation evidence. [Guided review](guided-review.md#review-in-four-stages)

Two follow-up tool ideas are a boundary-edge overlay for reviewing cuts and a contact sheet that shows the same export at rest and in a skeletal stress pose.

## Repair loop

1. Build/check; read the failing node, relation and pose.
2. Add a targeted region and inspect an actual-export close-up.
3. Repair dimensions, rings, caps, UVs, weights or attachment frames in source.
4. Rebuild and repeat relevant checks/renders; full asset checks before handover.
5. Review target-engine poses and record acceptance against export hashes.

If design is ambiguous, generate a labelled inferred reference. An actual-model render shows current geometry; an invented reference suggests a design. Keep their purposes separate.
