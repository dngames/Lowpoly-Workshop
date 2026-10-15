"""Compare every atlas cell's colour with the reference pixels it covers through the solved cameras.

Silhouette fitting cannot tell a teal jacket from a green one. This samples each fitted view: a
reference pixel counts towards a cell only where it can be trusted, so drawing/model misalignment
does not mix neighbouring colours into the answer:

- the cell is the visible surface there (z-buffer winner);
- the surface faces the camera (weight fades from facing_low to facing_high);
- the pixel lies at least edge_px inside both silhouettes and away from every cell boundary;
- the reference pixel is foreground and, when the palette declares a line class, not ink-dark.

Colours are compared in CIE Lab. References are lit and the atlas is not: diffuse shading scales
linear light, so each reference pixel is first scaled to the atlas pixel's luminance, which leaves
only hue and saturation to compare (the a/b distance, which carries the verdict). Lightness is
reported relative to the median shift over all trusted pixels and judged leniently; with a single seen
cell it cannot be judged. A cell that no trusted pixel sees is reported as unseen, not as
matching. Results are advice for review: they never fail a build or a check.

Writes out/colour/colour.json, a trust map per view (white = used) and swatches.png
(model colour above reference colour, per cell).
"""
import json
import os

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

from . import raster as rs
from . import rig
from .camfit import ViewFit, make_cam

DEFAULTS = dict(facing_low=0.25, facing_high=0.6, edge_px=3, min_pixels=40, tolerance_ab=12.0, tolerance_l=25.0,
                ink_lum=40)


def linear(rgb):
    """sRGB 0..255 -> linear light 0..1."""
    c = np.asarray(rgb, float) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def luminance(lin):
    return lin @ np.array([0.2126729, 0.7151522, 0.0721750])


def linear_to_lab(lin):
    """(..., 3) linear sRGB -> CIE Lab (D65)."""
    xyz = np.asarray(lin, float) @ np.array([[0.4124564, 0.2126729, 0.0193339],
                                             [0.3575761, 0.7151522, 0.1191920],
                                             [0.1804375, 0.0721750, 0.9503041]])
    xyz = xyz / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 216 / 24389, np.cbrt(xyz), (24389 / 27 * xyz + 16) / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def srgb_to_lab(rgb):
    return linear_to_lab(linear(rgb))


def lab_to_hex(lab):
    L, a, b = lab
    fy = (L + 16) / 116
    f = np.array([fy + a / 500, fy, fy - b / 200])
    xyz = np.where(f ** 3 > 216 / 24389, f ** 3, (116 * f - 16) / (24389 / 27)) * np.array([0.95047, 1.0, 1.08883])
    lin = xyz @ np.array([[3.2404542, -0.9692660, 0.0556434],
                          [-1.5371385, 1.8760108, -0.2040259],
                          [-0.4985314, 0.0415560, 1.0572252]])
    lin = np.clip(lin, 0, 1)
    c = np.where(lin <= 0.0031308, 12.92 * lin, 1.055 * lin ** (1 / 2.4) - 0.055)
    return "#%02x%02x%02x" % tuple(int(round(x * 255)) for x in np.clip(c, 0, 1))


def weighted_median(values, weights):
    """Per-column weighted median of (n, k) values."""
    out = []
    for col in np.asarray(values, float).T:
        order = np.argsort(col)
        cw = np.cumsum(np.asarray(weights, float)[order])
        out.append(col[order][np.searchsorted(cw, cw[-1] / 2)])
    return np.array(out)


def smoothstep(x, lo, hi):
    t = np.clip((x - lo) / max(hi - lo, 1e-9), 0, 1)
    return t * t * (3 - 2 * t)


