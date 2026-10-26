"""Review shots with one colour per piece (a connected run of one node's triangles): a detached
part, a patch lying on a face or a piece buried in another shows at a glance where the atlas
colours hide it. Front, side, back three-quarter and top, orthographic, side by side; z-fighting
found by kit/surfaces.py is ringed in magenta. No Blender: kit/raster.py draws them.
"""
import colorsys
import os

import numpy as np
from PIL import Image, ImageDraw

from . import glb as G
from . import raster as R
from . import surfaces as S

VIEWS = [(0, 0), (-90, 0), (145, 25), (0, 89)]
SIZE = 320


def piece_ids(tris, names):
    """Per triangle: its piece (corners shared within one node, welded at 0.1 mm)."""
    n = len(tris)
    up = list(range(n))

    def find(i):
        while up[i] != i:
            up[i] = up[up[i]]
            i = up[i]
        return i
    first = {}
    keys = np.round(np.asarray(tris) / 1e-4).astype(np.int64)
    for t in range(n):
        for k in range(3):
            key = (names[t],) + tuple(keys[t, k])
            if key in first:
                a, b = find(first[key]), find(t)
                if a != b:
                    up[max(a, b)] = min(a, b)
            else:
                first[key] = t
    roots = {}
    return [roots.setdefault(find(t), len(roots)) for t in range(n)]


def colour(i):
    r, g, b = colorsys.hls_to_rgb((i * 0.381966) % 1.0, 0.45 if i % 2 else 0.62, 0.75)
    return np.array([r, g, b]) * 255


def shot(tris, names, marks=()):
    """The four views as one PIL image."""
    tris = np.asarray(tris, float)
    ids = piece_ids(tris, names)
    palette = {i: colour(i) for i in set(ids)}
    lo, hi = tris.reshape(-1, 3).min(0), tris.reshape(-1, 3).max(0)
    centre, radius = (lo + hi) / 2, max(1e-6, float(np.linalg.norm(hi - lo)) / 2)
    out = Image.new("RGB", (SIZE * len(VIEWS), SIZE), "white")
    for v, (az, el) in enumerate(VIEWS):
        cam = R.Camera(az, el, 0, radius * 4, SIZE * 0.46 * 4, SIZE / 2, SIZE / 2, target=centre, ortho=True)
        rgb, cmap, _ = R.render(tris, ids, cam, SIZE, SIZE, palette=palette, classes={"_default": 1})
        img = np.where(cmap[..., None] > 0, rgb, 255).clip(0, 255).astype(np.uint8)
        tile = Image.fromarray(img)
        d = ImageDraw.Draw(tile)
        for p in marks:
            uv, _ = cam.project(np.asarray(p, float)[None])
            x, y = float(uv[0][0]), float(uv[0][1])
            d.ellipse([x - 10, y - 10, x + 10, y + 10], outline=(230, 0, 200), width=2)
        out.paste(tile, (v * SIZE, 0))
    return out


def run(asset, eps_view=60):
    """out/pieces/<file>.png for every output of the asset."""
    folder = asset.out("pieces")
    os.makedirs(folder, exist_ok=True)
    written = []
    for o in asset.outputs():
        path = asset.path(o["file"])
        if not os.path.exists(path):
            continue
        g = G.Glb(path)
        geo, _ = g.posed(g.sample())
        tris, names, uvs = S.soup(g, geo)
        if not len(tris):
            continue
        view = float(o.get("contract", {}).get("view_m", eps_view))
        imgs = g.images()
        atlas = np.asarray(imgs[0].convert("RGB")) if imgs else None
        found = S.overlaps(tris, names, uvs, eps=S.eps_for(view), tex=atlas)
        target = os.path.join(folder, os.path.splitext(os.path.basename(path))[0] + ".png")
        shot(tris, names, [e[4] for e in found["zfight"]]).save(target)
        written.append(target)
        print("SHOT", target, "%d pieces" % (max(piece_ids(tris, names)) + 1))
    return written
