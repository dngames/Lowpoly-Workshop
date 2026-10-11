"""Measure reference sheets: what you need before writing a generator.

CLI (python lowpoly.py sheets <tool> ...):
  cells   <img> [--rows 2 --cols 4 --label-h 136]    bounding box of the drawing in every grid cell
  grid    <img> <out.png> x0 y0 x1 y1 [scale step]    zoomed crop with a labelled pixel grid to read coordinates
  runs    <img> x0 y0 x1 y1 step [col] --pal pal.json  per-row (or column) class letters: where each colour runs
  palette <img> x0 y0 x1 y1 [k]                       k-means colour clusters (hex + pixel count)
  circle  <img> cx cy r_max a0 a1                     fit a circle to the outer outline between angles (wheels)
Library: silhouette(), Envelope (visual hull from a front and a side silhouette), fib_sphere(),
outline_spikes(), quantize() (flat-colour decal from a crop).
"""
import json
import math
import sys

import numpy as np
from PIL import Image, ImageDraw


def load(path):
    return np.asarray(Image.open(path).convert("RGB"))


def background(img):
    im = img.astype(float)
    return np.median(np.concatenate([im[0], im[-1], im[:, 0], im[:, -1]]), 0)


def fg_mask(img, thr=26, bg=None):
    bg = background(img) if bg is None else np.asarray(bg, float)
    return np.abs(img.astype(float) - bg).max(-1) > thr


def cells(img, rows, cols, label_h=0):
    """Bounding box of the foreground in each grid cell (label strip at the bottom of a cell excluded)."""
    H, W = img.shape[:2]
    ch, cw = H // rows, W // cols
    fg = fg_mask(img)
    out = {}
    for r in range(rows):
        for c in range(cols):
            sub = fg[r * ch:r * ch + ch - label_h, c * cw:c * cw + cw]
            ys, xs = np.nonzero(sub)
            if len(xs):
                out[(r, c)] = (xs.min() + c * cw, ys.min() + r * ch, xs.max() + c * cw, ys.max() + r * ch)
    return out, (cw, ch)


