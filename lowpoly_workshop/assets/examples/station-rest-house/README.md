# Tiny Tour: textured Yuzu Station Rest House remodel

Original 2D design → editable architectural geometry → painted materials → actual GLB review.
The historical six-view sheet and prompt are in `ref/`; new material art, its prompt and
packed pixels are in `inputs/`. `provenance.json` records source hashes and the remodel.

Wall footprint 14 x 9 m, +Y up, +Z street, origin at ground-centred base. The model adds
closed curved roof tiles and ridge caps, bevelled timber and stone, framed glazing,
terrace braces and slatted benches. Detail levels: 34,680 / 5,132 / 1,212 / 28 triangles.
The nearer-level budget is intentionally increased; inspect performance in the intended game.

Copy the folder into an empty workspace and run `lowpoly PATH all`, or use
`python scripts/building_example.py work/station-rest-house` in the source checkout.
`gen.py` authors geometry; `station_materials.py` builds the embedded 2048-square atlas.
The generator checks each closed primitive; the overlapping assembly is not declared
a single watertight solid. The portable default is the painted atlas. Runtime named-surface
conversion belongs to the game adapter, since Tiny Tour replaces imported materials.

MIT first-party example included at the owner's request. No artistic approval is asserted.
