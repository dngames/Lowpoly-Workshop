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

Generated pictures do not become fit targets automatically. Add approved ones to explicitly labelled sets and report their scores separately from originals. source=rendered records actual-model evidence, not an independent reference.

Provider tests mock HTTP and verify multipart requests, bounded jobs, immutability, resume and ledger. No paid call is needed for selftest. An artist/assistant writes gen.py; this CLI does not create geometry from images automatically.
