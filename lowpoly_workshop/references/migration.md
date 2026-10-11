# Migration from the original kit

Existing game projects retain their original kit and outputs. To port deliberately:

1. Copy the asset and every cross-project generator dependency into one portable project.
2. Set schema_version=2, kind, profile and relative generator/output paths.
3. Replace `from kit...` with `from lowpoly_workshop.kit...`; remove absolute path injection.
4. Include shared sources locally and resolve from __file__; do not reference another checkout's caches.
5. Keep fit sets/cameras/palettes/parameters. Register references with truthful source labels.
6. Add closed shells, contact/fit relations, stress poses, review regions and the correct mask convention.
7. Rebuild/check, compare references and inspect the target runtime before replacing shipped assets.

Historical docs/legacy-* retain modelling/fitting detail. Their kit imports, lowpoly.py commands and artifact-host page instructions are historical. Use the installed CLI/current local viewer. Consumer-specific exporters and adapters should stay in the consuming project.