def view_samples(vf, v, settings):
    """Trusted (cell, model rgb, reference rgb, weight) samples of one fitted view, and its trust map."""
    H, W = vf.cls.shape
    nodes, pose = vf.a.scene(vf.set, vf.view, v[7:])
    T, C = rig.posed_triangles(nodes, pose)
    cam = make_cam(v, vf.target)
    n = len(T)
    # a triangle-id buffer: every triangle is its own "cell" for the rasterizer
    ids = list(range(n))
    _, tid, zbuf = rs.render(T, ids, cam, W, H, shade=False, palette={i: (0, 0, 0) for i in ids},
                             classes={i: i + 1 for i in ids})
    tid = tid - 1
    albedo = vf.textured(v, shade=False)[0]
    normal = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    normal /= np.linalg.norm(normal, axis=1, keepdims=True) + 1e-12
    if cam.ortho:
        to_cam = np.broadcast_to(-cam.fwd, normal.shape)
    else:
        to_cam = cam.eye - T.mean(1)
        to_cam = to_cam / (np.linalg.norm(to_cam, axis=1, keepdims=True) + 1e-12)
    facing = np.abs((normal * to_cam).sum(1))  # faces carry no reliable outward flag; thin parts are two-sided
    names = sorted({c for c in C}, key=str)
    index = {c: i for i, c in enumerate(names)}
    cell_of = np.array([index[c] for c in C]) if n else np.zeros(0, int)
    seen = tid >= 0
    cellmap = np.where(seen, cell_of[np.maximum(tid, 0)] if n else -1, -1)
    boundary = np.zeros((H, W), bool)
    boundary[:, 1:] |= cellmap[:, 1:] != cellmap[:, :-1]
    boundary[:, :-1] |= cellmap[:, 1:] != cellmap[:, :-1]
    boundary[1:] |= cellmap[1:] != cellmap[:-1]
    boundary[:-1] |= cellmap[1:] != cellmap[:-1]
    edge = settings["edge_px"]
    away = ndimage.distance_transform_edt(~boundary) > edge
    _, line = vf.a.classes(vf.set)
    ref_fg = vf.cls > 0
    if line is not None:
        # the same darkness the fitter calls ink; dark parts of the line class's own colours still count
        ref_fg &= vf.img.mean(-1) >= settings["ink_lum"]
    inside_ref = ndimage.distance_transform_edt(ref_fg) > edge
    weight = np.zeros((H, W))
    ok = seen & away & inside_ref
    weight[ok] = smoothstep(facing[tid[ok]], settings["facing_low"], settings["facing_high"])
    keep = weight > 0
    return dict(cells=[names[i] for i in cellmap[keep]], model=albedo[keep], reference=vf.img[keep].astype(float),
                weight=weight[keep], trust=weight)


def judge(model_lab, ref_lab, chroma_lab, shift_l, settings):
    """chroma_lab: the reference brought to the model's luminance (shading removed)."""
    d_ab = float(np.linalg.norm(chroma_lab[1:] - model_lab[1:]))
    d_l = float(ref_lab[0] - model_lab[0] - shift_l)
    ok = d_ab <= settings["tolerance_ab"] and abs(d_l) <= settings["tolerance_l"]
    return d_ab, d_l, ok


