# Trail guide character source

An original character tutorial for Lowpoly Workshop: rounded head, projected face paint,
cap, jacket, backpack, boots and a rigid-node greeting. Written design brief; no supplied
image or inferred reference is claimed. Read `docs/create-character.md` in the source checkout.

The generator exposes height, torso width and backpack depth. Main jacket/cap colour uses
mask R; lining/badge uses G. Node pivots and geometry are authored in world-rest metres,
+Y up, facing +Z, character left +X. Face paint follows Head as a separate thin child;
closed-solid checks apply to the head itself, not the intentionally thin paint.

This example demonstrates a standing rigid-part gesture, not a walking controller or a
skinned/retargeted character. The supported greeting is sampled in the unit tests. Review
other motions and edited dimensions in the intended runtime. No artistic approval is recorded.

Copy this folder into an empty workspace, then run `lowpoly PATH all` or use
`scripts/character_example.py` from the source repository to create and build it.
