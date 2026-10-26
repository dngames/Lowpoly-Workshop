"""Sheet | model render | overlay | difference strips and silhouette scores for every rendered view.

Reads out/render/<set>/<view>.png (from blender/render.py), writes out/compare/<set>_<view>.jpg and
out/compare/scores.json: {set: {view: {"iou": .., "f4px": ..}}}. IoU is the overlap of the model's
silhouette with the drawing's; f4px is the share of outline pixels within 4 px of the other outline.
"""
import json
from pathlib import Path
import os

import numpy as np
from PIL import Image
from scipy import ndimage

from .asset import Asset


def fscore(a, b, tol):
    ea = a & ~ndimage.binary_erosion(a)
    eb = b & ~ndimage.binary_erosion(b)
    da = ndimage.distance_transform_edt(~ea)
    db = ndimage.distance_transform_edt(~eb)
    prec = (db[ea] <= tol).mean() if ea.any() else 0.0
    rec = (da[eb] <= tol).mean() if eb.any() else 0.0
    return 2 * prec * rec / (prec + rec + 1e-9)


def run(folder):
    a = Asset(folder)
    scores = {}
    for st in a.sets():
        for view in a.views(st):
            f = a.out("render", st, view + ".png")
            if not os.path.exists(f):
                continue
            crop = a.sheet(st, view)
            bgc = np.median(np.concatenate([crop[0], crop[-1], crop[:, 0], crop[:, -1]]), 0)
            fs = np.abs(crop.astype(float) - bgc).max(-1) > a.spec.get("sheet_bg_tol", 24)
            if a.spec.get("sheet_bg_mode", "border") != "border":
                from .raster import background_mask
                fs = ~background_mask(crop, a.spec.get("sheet_bg_tol",24), a.spec["sheet_bg_mode"])
            if a.spec.get("sheet_denoise", True):
                fs = ndimage.binary_opening(fs, iterations=1)
            rgba = np.asarray(Image.open(f).convert("RGBA")).astype(float)
            al = rgba[..., 3:] / 255.0
            comp = (rgba[..., :3] * al + bgc * (1 - al)).astype(np.uint8)
            m = rgba[..., 3] > 127
            iou = (m & fs).sum() / max((m | fs).sum(), 1)
            scores.setdefault(st, {})[view] = {"iou": round(float(iou), 4), "f4px": round(float(fscore(m, fs, 4)), 4)}
            diff = np.full(crop.shape, 238, np.uint8)
            diff[m & fs], diff[m & ~fs], diff[~m & fs] = (158, 156, 166), (214, 64, 52), (44, 104, 214)
            over = (crop.astype(float) * 0.5 + comp.astype(float) * 0.5).astype(np.uint8)
            Image.fromarray(np.concatenate([crop, comp, over, diff], 1)).save(
                a.out("compare", "%s_%s.jpg" % (st, view)), quality=90)
            print("%-14s %-10s IoU %.3f  edges within 4 px %.3f" % (st, view, iou, scores[st][view]["f4px"]))
    Path(a.out("compare","scores.json")).write_text(json.dumps(scores,indent=1))
    for st, row in scores.items():
        vals = [x["iou"] for x in row.values()]
        print("%-14s mean IoU %.3f over %d views" % (st, float(np.mean(vals)), len(vals)))
    return scores
