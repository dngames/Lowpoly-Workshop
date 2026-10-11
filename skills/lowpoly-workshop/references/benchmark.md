# Benchmark protocol

Status: planned; no comparative runs or willingness-to-pay results have been recorded. Do not publish speed, cost or quality claims from the synthetic repair demonstration.

## Question

Does Workshop reduce the total time and cost to a visually accepted, editable in-game asset compared with a plain Blender agent and hosted image-to-3D plus ordinary repair?

## Cases and acceptance criteria

Choose rights-cleared references not taken from Workshop's starters. Freeze the brief, budget, scale, required views, output formats, interaction points and acceptance criteria before any run. Use at least one character, one vehicle and one static prop.

| Case | Common requirements |
| --- | --- |
| Character with wearable | Inspect front, side, back and underside; connected joints in agreed poses; hair follows head; accessory fit; valid textures; agreed deformation |
| Vehicle | Agreed wheelbase and moving parts; named saddle/grip or other interaction sockets; rider/driver fit in agreed poses; no unintended gaps or intersections |
| Static or hollow prop | Agreed silhouette, scale, origin and support; correct undersides, cavity thickness where needed, UVs/materials and engine import |

Give every route the same references, including any inferred views. If one route generates extra views, give those views to all routes and record their costs separately. Do not treat invented views as ground truth. If a route cannot meet a requirement, record the limitation and any workaround rather than silently relaxing the brief.

## Routes

1. Plain Blender agent: same coding agent/model as route 2, Blender Python and ordinary documentation, no Workshop helpers or skill. It may write its own helpers and checks. Save its scripts.
2. Workshop: same agent/model, its documented tools and helpers, same Blender version and target runtime.
3. Tripo or Meshy: record the service/model/version/settings, then allow normal Blender repairs and integration to meet the same brief. Record generation and repair time separately.

Set identical time/cost caps and reviewer access. Run at least three independent fresh-session attempts per case/route; alternate route order. Record model/provider versions, seeds where supported, hardware, agent tokens, prompts, edits, retries and all outputs. Report first-time setup separately from repeated-use runs. Never reuse one route's finished generator in another route.

## Measure and review

Measure wall-clock time from reference intake to acceptance, human active minutes, agent/API spend, generation/render/repair time, retries, triangles, file sizes, and failed requirements. Include abandoned runs; blank means unmeasured, not zero. Use benchmarks/results-template.csv as a starting record, with one row per attempt and linked evidence. It contains no observations yet.

Have reviewers assess anonymized actual exports against the frozen brief, including held-out views/poses and the same target-engine import. Use independent checks appropriate to each requirement; Workshop's own source-aware checks must not be the sole acceptance judge for competing outputs. Record the evaluator and its version. Inspect both textured and plain surfaces; textures must not conceal missing geometry. Test editability with the same requested dimension/accessory change, and count the additional work.

Report individual runs, acceptance rate, median and range of time/cost, and remaining defects. Do not report a median for successful runs without also reporting failures. Small samples are preliminary, not a market-wide result.

## Product decision

Ask external developers to install and finish a case without the maintainers operating it. Record setup friction and support minutes. Interview them about which work it saved and what they would pay for; a stated price is not a purchase. Paid pilots can test actual willingness to pay after reliability and support costs are understood. No customer outreach or paid provider calls are performed by this protocol.