def run(folder, sets=None, **overrides):
    from .asset import Asset
    a = Asset(folder)
    settings = {**DEFAULTS, **a.spec.get("colour_match", {}), **{k: v for k, v in overrides.items() if v is not None}}
    pool, views = {}, {}
    for st in (sets or list(a.sets())):
        for view in a.views(st):
            cam = a.cam(st, view)
            if not cam:
                print("SKIP  %s/%s: no solved camera (run fit first)" % (st, view))
                continue
            vf = ViewFit(a, st, view)
            s = view_samples(vf, np.asarray(cam["cam"], float), settings)
            trust = a.out("colour", "%s_%s_trust.png" % (st, view))
            Image.fromarray((s["trust"] * 255).astype(np.uint8)).save(trust)
            counts = {}
            for c, m, r, w in zip(s["cells"], s["model"], s["reference"], s["weight"]):
                p = pool.setdefault(c, ([], [], []))
                p[0].append(m), p[1].append(r), p[2].append(w)
                counts[str(c)] = counts.get(str(c), 0) + 1
            views["%s/%s" % (st, view)] = dict(trust_map=os.path.relpath(trust, folder).replace(os.sep, "/"),
                                               trusted_pixels=counts)
    all_cells = {}
    for nd in a.build().values():
        atl = nd.get("atlas") or a.gen.ATLAS
        for c, (hexc, _, decal) in atl.cells.items():
            all_cells.setdefault(c, (hexc, decal))
    stats = {}
    for c, (m, r, w) in pool.items():
        if len(w) < settings["min_pixels"]:
            continue
        w = np.asarray(w)
        ml, rl = linear(np.asarray(m)), linear(np.asarray(r))
        ym, yr = luminance(ml), luminance(rl)
        # diffuse shading scales linear light; at the atlas's luminance only hue and saturation differ
        shaded = np.clip(rl * (ym / np.maximum(yr, 1e-4))[:, None], 0, 1)
        lit = yr > 1e-3
        if lit.sum() < settings["min_pixels"]:
            continue
        stats[c] = (weighted_median(linear_to_lab(ml), w), weighted_median(srgb_to_lab(np.asarray(r)), w),
                    weighted_median(linear_to_lab(shaded[lit]), w[lit]), float(w.sum()))
    # the lighting shift follows the surface area actually seen, so many tiny cells cannot outvote a large one
    shift_l = float(weighted_median([[rl[0] - ml[0]] for ml, rl, _, _ in stats.values()],
                                    [n for *_, n in stats.values()])[0]) if stats else 0.0
    cells = {}
    for c in sorted(all_cells, key=str):
        hexc, decal = all_cells[c]
        row = dict(palette=hexc, decal=bool(decal), pixels=len(pool.get(c, ([], [], []))[2]))
        if c not in stats:
            row["status"] = "unseen"
        else:
            ml, rl, chroma, _ = stats[c]
            d_ab, d_l, ok = judge(ml, rl, chroma, shift_l, settings)
            row.update(model=lab_to_hex(ml), reference=lab_to_hex(rl), d_ab=round(d_ab, 1), d_l=round(d_l, 1),
                       status="ok" if ok else "review")
            if not ok and not decal:
                # the reference's hue and saturation at the atlas lightness, corrected by the relative shift
                row["suggest"] = lab_to_hex(np.array([ml[0] + d_l, chroma[1], chroma[2]]))
        cells[str(c)] = row
    report = dict(settings=settings, lightness_shift=round(shift_l, 1), views=views, cells=cells)
    out = a.out("colour", "colour.json")
    with open(out, "w") as stream:
        json.dump(report, stream, indent=1)
    swatches(cells, a.out("colour", "swatches.png"))
    print("Lightness of the references against the atlas: %+.1f L (lighting; removed before judging)" % shift_l)
    for c, row in cells.items():
        if row["status"] == "unseen":
            print("UNSEEN  %-16s %s" % (c, row["palette"]))
        else:
            print("%-7s %-16s atlas %s  reference %s  hue/sat %.1f  lightness %+.1f%s  (%d px)" % (
                row["status"].upper(), c, row["model"], row["reference"], row["d_ab"], row["d_l"],
                ("  try " + row["suggest"]) if row.get("suggest") else "", row["pixels"]))
    return report


def swatches(cells, path, size=48):
    rows = list(cells.items())
    img = Image.new("RGB", (max(1, len(rows)) * size, size * 2 + 14), (236, 236, 236))
    draw = ImageDraw.Draw(img)
    for i, (name, row) in enumerate(rows):
        x = i * size
        draw.rectangle([x, 0, x + size - 2, size - 1], fill=row.get("model", row["palette"]))
        if row.get("reference"):
            draw.rectangle([x, size, x + size - 2, 2 * size - 1], fill=row["reference"])
        mark = {"ok": (60, 140, 80), "review": (210, 60, 50)}.get(row["status"], (150, 150, 150))
        draw.rectangle([x, 2 * size + 2, x + size - 2, 2 * size + 12], fill=mark)
    img.save(path)
