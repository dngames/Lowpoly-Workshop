Pixal3D standalone run pack - just double-click, no knowledge needed
=====================================================================

WHAT THIS DOES
  Turns the bundled front-view reference (a rest house) into a low-poly
  checked GLB: prepare input -> generate mesh -> decimate -> build -> check.
  No installs, no accounts, no AI agent. Python is bundled inside.

RUN
  1. Extract this zip to a short path like D:\Pixal3D-RunPack
  2. Double-click ONE of:
       Run-Generate.cmd      CPU machine (slow: hours to days on old i5/i7)
       Run-Generate-GPU.cmd  graphics-card machine, 6GB+ VRAM (minutes)
  3. Wait. A black window shows live progress; it stays open when done.

SUCCESS LOOKS LIKE
  - job\inputs\pixal3d_raw.glb      (generated high-poly mesh)
  - job\out\model.glb               (low-poly checked deliverable, needs Blender)
  - job\run.log                     (full log of this run)

NOTES
  - Blender is only needed for the decimate/build/check stages. Without it
    the run stops cleanly after generation and tells you the exact next steps.
  - Needs ~15 GB free disk while running.
  - Details: workshop\docs\pixal3d.md (full workflow documentation).

TROUBLESHOOTING
  - Window won't start: you must extract the zip first (don't run from inside it).
  - Out of memory on GPU: use Run-Generate.cmd (CPU fallback, slower).
  - Slow CPU run: normal on old hardware; -Threads defaults to core count.

CONTENTS
  python/             private Python 3.14 (used automatically, untouched system)
  launch.py           hermetic repo launcher
  workshop/           Lowpoly-Workshop source (git tag e330d83)
  models-sv/          9 Q8 single-view GGUF weights (~7.5 GB)
  runtime-vulkan/     portable trellis-cli (GPU via Vulkan, CPU fallback)
  runtime-cpu/        native AVX2 trellis-cli + MinGW DLLs (fast CPU path)
  smoke-asset/        test asset (reference + generator wired to load output)
  wheels/             fallback Python wheels (only if python\ is missing)
