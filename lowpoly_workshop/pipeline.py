#!/usr/bin/env python3
"""Low-poly asset kit: one command per pipeline stage, all driven by an asset folder.

usage: python lowpoly.py <asset_dir> <command> [args]
  fit <set|all> [view ...] [--grid] [--fresh] [--noopt]   solve camera (+ pose) per sheet view
  refine name:step ... [--sweeps N] [--sets a,b]          tune generator params against all solved views
  build [output.glb ...]                                  Blender: .blend + .glb + atlas + kit mask
  check                                                   contract checks on the exported GLBs
  render [views [set ...] | show]                         Blender renders through the solved cameras / shots
  compose                                                 sheet | render | overlay | diff strips + scores
  page                                                    hand-over web page folder (+ files.json to publish)
  package                                                 zip the asset with .blend files and scripts
  all                                                     build, check, render views + show, compose, page, package
python lowpoly.py sheets <tool> ...                          sheet measuring tools (see kit/sheets.py)
"""
import glob
import json
import os
import shutil
import subprocess
import sys
import zipfile
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
KIT_HOME = os.environ.get("LOWPOLY_KIT_HOME", os.path.join(os.path.expanduser("~"), ".lowpoly-kit"))


def find_blender():
    for env in ("KIT_BLENDER", "BLENDER"):
        if os.environ.get(env) and os.path.exists(os.environ[env]):
            return os.environ[env]
    cands = glob.glob(os.path.join(os.path.expanduser("~"), ".local", "opt", "blender-*", "blender")) + \
        glob.glob(os.path.join(KIT_HOME, "blender", "*", "blender")) + \
        glob.glob(os.path.join(KIT_HOME, "blender", "*", "blender.exe")) + \
        glob.glob(os.path.join(KIT_HOME, "blender", "*", "Blender.app", "Contents", "MacOS", "Blender"))
    if cands:
        return sorted(cands)[-1]
    found = shutil.which("blender")
    if found:
        return found
    raise FileNotFoundError("Blender not found. Install Blender 4.5 and set KIT_BLENDER to its executable.")


def blender(script, *args):
    if script == "render.py":
        from .kit.asset import Asset
        a = Asset(args[0])
        if a.spec.get("render_engine") == "raster":
            from .kit.preview import run
            run(a, list(args[1:]));return
    cmd = [find_blender(), "-t", os.environ.get("LOWPOLY_BLENDER_THREADS", "2"), "-b", "--factory-startup", "--python-exit-code", "1", "-P", os.path.join(HERE, "kit", "blender", script), "--"]
    cmd += [str(x) for x in args]
    p = subprocess.run(cmd, capture_output=True, text=True)
    keep = ("BUILT", "RENDERED", "SHOT", "REVIEW", "SKIN", "Error", "Traceback", "File \"", "    ")
    for line in (p.stdout + p.stderr).splitlines():
        if line.startswith(keep) or "Error" in line or "Traceback" in line:
            print(line)
    if p.returncode != 0:
        print((p.stdout + p.stderr)[-6000:])
        sys.exit("Blender failed (%d)" % p.returncode)


def _fit_one(args):
    folder, st, view, keep, grid, opt = args
    from lowpoly_workshop.kit.asset import Asset
    from lowpoly_workshop.kit.camfit import fit_view
    a = Asset(folder)
    v, sc = fit_view(a, st, view, keep=keep, grid=grid, optimize=opt)
    return st, view, sc, [round(float(x), 3) for x in v]


def cmd_fit(folder, args):
    from lowpoly_workshop.kit.asset import Asset
    a = Asset(folder)
    flags = {x for x in args if x.startswith("--")}
    names = [x for x in args if not x.startswith("--")]
    sets = list(a.sets()) if not names or names[0] == "all" else [names[0]]
    views = names[1:]
    jobs = [(folder, st, v, "--fresh" not in flags, "--grid" in flags, "--noopt" not in flags)
            for st in sets for v in a.views(st) if not views or v in views]
    if not jobs:raise ValueError("No sheet views configured for fitting")
    with ProcessPoolExecutor(max_workers=min(len(jobs), int(os.environ.get("LOWPOLY_FIT_WORKERS", "4")), os.cpu_count() or 4)) as ex:
        for st, view, sc, v in ex.map(_fit_one, jobs):
            print("%-14s %-10s %s  cam %s" % (st, view, " ".join("%s %.3f" % kv for kv in sc.items()), v[:7]),
                  flush=True)


def cmd_page(folder):
    from lowpoly_workshop.kit.page import build_page
    build_page(folder, HERE)


def cmd_package(folder):
    from lowpoly_workshop.distribution import package_asset
    package_asset(folder)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return
    if sys.argv[1] == "sheets":
        from lowpoly_workshop.kit import sheets
        sheets.main(sys.argv[2:])
        return
    folder, cmd, args = os.path.abspath(sys.argv[1]), sys.argv[2], sys.argv[3:]
    if cmd == "fit":
        cmd_fit(folder, args)
    elif cmd == "refine":
        from lowpoly_workshop.kit import refine
        sw = int(args[args.index("--sweeps") + 1]) if "--sweeps" in args else 4
        sets = args[args.index("--sets") + 1].split(",") if "--sets" in args else None
        specs = [x.split(":") for x in args if ":" in x]
        refine.run(folder, specs, sw, sets)
    elif cmd == "build":
        blender("build.py", folder, *args)
    elif cmd == "check":
        from lowpoly_workshop.kit import check
        sys.exit(0 if check.run(folder) else 1)
    elif cmd == "render":
        what = args or ["views"]
        blender("render.py", folder, *what)
    elif cmd == "compose":
        from lowpoly_workshop.kit import compose
        compose.run(folder)
    elif cmd == "page":
        cmd_page(folder)
    elif cmd == "package":
        cmd_package(folder)
    elif cmd == "all":
        blender("build.py", folder)
        from lowpoly_workshop.kit import check
        ok = check.run(folder)
        blender("render.py", folder, "views")
        blender("render.py", folder, "show")
        blender("review.py", folder)
        from lowpoly_workshop.kit import compose
        compose.run(folder)
        cmd_page(folder)
        cmd_package(folder)
        sys.exit(0 if ok else 1)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
