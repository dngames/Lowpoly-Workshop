# Reference completion

Register originals in asset.json:

```json
"references": [{"path":"ref/front.png","source":"original","view":"front"}],
"reference_completion": {"views":["front","back","left","right","top","bottom"],"notes":"Keep wheelbase and ornament count."}
```

Use `lowpoly sheets --help` for image/palette tools. Fitting uses sets, palettes, cell_class and camera hints. The historical [fitting guide](legacy-fitting.md) and [field reference](legacy-asset-json.md) describe these; apply the new imports/schema from [migration](migration.md).

ASSET references plan writes out/reference-jobs.json with missing canonical views, original hashes and prompts. It never overwrites originals. An assistant may use an available image tool, then `ASSET references import JOB_ID generated.png`. Replanning skips registered views. Records include provider/model when known, prompt, input hashes, result hash, inferred=true and pending review status.

The optional built-in provider uses the [OpenAI Images edit API](https://developers.openai.com/api/reference/resources/images/methods/edit), sending source images plus the view prompt and decoding a returned image into a local PNG. Configure OPENAI_API_KEY locally and choose a compatible --model (or LOWPOLY_IMAGE_MODEL). --max-jobs bounds each run to 1–24 requests, default one. Build/check/all never call a provider. Service pricing/availability belong to the configured provider.

```sh
lowpoly work/prop references run --model YOUR_IMAGE_MODEL --max-jobs 2
```

Generated views are plausible design proposals, not recovered facts. Review against every original; change review_status only after review. Conflicts need a design correction, not changes to originals. An agent may plan/generate missing structure within authorized scope and configured cost limit; no configured provider need not block modelling from available evidence.

## Pictures that fit well

Most fitting trouble starts in the picture. Fitting classifies sheet pixels by their nearest palette colour and takes the background from the image border, so:

- **One subject per view on a plain, even background.** Nothing held or standing nearby unless it belongs to the asset; it joins the silhouette.
- **Matching views.** Same scale, level camera, close to orthographic, every view of a turnaround drawn to the same proportions.
- **Flat or softly shaded colour.** Cast shadows, rim light, gradients and strong textures pull pixels towards the wrong palette entry and mislead the [colour match](colour-match.md). Even ink outlines are fine when declared as `_line_class`.
- **Characters in a relaxed A-pose.** Arms about 45° down with a clear gap to the body, legs slightly apart, hands open. Separated limbs give separate silhouettes to fit; a T-pose puts hands at the frame edge.
- **Show the shapes you model.** Eyes open, hair off the face, hoods and hat brims pushed back. Whatever the picture hides has to be invented.
- **Ask for what you want, not what you don't.** In generation notes, "smooth fabric" works better than "no wrinkles" and "empty hands" better than "no weapon".

A note to start from, for a character's `reference_completion.notes`:

```text
Relaxed A-pose, arms angled about 45 degrees down with a clear gap from the body, hands open,
eyes open, calm expression, hair clear of the face, flat even lighting, same scale as the front view.
```

Generated pictures do not become fit targets automatically. Add approved ones to explicitly labelled sets and report their scores separately from originals. source=rendered records actual-model evidence, not an independent reference.

Provider tests mock HTTP and verify multipart requests, bounded jobs, immutability, resume and ledger. No paid call is needed for selftest. An artist/assistant writes gen.py; this CLI does not create geometry from images automatically.
