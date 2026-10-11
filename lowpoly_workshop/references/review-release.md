# Review and release

Serve the page over localhost. Inspect silhouette, below, texture/checker/wireframe, sockets, clips and problem regions. Every exported-model shot records its GLB SHA-256. Add close-ups in review.regions; diagnostic regions are also added for duplicate/degenerate/nonmanifold source meshes and decal issues. Head/helmet fit, expression and fringe shape still need judgement.

`lowpoly ASSET approve --note "Reviewed below and in game"` records current export hashes. Use only after user/artist acceptance. Changed exports make approval stale. Approval never changes automated failures to passes.

ASSET package creates project/ (source, refs, cameras, exports, checks/review), toolkit/lowpoly_workshop/, rebuild.py, notices and a relative checksum manifest. Extract cleanly, install dependencies/set KIT_BLENDER, then python rebuild.py. Inspect unfamiliar Python before execution. Geometry/contracts should reproduce; Blender metadata/archive timestamps are not promised byte-identical across platforms.

From a source checkout, `lowpoly release ../Lowpoly-Workshop-0.2.2.zip` creates source/docs/tests/notices plus a manifest and sibling SHA-256. Wheel-only installs cannot create source releases. Verify clean extraction and wheel installation before release.

The original kit and examples are first-party material, confirmed by their owner and released under MIT; see licensing.md. Preserve all notices and record permissions for any newly contributed references. A license grants redistribution rights; it does not authorize an assistant to publish unrelated user projects. Release notes must distinguish observed checks from planned benchmarks and untested engine support.
