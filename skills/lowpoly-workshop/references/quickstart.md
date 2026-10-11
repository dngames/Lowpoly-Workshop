# Quickstart

Choose a workspace drive with enough room for models, renders, dependencies and caches. The Windows example below uses D:; change the paths for your machine. Existing tools may be read from another drive.

```powershell
Set-Location D:\code\Lowpoly-Workshop
New-Item -ItemType Directory -Force .runtime\tmp,.runtime\cache | Out-Null
$env:TEMP="$PWD\.runtime\tmp"
$env:TMP=$env:TEMP
$env:PIP_CACHE_DIR="$PWD\.runtime\cache\pip"
$env:PYTHONPYCACHEPREFIX="$PWD\.runtime\cache\python"
$env:KIT_BLENDER='D:\tools\blender\blender.exe'
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install .
lowpoly doctor
lowpoly selftest --blender
lowpoly new work\wearable --kind wearable
lowpoly work\wearable all
lowpoly serve work\wearable\out\page --port 8000
```

On macOS/Linux use equivalent environment variables, `.venv/bin/activate` and your Blender executable. The kit never installs/downloads Blender automatically. `python -m lowpoly_workshop` works if `lowpoly` is not on PATH.

## Commands

| Command | Purpose |
| --- | --- |
| `new FOLDER --kind KIND [--title TITLE]` | Starter project; refuses nonempty destination |
| `doctor` | Check imports and locate Blender |
| `selftest [--blender]` | Installed-package smoke checks and optional actual exports |
| `ASSET build [--force]` | GLB/blend/atlas/mask, with hash-based cache |
| `ASSET check` | Export contracts and source relations/UV rules; failure exit code |
| `ASSET inspect` | Topology/decal diagnostics without Blender |
| `ASSET review` | Actual-GLB renders and configured regions |
| `ASSET skin` | Separate `out/skinned.glb` from skeleton hook |
| `ASSET all` | Build/check/render/compare/review/page/package |
| `ASSET page` / `package` | Local viewer / self-contained asset zip |
| `ASSET fit all --grid` | Camera fitting for configured sheet views |
| `ASSET refine param:step --sweeps 4` | Tune exposed parameters |
| `ASSET render views` / `render show` / `compose` | Solved views, scene shots, comparison strips |
| `ASSET references plan --views back left right` | Queue missing design views |
| `ASSET references import JOB_ID IMAGE` | Import generated image with provenance |
| `ASSET references run --model MODEL --max-jobs 1` | Optional configured image API |
| `ASSET approve --note TEXT` | Record reviewed export hashes after visual acceptance |
| `serve FOLDER --port 8000` | Localhost-only viewer server |
| `release DESTINATION.zip` | Source archive and SHA-256 manifest outside source tree |

`all` exports rigid models. Run `skin` separately, then `page` to include the optional skeletal character. Ordinary checks do not evaluate skinning.

`KIT_BLENDER` or `BLENDER` selects the executable. `LOWPOLY_KIT_HOME` searches an existing install. `LOWPOLY_BLENDER_THREADS` defaults to 2, `LOWPOLY_FIT_WORKERS` to 4, and review `LOWPOLY_RENDER_SAMPLES` to 16. TEMP/TMP control temporary renders. Reduce review modes/views while iterating, then inspect all relevant angles before approval.

Generators execute Python. Inspect unfamiliar source before running; project path validation is not a Python sandbox.