def grid_image(img, out, x0, y0, x1, y1, scale=2, step=20):
    im = Image.fromarray(img).crop((x0, y0, x1, y1))
    im = im.resize(((x1 - x0) * scale, (y1 - y0) * scale), Image.NEAREST)
    d = ImageDraw.Draw(im)
    for x in range((x0 // step + 1) * step, x1, step):
        X = (x - x0) * scale
        d.line([(X, 0), (X, im.height)], fill=(255, 0, 255) if x % (step * 5) == 0 else (0, 160, 255))
        d.text((X + 2, 2), str(x), fill=(200, 0, 0))
    for y in range((y0 // step + 1) * step, y1, step):
        Y = (y - y0) * scale
        d.line([(0, Y), (im.width, Y)], fill=(255, 0, 255) if y % (step * 5) == 0 else (0, 160, 255))
        d.text((2, Y + 2), str(y), fill=(200, 0, 0))
    im.save(out)


def classify_letters(img, pal):
    """pal: {letter: [hex, ...]}; '.' background, '#' ink line."""
    im = img.astype(float)
    bg = background(img)
    letters, cents = [], []
    for k, hs in pal.items():
        for h in hs:
            letters.append(k)
            cents.append([int(h.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)])
    cents = np.array(cents, float)
    d = ((im[..., None, :] - cents[None, None]) ** 2).sum(-1)
    lab = np.array(letters)[d.argmin(-1)]
    lab[im.mean(-1) < 42] = "#"
    lab[np.abs(im - bg).max(-1) < 22] = "."
    return lab


def palette(img, k=12, seed=1):
    from scipy.cluster.vq import kmeans2
    px = img.reshape(-1, 3).astype(float)
    fg = np.abs(px - background(img)).max(1) > 26
    px = px[fg][::3]
    cent, lab = kmeans2(px, k, minit="++", seed=seed)
    cnt = np.bincount(lab, minlength=k)
    return [("#%02x%02x%02x" % tuple(cent[i].astype(int)), int(cnt[i])) for i in np.argsort(-cnt)]


def fit_circle(pts):
    x, y = pts[:, 0].astype(float), pts[:, 1].astype(float)
    A = np.c_[2 * x, 2 * y, np.ones_like(x)]
    c, *_ = np.linalg.lstsq(A, x * x + y * y, rcond=None)
    R = math.sqrt(c[2] + c[0] ** 2 + c[1] ** 2)
    return c[0], c[1], R, float(np.abs(np.hypot(x - c[0], y - c[1]) - R).max())


def circle(img, cx, cy, rmax, a0, a1):
    """Outer outline points along rays from a rough centre, then a least-squares circle (x, y, r, max err)."""
    fg = fg_mask(img)
    pts = []
    for a in np.deg2rad(np.arange(a0, a1, 2.0)):
        for r in np.arange(rmax, 5, -0.5):
            x, y = int(round(cx + r * math.cos(a))), int(round(cy + r * math.sin(a)))
            if 0 <= y < fg.shape[0] and 0 <= x < fg.shape[1] and fg[y, x]:
                pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
                break
    return fit_circle(np.array(pts))


def silhouette(img, box, y_max=None):
    """Largest connected foreground blob inside box (x0, y0, x1, y1), holes kept open to the outside."""
    import cv2
    x0, y0, x1, y1 = box
    m = np.zeros(img.shape[:2], np.uint8)
    sub = fg_mask(img[y0:y1, x0:x1])
    if y_max is not None:
        sub[y_max - y0:] = False
    m[y0:y1, x0:x1] = sub
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m)
    keep = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
    return lab == keep


class Envelope:
    """Visual hull of a front and a side silhouette, rounded per row by a superellipse.

    to_front(x, y) / to_side(x, y) map sheet pixels to (X, Y) and (Z, Y) in metres."""

    def __init__(self, front, side, to_front, to_side, from_front, from_side, y_lo=-1e9, n=2.6):
        self.front, self.side, self.y_lo, self.n = front, side, y_lo, n
        self.to_front, self.to_side, self.from_front, self.from_side = to_front, to_side, from_front, from_side
        self.fx0, self.fx1 = self._extents(front, to_front)
        self.sz0, self.sz1 = self._extents(side, to_side)

    @staticmethod
    def _extents(mask, to):
        lo = np.zeros(mask.shape[0])
        hi = np.zeros(mask.shape[0])
        for y in range(mask.shape[0]):
            xs = np.nonzero(mask[y])[0]
            if len(xs):
                lo[y], hi[y] = to(xs.min(), y)[0], to(xs.max(), y)[0]
        return lo, hi

    def inside(self, P):
        X, Y, Z = P[..., 0], P[..., 1], P[..., 2]
        xf, yf = self.from_front(X, Y)
        zs, ys = self.from_side(Z, Y)
        yf = np.clip(np.round(yf).astype(int), 0, self.front.shape[0] - 1)
        ys = np.clip(np.round(ys).astype(int), 0, self.side.shape[0] - 1)
        xf = np.clip(np.round(xf).astype(int), 0, self.front.shape[1] - 1)
        zs = np.clip(np.round(zs).astype(int), 0, self.side.shape[1] - 1)
        ok = self.front[yf, xf] & self.side[ys, zs] & (Y >= self.y_lo)
        x0, x1, z0, z1 = self.fx0[yf], self.fx1[yf], self.sz0[ys], self.sz1[ys]
        a, b = np.maximum((x1 - x0) / 2, 1e-3), np.maximum((z1 - z0) / 2, 1e-3)
        u = np.abs((X - (x0 + x1) / 2) / a) ** self.n + np.abs((Z - (z0 + z1) / 2) / b) ** self.n
        return ok & (u <= 1.0)

    def radius(self, c, D, r_max=0.8, steps=160):
        """Distance from centre c to the hull surface along each unit direction in D (N, 3)."""
        t = np.linspace(0, r_max, steps)
        P = c[None, None] + D[:, None] * t[None, :, None]
        ins = self.inside(P)
        last = np.where(ins.any(1), steps - 1 - np.argmax(ins[:, ::-1], 1), 0)
        return t[last]


def fib_sphere(n):
    i = np.arange(n) + 0.5
    phi = np.arccos(1 - 2 * i / n)
    th = math.pi * (1 + 5 ** 0.5) * i
    return np.stack([np.cos(th) * np.sin(phi), np.cos(phi), np.sin(th) * np.sin(phi)], -1)


def outline_spikes(mask, opened, min_out=6, eps=3.5, y_max=None):
    """Convex outline vertices standing at least min_out px outside a morphologically opened mask
    (hair spikes, fins, horns). Returns [(x, y, distance_px)]."""
    import cv2
    cs, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cnt = max(cs, key=cv2.contourArea)
    poly = cv2.approxPolyDP(cnt, eps, True)[:, 0, :]
    dist = cv2.distanceTransform((~opened.astype(bool)).astype(np.uint8), cv2.DIST_L2, 5)
    out = []
    for i, (x, y) in enumerate(poly):
        if (y_max is not None and y > y_max) or dist[y, x] < min_out:
            continue
        a, b = poly[i - 1], poly[(i + 1) % len(poly)]
        if np.cross(np.r_[a - [x, y]], np.r_[b - [x, y]]) < 0:
            continue
        out.append((int(x), int(y), float(dist[y, x])))
    return out


def quantize(crop, src_to_name, name_to_hex, rules=None, median=5):
    """Flat-colour decal: nearest source colour -> named class -> output colour, cleaned by rules.

    rules(cls, crop, ys, xs) may rewrite the class array (e.g. keep dark pixels only inside eye boxes)."""
    import cv2
    keys = list(src_to_name)
    src = np.array([[int(h.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)] for h in keys], float)
    im = crop.astype(float)
    lab = ((im[..., None, :] - src[None, None]) ** 2).sum(-1).argmin(-1)
    cls = np.array([src_to_name[k] for k in keys])[lab]
    ys, xs = np.mgrid[0:crop.shape[0], 0:crop.shape[1]]
    if rules:
        cls = rules(cls, crop, ys, xs)
    order = list(name_to_hex)
    idx = np.array([order.index(c) for c in cls.ravel()], np.uint8).reshape(cls.shape)
    if median:
        idx = cv2.medianBlur(idx, median)
    rgb = np.array([[int(name_to_hex[o].lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)] for o in order], np.uint8)
    return rgb[idx]


def main(argv):
    tool = argv[0]
    img = load(argv[1])
    if tool == "cells":
        rows = int(argv[argv.index("--rows") + 1]) if "--rows" in argv else 2
        cols = int(argv[argv.index("--cols") + 1]) if "--cols" in argv else 4
        lab = int(argv[argv.index("--label-h") + 1]) if "--label-h" in argv else 0
        boxes, (cw, ch) = cells(img, rows, cols, lab)
        print("image %dx%d, cell %dx%d" % (img.shape[1], img.shape[0], cw, ch))
        for (r, c), (x0, y0, x1, y1) in sorted(boxes.items()):
            print("  r%d c%d  x %4d-%4d  y %4d-%4d  (w %d h %d)" % (r, c, x0, x1, y0, y1, x1 - x0, y1 - y0))
    elif tool == "grid":
        x0, y0, x1, y1 = map(int, argv[3:7])
        sc = int(argv[7]) if len(argv) > 7 else 2
        st = int(argv[8]) if len(argv) > 8 else 20
        grid_image(img, argv[2], x0, y0, x1, y1, sc, st)
        print("wrote", argv[2])
    elif tool == "runs":
        x0, y0, x1, y1, st = map(int, argv[2:7])
        axis = "col" if "col" in argv[7:] else "row"
        pal = json.load(open(argv[argv.index("--pal") + 1]))
        lab = classify_letters(img[y0:y1, x0:x1], pal)
        if axis == "row":
            for y in range(0, y1 - y0, st):
                print("%4d %s" % (y + y0, "".join(lab[y, ::2])))
        else:
            for x in range(0, x1 - x0, st):
                print("%4d %s" % (x + x0, "".join(lab[::2, x])))
    elif tool == "palette":
        x0, y0, x1, y1 = map(int, argv[2:6])
        k = int(argv[6]) if len(argv) > 6 else 12
        for h, n in palette(img[y0:y1, x0:x1], k):
            print("%7d  %s" % (n, h))
    elif tool == "circle":
        cx, cy, rmax, a0, a1 = map(float, argv[2:7])
        print("centre (%.2f, %.2f) radius %.2f max error %.2f px" % circle(img, cx, cy, rmax, a0, a1))
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
