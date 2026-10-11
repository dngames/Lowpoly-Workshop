"""Solve one camera (plus optional pose parameters) per sheet view and score the fit.

The camera vector is [az, el, roll, dist, px_per_m, cx, cy] followed by the asset's extra parameters
(crank angle, steering, limb angles ... as defined by gen.fit_extra). az = 0 looks at the asset's
front, az = -90 at its right side, el = 90 from above. A large dist (40+) is near-orthographic,
which is what most turnaround sheets are.
"""
import json
import os

import numpy as np
from PIL import Image
from scipy.optimize import minimize

from . import raster as rs
from . import rig


def make_cam(v, target, ds=1.0):
    az, el, roll, dist, s, cx, cy = v[:7]
    return rs.Camera(az, el, roll, dist, s * dist * ds, cx * ds, cy * ds, target=target)


class ViewFit:
    """Everything needed to evaluate one sheet view against the model."""

    def __init__(self, asset, set_name, view):
        self.a, self.set, self.view = asset, set_name, view
        self.img = asset.sheet(set_name, view)
        classes, line = asset.classes(set_name)
        self.cls = rs.classify(self.img, classes, bg_tol=asset.spec.get("sheet_bg_tol", 24), line_class=line)
        self.cell_cls = asset.cell_classes()
        self.names = asset.class_names()
        self.target = asset.target()
        self.ex = asset.extra_spec(set_name, view)
        st = asset.sets()[set_name]
        self.nominal = st["views"][view].get("nominal")

    def tris(self, v):
        nodes, pose = self.a.scene(self.set, self.view, v[7:])
        T, C = rig.posed_triangles(nodes, pose)
        return T, C, self.a.palette(nodes)

    def evaluate(self, v, ds=1.0):
        step = int(round(1 / ds))
        cls = self.cls[::step, ::step]
        H, W = cls.shape
        if v[3] < 1.2:
            return {"fg": 0.0}, None
        T, C, pal = self.tris(v)
        _, cm, _ = rs.render(T, C, make_cam(v, self.target, 1.0 / step), W, H, shade=False, palette=pal,
                             classes=self.cell_cls)
        return rs.scores(cm, cls, names=self.names), cm

    def prior(self, v):
        pen = 0.0
        for x, (lo, hi) in zip(v[7:], self.ex.get("limits", [])):
            w = 1.0 if (hi - lo) < 2 else 0.01
            pen += w * (max(0.0, lo - x) + max(0.0, x - hi))
        if self.nominal:
            az0, el0 = self.nominal
            daz = abs(((v[0] - az0 + 180) % 360) - 180)
            pen += 0.01 * (max(0.0, daz - 10) + max(0.0, abs(v[1] - el0) - 10))
        return pen

    def loss(self, v, ds):
        return -rs.objective(self.evaluate(v, ds)[0]) + self.prior(v)

    def solve(self, v0, stages=((0.25, 260), (0.5, 220))):
        v = np.array(v0, float)
        n = len(v)
        for ds, it in stages:
            steps = np.array([4, 4, 2, v[3] * 0.25, v[4] * 0.04, 8, 8] + list(self.ex.get("steps", [])), float)[:n]
            steps *= (1 if ds < 0.4 else 0.4)
            simplex = [v] + [v + np.eye(n)[i] * steps[i] for i in range(n)]
            r = minimize(self.loss, v, args=(ds,), method="Nelder-Mead",
                         options={"initial_simplex": simplex, "maxiter": it * (3 if n > 9 else 1),
                                  "xatol": 1e-3, "fatol": 1e-4})
            v = r.x
        return v

    def align(self, v):
        """Scale and centre so the model's projected bbox matches the sheet's (fast initial guess)."""
        T, _, _ = self.tris(v)
        cam = make_cam(list(v[:4]) + [1.0 / v[3], 0.0, 0.0], self.target)
        uv, z = cam.project(T.reshape(-1, 3))
        if (z <= 0.05).any():
            return None
        ys, xs = np.nonzero(self.cls > 0)
        f = (np.ptp(xs) / np.ptp(uv[:, 0]) + np.ptp(ys) / np.ptp(uv[:, 1])) / 2
        w = list(v)
        w[4] = f / v[3]
        w[5] = (xs.max() + xs.min()) / 2 - f * (uv[:, 0].max() + uv[:, 0].min()) / 2
        w[6] = (ys.max() + ys.min()) / 2 - f * (uv[:, 1].max() + uv[:, 1].min()) / 2
        return w

    def grid(self, v0):
        """Coarse search over azimuth, elevation and distance from the initial guess."""
        best, bv = -1e9, None
        for daz in (-40, -20, 0, 20, 40):
            for el in sorted({max(-89.5, min(89.5, v0[1] + d)) for d in (-30, -15, 0, 15, 30)}):
                for D in (3.0, 6.0, 40.0):
                    v = list(v0)
                    v[0], v[1], v[3] = v0[0] + daz, el, D
                    w = self.align(v)
                    if w is None:
                        continue
                    s = -self.loss(w, 0.25)
                    if s > best:
                        best, bv = s, w
        return bv

    def panel(self, v):
        """Sheet | model | overlay | difference strip for a solved vector."""
        H, W = self.cls.shape
        nodes, pose = self.a.scene(self.set, self.view, v[7:])
        T, C, U = rig.posed_triangles(nodes, pose, uv_fn=self.a.gen.ATLAS.face_uvs)
        texes = {}
        for nd in nodes.values():
            atl = nd.get("atlas") or self.a.gen.ATLAS
            texes.setdefault(id(atl), (atl, atl.paint()[0].astype(float)))
        # one texture per atlas: render each atlas's triangles and keep the nearest
        rgb = np.zeros((H, W, 3))
        zbest = np.full((H, W), np.inf)
        cam = make_cam(v, self.target)
        owner = []
        for nd in nodes.values():
            atl = nd.get("atlas") or self.a.gen.ATLAS
            owner += [id(atl)] * sum(len(f[0]) - 2 for f in nd["faces"])
        owner = np.array(owner)
        pal = self.a.palette(nodes)
        for key, (atl, tex) in texes.items():
            m = owner == key
            if not m.any():
                continue
            img, _, z = rs.render(T[m], [c for c, k in zip(C, m) if k], cam, W, H, palette=pal,
                                  classes=self.cell_cls, uvs=U[m], tex=tex)
            upd = z < zbest
            rgb[upd], zbest[upd] = img[upd], z[upd]
        _, cm, _ = rs.render(T, C, cam, W, H, shade=False, palette=pal, classes=self.cell_cls)
        bgc = np.median(np.concatenate([self.img[0], self.img[-1]]), 0)
        ren = np.where((cm > 0)[..., None], rgb, bgc).astype(np.uint8)
        diff = np.full(self.img.shape, 236, np.uint8)
        fm, fs = cm > 0, self.cls > 0
        diff[fm & fs], diff[fm & ~fs], diff[~fm & fs] = (150, 150, 150), (225, 45, 45), (45, 95, 230)
        over = (self.img.astype(float) * 0.5 + ren.astype(float) * 0.5).astype(np.uint8)
        return np.concatenate([self.img, ren, over, diff], 1)


