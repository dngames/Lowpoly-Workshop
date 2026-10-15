# Lowpoly Workshop

An open-source workshop for building, checking and repairing editable low-poly game assets from references.

An artist or AI assistant turns drawings or photographs into editable parametric Blender projects and GLB assets. Python tools measure references, fit cameras, export models, check contracts, render problem areas and package a local review page. Characters, wearables, vehicles, hollow objects and static props share the same core.

**0.3.0 · early release · MIT.** Code, documentation and bundled first-party examples are open source; see [licensing](docs/licensing.md). Original game artwork is excluded. Artistic quality and target-engine compatibility still require review.

## What it adds to a Blender agent

A Blender agent can already write scripts, model, render and repair assets. Workshop supplies reusable geometry helpers and a repeatable build/check/review/package process: configurable game contracts, joint and support checks, actual-export close-ups, and approval records that expire when exports change. The artist or agent still makes the modelling decisions.

A capable agent could implement the same workflow. We have not measured a speed, cost or quality advantage over a plain Blender agent or image-to-3D services. See the [comparison](docs/comparison.md) and [benchmark protocol](docs/benchmark.md). [Repair demonstrations](docs/repair-demos.md) show the kind of problem this workflow addresses.

## Start

Python 3.10+ and Blender 4.5 are required. Set `KIT_BLENDER` to the Blender executable if it is not on PATH.

```sh
python -m venv .venv
# Activate the environment using your shell, then:
python -m pip install .
lowpoly doctor
lowpoly new work/crate --kind static-prop --guided
lowpoly work/crate all
lowpoly serve work/crate/out/page --port 8000
```

Open http://127.0.0.1:8000. The viewer uses bundled Three.js locally. No CDN, account or image-generation service is required for modelling, fitting, export or review. See the [Windows/D: quickstart](docs/quickstart.md) for local caches.

## Included

- Five independent starters: static-prop, hollow-prop, wearable, articulated, character.
- Parametric primitives, closed organic shells, conservative hidden-face cleanup and surface-projected wrapping.
- Named pivots/sockets, rigid-node clips and optional generator-defined skeletal export.
- Configurable budgets, topology, joint contact, clearance, fit/support, ground, materials, masks and decal checks.
- Multi-view camera fitting and rendered comparisons.
- Colour match: atlas cells against the reference pixels they cover, with trust maps and palette suggestions.
- Optional feature checklist, source/evidence-bound staged review, saved findings and next-action guidance.
- Actual-export review: back/underside, poses, clay/checker/wireframe, explicit and diagnostic close-ups.
- Optional inferred reference views with original hashes and a provenance ledger.
- Content cache, checksummed source/asset archives, offline review viewer, tests and an [agent skill](lowpoly_workshop/SKILL.md).

## Workflow

Establish scale and use → write `gen.py` → build → fit supplied views → inspect failures and close-ups → repair → rebuild → review in the target runtime.

The CLI executes a generator written by an artist or AI assistant. It does not reconstruct arbitrary images into meshes by itself. The optional image provider creates design references, not geometry. Invented hidden parts stay labelled and reviewable. Passing checks cannot prove a silhouette, expression, texture or movement looks right.

## Documentation

[Guided review](docs/guided-review.md) · [Quickstart](docs/quickstart.md) · [Contracts](docs/contracts.md) · [Repair recipes](docs/modelling.md) · [Colour match](docs/colour-match.md) · [Repair demonstrations](docs/repair-demos.md) · [Comparison](docs/comparison.md) · [Benchmarks](docs/benchmark.md) · [Roadmap](docs/roadmap.md) · [References/providers](docs/references.md) · [Review/release](docs/review-release.md) · [Game adapters](docs/adapters.md) · [Migration](docs/migration.md) · [Testing](docs/testing.md) · [Licensing](docs/licensing.md)
