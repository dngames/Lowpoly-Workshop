# Standalone no-agent run pack (`Pixal3D-RunPack.zip`)

One-click Pixal3D generation for a machine without an AI agent:
unzip, double-click `Run-Generate.cmd` (CPU) or `Run-Generate-GPU.cmd`
(graphics card, 6GB+ VRAM), wait. Scripts are plain Windows PowerShell 5.1.

## Layout of an assembled pack root

```
<pack>/
  Run-Generate.ps1  Run-Generate.cmd  Run-Generate-GPU.cmd  README-FIRST.txt
  launch.py             # hermetic repo launcher (embedded python ignores PYTHONPATH)
  python/               # private Python 3.14 embeddable + deps (no system install)
  workshop/             # Lowpoly-Workshop source (git archive of a release tag)
  models-sv/            # 9 Q8 single-view GGUF weights (~7.5 GB)
  runtime-vulkan/       # portable trellis-cli (GPU via Vulkan, CPU fallback)
  runtime-cpu/          # native AVX2 trellis-cli + MinGW DLLs (fast CPU path)
  smoke-asset/          # test asset (reference + generator wired to load output)
  wheels/               # fallback Python wheels (only if python/ is missing)
```

## Assembling (on a machine that already has a working setup)

1. Embeddable Python: download `python-3.14.7-embed-amd64.zip`, extract to
   `python/`, uncomment `import site` in `python314._pth`, then with
   `PYTHONNOUSERSITE=1` run `get-pip.py` and install
   `numpy scipy Pillow opencv-python-headless` from local wheels
   (`--no-index --find-links wheels --ignore-installed`).
2. `workshop/`: `git archive` of the release tag + extract (use Python
   `zipfile`, not `Expand-Archive`, which can hang under Defender load).
3. Copy in `models-sv/`, both runtimes, and `smoke-asset/` (the test asset
   minus `inputs/`, `out/`, `.workshop/`).
4. Self-test the exact double-click path: `Run-Generate.ps1 -PrepOnly`,
   then delete `job/` (and any `.venv/`).
5. `python build_zip.py <pack_root> <output_zip>` + SHA-256 the result.

## Notes

- Blender is optional on the target: without it the run stops cleanly after
  mesh generation and prints the exact decimate/build/check follow-ups.
- `Run-Generate.ps1` uses only PowerShell 5.1 syntax (no `?:` ternaries).
  Verify with the .NET parser before shipping.
- See `docs/pixal3d.md` for the full workflow this pack automates.
