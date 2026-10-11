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

## Repair loop

1. Build/check; read the failing node, relation and pose.
2. Add a targeted region and inspect an actual-export close-up.
3. Repair dimensions, rings, caps, UVs, weights or attachment frames in source.
4. Rebuild and repeat relevant checks/renders; full asset checks before handover.
5. Review target-engine poses and record acceptance against export hashes.

If design is ambiguous, generate a labelled inferred reference. An actual-model render shows current geometry; an invented reference suggests a design. Keep their purposes separate.
