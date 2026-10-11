"""Reproduce a flat-fringe repair using original procedural geometry and actual GLBs."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lowpoly_workshop.templates import create
from lowpoly_workshop import __version__
from PIL import Image, ImageDraw, ImageFont


def run(destination):
    root = Path(destination).resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError("Demo destination must be empty")
    root.mkdir(parents=True, exist_ok=True)
    views = ["front", "side", "below"]
    evidence = {"workshop_version": __version__, "source": "original-procedural-example",
                "purpose": "synthetic repair illustration; not a competitive benchmark",
                "visual_approval": "pending", "variants": {}}
    panels = []
    for variant in ("before", "after"):
        folder = create(root / variant, "wearable", "Fringe " + variant)
        source = folder / "gen.py"
        code = source.read_text()
        if variant == "before":
            old = "hair=Mesh();wrapped_patch(hair,rows,directions,t,'dark',offset=.018,thickness=.012)"
            assert old in code
            code = code.replace(old, "hair=box((0,.55,.324),(.295,.07,.012),'dark')")
            source.write_text(code, encoding="utf-8")
        spec_path = folder / "asset.json"
        spec = json.loads(spec_path.read_text())
        spec["review"] = {"size": 384, "views": [], "modes": ["textured"], "regions": [
            {"name": "comparison", "bounds": [[-.4,-.1,-.4],[.4,.9,.4]], "views": views}]}
        spec_path.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
        for command in ("build", "check", "review"):
            subprocess.run([sys.executable, "-m", "lowpoly_workshop", str(folder), command], check=True)
        model = folder / "out/model.glb"
        index = folder / "out/review/index.json"
        shots = json.loads(index.read_text())["shots"]
        model_hash = hashlib.sha256(model.read_bytes()).hexdigest()
        assert all(shot["sha256"] == model_hash for shot in shots)
        evidence["variants"][variant] = {
            "generator": source.relative_to(root).as_posix(),
            "generator_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "glb": model.relative_to(root).as_posix(), "glb_sha256": model_hash,
            "review_index": index.relative_to(root).as_posix(), "checks_passed": True,
            "shots": shots}
        row = []
        for view in views:
            shot = next(s for s in shots if s["view"] == view and s["region"] == "comparison")
            with Image.open(folder / shot["file"]) as im:
                row.append(im.convert("RGB"))
        panels.append(row)
    margin, header, size = 12, 48, 384
    canvas = Image.new("RGB", (3*size + 4*margin, 2*(size+header) + 3*margin), "#202936")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default(size=18)
    for row, (label, images) in enumerate(zip(("BEFORE: flat slab", "AFTER: wrapped patch"), panels)):
        y = margin + row*(size+header+margin)
        for col, (view, im) in enumerate(zip(views, images)):
            x = margin + col*(size+margin)
            draw.text((x, y+10), label + " / " + view, fill="white", font=font)
            canvas.paste(im, (x, y+header))
    canvas.save(root / "comparison.png")
    evidence["comparison_sha256"] = hashlib.sha256((root / "comparison.png").read_bytes()).hexdigest()
    (root / "evidence.json").write_text(json.dumps(evidence, indent=2)+"\n", encoding="utf-8")
    print("DEMO", root / "comparison.png")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination")
    run(parser.parse_args().destination)
