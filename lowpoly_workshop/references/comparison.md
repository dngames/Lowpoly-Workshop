# What Workshop adds to a Blender agent

Workshop is a reusable modelling workflow, not a trained image-to-mesh model or an autonomous artist. A plain Blender agent can write Python, create meshes, render, inspect and repair them. With enough instructions and engineering it can reproduce this workflow. No measured superiority is claimed.

| Concern | Plain Blender agent | Workshop today |
| --- | --- | --- |
| Geometry decisions | Agent or artist authors Blender geometry | Agent or artist authors a parametric generator using optional helpers |
| Repeatability | Depends on saved scripts and session discipline | Source, editable parameters, declared outputs and a rebuildable bundle |
| Game requirements | Usually supplied in prompts or custom scripts | Configurable node, pivot, socket, budget, mask and topology contracts |
| Repair review | Agent chooses renders and checks | Actual-export multi-angle/underside/region renders, plus finite contact and fit checks |
| Acceptance | A statement or external process | Export-hash-bound acceptance that becomes stale after changes |
| Setup | Blender plus an agent connection | Python dependencies, Blender, CLI and project schema |

These are workflow differences, not proof of better models. For a quick one-off object, the extra setup can cost more than it saves. Shared projects, repeatable variants, accessories and strict game contracts are the intended use cases. The artist still decides if hair looks natural, a face resembles its reference, or a pose feels right. Checks require correct declarations and only cover the sampled conditions.

## Related tools

Reviewed 2026-10-11 from their own project descriptions; these are not head-to-head test results.

- [Tripo](https://developers.tripo3d.ai/en) and [Meshy](https://www.meshy.ai/api) offer image/text-to-3D, texturing, topology processing and rigging/animation. Workshop does not currently provide their neural mesh-generation capability.
- [TRELLIS](https://github.com/microsoft/TRELLIS) publishes a generative 3D model and inference code. Running a generative backend is a different route from authoring parametric geometry.
- [MCP for Blender](https://github.com/ahujasid/mcp-for-blender) connects agents to Blender, including code execution and visual verification. Workshop can be used alongside an agent connection; having an agent alone is not a unique feature.
- [img2threejs](https://github.com/img2threejs/img2threejs) is a close neighbour: reference-driven procedural reconstruction, quality gates and visual review for Three.js. Editable code and staged review are not unique to Workshop.

Potential future integrations could feed generated meshes into a repair/review process. They are not implemented here. Importing arbitrary topology into the parametric generator workflow would require additional work.

## Evidence needed

Use the [benchmark protocol](benchmark.md) to compare time, cost, defects and accepted runtime results. Record failures and agent/artist effort. Local regression passes demonstrate specific checks, not competitive advantage or willingness to pay.