def fit_view(asset, set_name, view, keep=True, grid=False, optimize=True):
    vf = ViewFit(asset, set_name, view)
    prev = asset.cam(set_name, view) if keep else None
    st = asset.sets()[set_name]
    init = list(st["views"][view].get("init", st.get("init", [0, 0, 0, 40, 300, vf.img.shape[1] / 2,
                                                                 vf.img.shape[0] / 2])))
    v0 = prev["cam"] if prev else init + list(vf.ex.get("init", []))
    n_extra = len(vf.ex.get("init", []))
    if len(v0) < 7 + n_extra:
        v0 = list(v0) + list(vf.ex["init"][len(v0) - 7:])
    v0 = list(v0[:7 + n_extra])
    if grid:
        g = vf.grid(v0)
        v0 = list(g) if g is not None else v0
    v = vf.solve(v0) if optimize else np.array(v0, float)
    sc, _ = vf.evaluate(v)
    f = asset.cam_file(set_name, view)
    os.makedirs(os.path.dirname(f), exist_ok=True)
    with open(f,"w") as stream:
        json.dump({"cam": [float(x) for x in v], "scores": {k: round(float(x), 4) for k, x in sc.items()}},stream,indent=1)
    Image.fromarray(vf.panel(v)).save(asset.out("fit", "%s_%s.png" % (set_name, view)))
    return v, sc
