---
name: lowpoly-workshop
description: Build or repair editable low-poly game models from reference images through a parametric Blender and GLB pipeline, with contract checks and actual-export review.
---

Use the installed lowpoly CLI. Read references/quickstart.md for setup and references/contracts.md for generator/schema details.

Establish intended scale, use, visible design and game contract from the request/project. Choose a starter; keep engine-specific names, masks and staging in the consuming adapter. Write deterministic portable gen.py with editable dimensions, outward surfaces and named pivots/sockets.

When important structure is missing, plan inferred views and use an available image-generation provider within the user's authorized scope and configured cost limit. Register provenance; never overwrite originals or describe invented details as recovered. Read references/references.md. Without a configured provider, model reasonable hidden structure and record assumptions.

For gaps, wrapping, accessories, hollow props, decals and support contacts, read the relevant references/modelling.md recipe. Declare intended closed shells, relations, stress poses and targeted regions. Use host normals for attachment/offset, shared rings and thickness for continuous surfaces, and controlled overlap at moving joints. Preserve UV corners during cleanup.

For guided projects, read references/guided-review.md. Establish important features and original/inferred evidence, bind them to exported parts and required views, then use workflow next to resume. Record repair findings. Accept features/stages only after actual inspection and within user authorization; a numeric score is not evidence. Existing projects can remain in legacy mode.

Build/check, then inspect actual-export front/profile/back/below and useful close-ups in textured/clay/checker/wireframe modes. Repair source geometry/UV/frames/weights and rebuild; render again. An actual-model diagnostic and an inferred design reference have different meanings. Finite checks do not replace visual review.

Use the generator's skin hook for skeletal exports and inspect target-runtime deformation. Ordinary rigid checks do not evaluate skinning. Preserve existing game contracts and add requirements through adapters.

Prepare the local review page and checksummed bundle. Record approval only after user/artist acceptance of the current export; approval is hash-bound. Respect requests to review one model before the next. This skill grants no authorization to publish/share/create repositories.

After fitting, use `lowpoly ASSET coverage` for geometric observation gaps and a held-out CPU review view. Read references/appearance-workflow.md, references/build-validation.md and references/legacy-port-audit.md. Coverage is not paint acceptance. Use `paint` for supplied-sheet class diagnostics and `pieces` for disconnected-component views. CPU palette proofs never substitute for actual-export/runtime review.

When the user supplies an existing low-poly mesh (a GLB) to start from, skip generation and read references/base-mesh.md: collect target-look views if needed, run `lowpoly ASSET base import PATH --licence ID --credit TEXT [--front ...] [--height M] [--budget N] [--drop-plinth | --drop-node NAME]` (record the licence and credit; never commit third-party meshes or renders of them to a repository that cannot carry their licence), load it in `gen.py` with `lowpoly_workshop.base_mesh.load_glb_node` (`separate_nodes=True` for editable parts, `propose_palette` for the base's own colours), remodel, then build, check and review; use `lowpoly ASSET base bake` to put the base's colours onto hand-built LODs. Only a reduction over `--budget` needs Blender.

When using `raven38/pixal3d.cpp` (`trellis-cli`) to generate 3D meshes from reference images (optional; not needed when a base mesh is supplied), read references/pixal3d.md: run `lowpoly ASSET pixal3d prep` and `lowpoly ASSET pixal3d run` to create `inputs/pixal3d_raw.glb`, then use Blender MCP (`tools.blender.execute_blender_code` with `lowpoly ASSET pixal3d mcp-script`, or `lowpoly ASSET pixal3d decimate`) only to reduce polycount and normalize orientation/scale/ground into `inputs/pixal3d_lowpoly.glb` before `build`, `check`, and `review`. For game LODs below a few thousand triangles, keep the hand-built LODs and run `lowpoly ASSET pixal3d bake` to bake the generated colours onto them instead.
