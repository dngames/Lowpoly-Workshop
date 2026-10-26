# High-poly trail guide character source

An original, higher-detail companion to the Workshop's low-poly character example.
Rounded volumes, modelled nose/ears/thumbs, backpack pocket and straps, jacket zip/cuffs,
boot soles and laces add form at 21,162 triangles (40,000 triangle contract).
Written design brief; no supplied or inferred reference image is claimed.

Read `docs/create-character-high.md` in the source checkout. Use
`python scripts/character_example.py work/trail-guide-high --detail high`, or copy this
folder into an empty workspace and run `lowpoly PATH all`.

Height, torso width, backpack depth and atlas colours remain editable. Geometry/pivots
use metres, +Y up and +Z front. FacePaint is a thin child of the closed Head node.
The two-second greeting uses rigid nodes with overlapping capped joints; inspect
other motions and parameter changes again. This is a stylized higher-detail mesh,
not a film sculpt, skinned anatomy mesh or retopologized animation character.
No artistic approval or target-game integration is asserted.
