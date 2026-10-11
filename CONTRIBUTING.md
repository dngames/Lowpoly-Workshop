# Contributing

Run unit regressions and `lowpoly selftest --blender` after geometry/export changes. Add small procedural broken/correct cases for demonstrated failures. Keep references out unless redistribution rights are recorded. Preserve schema compatibility or document migration. Keep game contracts in adapters, avoid absolute paths and distinguish actual-model renders from invented references.

Bug reports should include versions, minimal asset.json/gen.py, the failed check/pose, close-up and expected behaviour. Remove secrets/private artwork.

After editing docs/notices, run `python scripts/sync_skill_docs.py` before packaging. CI verifies that the installable skill and wheel carry matching local references.

Use the workflow-experience issue template for independent adoption reports. Follow docs/benchmark.md for comparative observations; include failures and avoid presenting planned runs as measured results. Contributions are accepted under the project MIT license; only contribute material you are authorized to license.
