"""Assemble Pixal3D-RunPack.zip: .gguf stored uncompressed, everything else deflated.

Usage: python build_zip.py <pack_root> <output_zip>
Skips machine-generated folders (private venv, previous job runs, logs).
"""
import sys
import zipfile
from pathlib import Path

root = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2]).resolve()
skip_dirs = {".venv", "job"}
skip_names = {"run.log"}

if out.exists():
    out.unlink()

count = 0
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in skip_dirs for part in rel.parts):
            continue
        if path.name in skip_names:
            continue
        arc = Path(out.stem) / rel
        if path.suffix.lower() == ".gguf":
            z.write(path, arc, compress_type=zipfile.ZIP_STORED)
        else:
            z.write(path, arc)
        count += 1
        if count % 25 == 0:
            print(f"{count} files ...", flush=True)

size_gb = out.stat().st_size / 1e9
print(f"ZIP DONE: {count} files, {size_gb:.2f} GB -> {out}")
