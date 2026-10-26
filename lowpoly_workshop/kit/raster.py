"""Tiny z-buffer rasterizer, camera model and silhouette scores used to fit models to sheet views.

render() needs a palette (cell -> rgb) and a class map (cell -> int class id; 0 is background).
Optional per-triangle UVs plus a texture sample the atlas instead of flat cell colours.
"""
import math

import numpy as np


def hex2rgb(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], float)


class Camera:
    """az/el in degrees; az=0 looks at the bike's front, az=-90 at its right (drive) side."""

    def __init__(self, az, el, roll, dist, f, cx, cy, target=(0.0, 0.5, 0.05), ortho=False):
        self.az, self.el, self.roll, self.dist, self.f, self.cx, self.cy = az, el, roll, dist, f, cx, cy
        self.target = np.asarray(target, float)
        self.ortho = ortho
        a, e, r = map(math.radians, (az, el, roll))
        d = np.array([math.cos(e) * math.sin(a), math.sin(e), math.cos(e) * math.cos(a)])
        right = np.array([math.cos(a), 0.0, -math.sin(a)])
        up = np.array([-math.sin(e) * math.sin(a), math.cos(e), -math.sin(e) * math.cos(a)])
        cr, sr = math.cos(r), math.sin(r)
        self.right = cr * right + sr * up
        self.up = -sr * right + cr * up
        self.fwd = -d
        self.eye = self.target + d * dist

    def vec(self):
        return [self.az, self.el, self.roll, self.dist, self.f, self.cx, self.cy]

    def project(self, P):
        q = P - self.eye
        x, y, z = q @ self.right, q @ self.up, q @ self.fwd
        if self.ortho:
            s = self.f / self.dist
            return np.stack([self.cx + s * x, self.cy - s * y], -1), z
        return np.stack([self.cx + self.f * x / z, self.cy - self.f * y / z], -1), z


def render(tris, cells, cam, W, H, shade=True, light=(-0.4, 0.75, 0.55), palette=None, classes=None,
           uvs=None, tex=None):
    """Returns rgb (H,W,3) float, class map (H,W) int, depth.

    palette maps cell -> rgb and classes maps cell -> class id (defaults: the bike's cells)."""
    T = len(tris)
    uv, z = cam.project(tris.reshape(-1, 3))
    uv = uv.reshape(T, 3, 2)
    z = z.reshape(T, 3)
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    L = np.asarray(light, float)
    L /= np.linalg.norm(L)
    # light rides with the camera so every view is lit from its upper left
    Lw = L[0] * cam.right + L[1] * cam.up - L[2] * cam.fwd
    view = -cam.fwd
    sgn = np.sign(n @ view)
    sgn[sgn == 0] = 1
    lam = np.clip((n * sgn[:, None]) @ Lw, 0, 1)
    k = 0.62 + 0.38 * lam if shade else np.ones(T)
    col = np.array([palette[c] for c in cells]) * k[:, None]
    default = classes.get("_default", 1)
    cls = np.array([classes.get(c, default) for c in cells])
    zbuf = np.full((H, W), np.inf)
    rgb = np.zeros((H, W, 3))
    cmap = np.zeros((H, W), int)
    for t in range(T):
        if np.any(z[t] <= 1e-4):
            continue
        p = uv[t]
        x0 = max(int(math.floor(p[:, 0].min())), 0)
        x1 = min(int(math.ceil(p[:, 0].max())), W - 1)
        y0 = max(int(math.floor(p[:, 1].min())), 0)
        y1 = min(int(math.ceil(p[:, 1].max())), H - 1)
        if x1 < x0 or y1 < y0:
            continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        (ax, ay), (bx, by), (cx, cy) = p
        den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) < 1e-9:
            continue
        w0 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / den
        w1 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / den
        w2 = 1 - w0 - w1
        inside = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
        if not inside.any():
            continue
        zz = w0 * z[t, 0] + w1 * z[t, 1] + w2 * z[t, 2]
        sub = zbuf[y0:y1 + 1, x0:x1 + 1]
        upd = inside & (zz < sub)
        sub[upd] = zz[upd]
        if tex is not None and uvs is not None:
            th, tw = tex.shape[:2]
            uu = w0 * uvs[t, 0, 0] + w1 * uvs[t, 1, 0] + w2 * uvs[t, 2, 0]
            vv = w0 * uvs[t, 0, 1] + w1 * uvs[t, 1, 1] + w2 * uvs[t, 2, 1]
            tx = np.clip((uu * tw).astype(int), 0, tw - 1)
            ty = np.clip((vv * th).astype(int), 0, th - 1)
            rgb[y0:y1 + 1, x0:x1 + 1][upd] = tex[ty[upd], tx[upd]] * k[t]
        else:
            rgb[y0:y1 + 1, x0:x1 + 1][upd] = col[t]
        cmap[y0:y1 + 1, x0:x1 + 1][upd] = cls[t]
    return rgb, cmap, zbuf


