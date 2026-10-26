# Tiny Tour: Yuzu Station Rest House

First-party Tiny Tour architecture, included at the repository owner's request.
See `provenance.json` for the source commit, hashes and adaptation notes.
Released in Workshop under its MIT license. The original 2D design sheet and prompt are included in `ref/` and registered in
`asset.json`. Game textures, branding atlases and runtime placement code are excluded.

A 14 x 9 m two-storey rest house, with a hipped roof and front gable, covered
terrace, four canopy supports, three benches, framed windows and a chimney.
All four source detail levels are retained: 685 / 517 / 201 / 28 triangles.
The far proxy deliberately omits terrace furniture and facade openings.
Metres, +Y up, street/front +Z; origin at the base centre.

Copy this directory to an empty workspace and run `lowpoly PATH all`, or use
`python scripts/building_example.py work/station-rest-house` from the source checkout.
Read `docs/create-building.md` for the walkthrough. Geometry, palette and detail
policy are editable in `gen.py`; budget metadata is in `inputs/construction.json`.
The generator checks individual closed primitives before hidden-face removal;
whole cleaned assemblies are not claimed to be watertight single shells.
No artistic approval is asserted for the Workshop export.