def background_mask(img, tolerance=24, mode='border'):
    """Background mask; opt-in gradient mode fits the sheet's empty border strips.

    Turnaround sheets often use a grey studio gradient. A single median colour
    mistakes its darker corners for geometry, while raising the tolerance loses
    cream plaster. Fit a robust quadratic field without sampling the object.
    """
    im = img.astype(float)
    if mode == 'blue':
        # Opt-in for warm wood/neutral stone against a blue studio backdrop.
        # Blue-tinted floor shadows are background too. Do not use for assets
        # containing blue/teal parts: inspect the full-view masks first.
        return (im[...,2]-im[...,0]>12)&(im[...,1]-im[...,0]>6)
    border = np.concatenate([im[0], im[-1], im[:, 0], im[:, -1]])
    if mode == 'border':
        bg = np.median(border, 0)
    elif mode == 'gradient':
        h,w = im.shape[:2]
        if min(h,w)<32:raise ValueError('Gradient masking needs crops at least 32 pixels across')
        y,x = np.mgrid[-1:1:complex(h), -1:1:complex(w)]
        field = np.stack((np.ones_like(x),x,y,x*x,x*y,y*y),-1)
        # Inset past panel rules; robust rejection excludes props near an edge.
        iy,ix = np.indices((h,w))
        edge = np.minimum.reduce([iy,ix,h-1-iy,w-1-ix])
        sample = (edge>=6)&(edge<14)
        a,b = field[sample][::2],im[sample][::2]
        keep = np.ones(len(a),bool)
        for _ in range(4):
            coeff = np.linalg.lstsq(a[keep],b[keep],rcond=None)[0]
            residual = np.abs(a@coeff-b).max(-1)
            keep = residual <= max(6.,float(np.quantile(residual,.85)))
        bg = field@coeff
    else:
        raise ValueError(f'unknown sheet background mode: {mode}')
    return np.abs(im-bg).max(-1)<tolerance



def classify(img, classes, bg_tol=24, line_class=None, line_lum=40, bg_mode="border"):
    """Sheet pixels -> class ids by nearest palette colour; 0 = background (taken from the image border).

    classes: {class id: [hex, ...]}; line_class: class for dark ink pixels (None keeps nearest colour)."""
    im = img.astype(float)
    bgm = background_mask(img, bg_tol, bg_mode)
    cents, owner = [], []
    for k, hs in classes.items():
        for h in hs:
            cents.append(hex2rgb(h))
            owner.append(int(k))
    cents, owner = np.array(cents), np.array(owner)
    cls = np.zeros(im.shape[:2], int)
    for y0 in range(0, im.shape[0], 128):        # chunked to bound memory on big crops
        blk = im[y0:y0 + 128]
        d = ((blk[..., None, :] - cents[None, None]) ** 2).sum(-1)
        cls[y0:y0 + 128] = owner[d.argmin(-1)]
    if line_class is not None:
        cls[im.mean(-1) < line_lum] = line_class
    cls[bgm] = 0
    return cls


def iou(a, b):
    u = (a | b).sum()
    return (a & b).sum() / u if u else 1.0


def scores(cm, cs, outline=1, names=None):
    """IoU of the silhouettes (model dilated by the sheet's ink outline) and of every class present."""
    from scipy import ndimage
    fm, fs = cm > 0, cs > 0
    if outline:
        fm = ndimage.binary_dilation(fm, iterations=outline)
    out = {"fg": iou(fm, fs)}
    for k in sorted(set(np.unique(cs)) | set(np.unique(cm))):
        if k <= 0 or ((cs == k).sum() < 50 and (cm == k).sum() < 50):
            continue
        out[(names or {}).get(k, "c%d" % k)] = iou(cm == k, cs == k)
    return out


def objective(s):
    """Silhouette plus the mean class IoU: what camera and pose fits maximise."""
    parts = [v for k, v in s.items() if k != "fg"]
    return s["fg"] + (float(np.mean(parts)) if parts else 0.0)
