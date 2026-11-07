"""Bake a Pixal3D generation's colours onto the asset's own hand-built LODs.

The generated mesh is far too dense for a game LOD and does not decimate cleanly below a few
thousand triangles, but its colours carry the reference's detail. This module keeps the authored
geometry and moves only the colour across:

  1. Load the dense generated surface with per-point colour (the `.ply` trellis-cli writes next to
     its `.glb`, or the `.glb` itself, sampling its base-colour texture) in Workshop's frame.
  2. Fit it to the reference LOD: bounds first, then a per-axis scale and offset that maximise the
     front and side silhouette overlap.
  3. Give every authored polygon its own chart in one atlas and colour each texel from the first
     generated surface met coming in from outside along the polygon's normal, falling back to the
     nearest generated point facing the same way.
  4. Write per LOD the atlas, a textured `.glb` (all nodes flattened into one mesh) and a preview.
"""
from pathlib import Path

import numpy as np

from .spec import local_path
from .kit.atlas import write_png
from .kit.atomic import replacing, write_json
from .kit.glb import write_glb
from . import base_mesh

FIT_STEPS = ((0.08, 0.043), (0.04, 0.021), (0.02, 0.0086), (0.01, 0.0036))  # (scale, offset / extent)
BUCKET_DOT = 0.35  # how closely a fallback point's normal must agree with the polygon's
PAD = 2  # texels around each chart, sampled from the polygon's plane


# -- the generated surface

def _read_ply(path):
    """Binary little-endian PLY as trellis-cli writes it: float xyz + uchar rgb, triangle faces."""
    with open(path, "rb") as f:
        header = b""
        while not header.endswith(b"end_header\n"):
            line = f.readline()
            if not line:
                raise ValueError(f"{path}: PLY header has no end_header")
            header += line
        lines = header.decode("ascii", "replace").splitlines()
        if "format binary_little_endian 1.0" not in lines:
            raise ValueError(f"{path}: expected a binary little-endian PLY")
        props = [l.split()[-1] for l in lines if l.startswith("property ") and "list" not in l]
        if props[:6] != ["x", "y", "z", "red", "green", "blue"] or len(props) != 6:
            raise ValueError(f"{path}: expected vertex properties x y z red green blue, got {props}")
        nv = int(next(l for l in lines if l.startswith("element vertex")).split()[-1])
        nf = int(next(l for l in lines if l.startswith("element face")).split()[-1])
        v = np.fromfile(f, dtype=[("p", "<f4", 3), ("c", "u1", 3)], count=nv)
        fc = np.fromfile(f, dtype=[("n", "u1"), ("i", "<i4", 3)], count=nf)
    if len(v) != nv or len(fc) != nf or (fc["n"] != 3).any():
        raise ValueError(f"{path}: truncated PLY or non-triangle faces")
    p = v["p"].astype(np.float64)
    p = np.stack([-p[:, 0], p[:, 2], p[:, 1]], axis=1)  # Z-up, front -Y -> Y-up, front +Z
    return p, v["c"].astype(np.float64) / 255.0, fc["i"].astype(np.int64)


def _read_glb(path, front="-z", order=("vertex", "texture", "factor"), drop_node=(), drop_plinth=False):
    """Positions, sRGB colours and triangles of every mesh primitive (at rest pose), turned to face +Z.

    `front` is the direction the file's model faces (Pixal3D's glTF faces -Z). Colours come from `order`:
    by default vertex colours, then the base-colour texture, then the material colour."""
    scene = base_mesh.read_scene(path)
    prims = list(scene.prims)
    if drop_node:
        prims, _ = base_mesh.drop_nodes(scene, prims, drop_node)
    elif drop_plinth:
        prims, _ = base_mesh.detect_plinth(scene, prims)
    prims = base_mesh.rotate(prims, front)
    pts, cols, faces, base = [], [], [], 0
    for prim in prims:
        c, source = base_mesh.vertex_colours(scene, prim, order)
        if c is None:
            raise ValueError(f"{path}: mesh has neither COLOR_0, a textured TEXCOORD_0 nor a material colour")
        pts.append(prim.pos)
        cols.append(c)
        faces.append(prim.tri + base)
        base += len(prim.pos)
    return np.concatenate(pts), np.concatenate(cols), np.concatenate(faces)


def load_source(path, **glb_options):
    """(points, colours 0..1, unit normals) of the generated surface in Workshop's frame.

    `glb_options` (front, order, drop_node, drop_plinth) apply to a GLB; a PLY is always trellis-cli's."""
    path = Path(path)
    p, c, f = _read_ply(path) if path.suffix.lower() == ".ply" else _read_glb(path, **glb_options)
    fn = np.cross(p[f[:, 1]] - p[f[:, 0]], p[f[:, 2]] - p[f[:, 0]])
    vn = np.zeros_like(p)
    for k in range(3):
        np.add.at(vn, f[:, k], fn)
    vn /= np.linalg.norm(vn, axis=1, keepdims=True) + 1e-12
    # face centres densify a coarse source so the outside-in trace has no holes between vertices
    if len(f) < 4 * len(p):
        p = np.concatenate([p, p[f].mean(1)])
        c = np.concatenate([c, c[f].mean(1)])
        cn = fn / (np.linalg.norm(fn, axis=1, keepdims=True) + 1e-12)
        vn = np.concatenate([vn, cn])
    return p, c, vn


def default_source(folder):
    for rel in ("inputs/pixal3d_raw.ply", "inputs/pixal3d_raw.glb"):
        path = local_path(folder, rel)
        if path.is_file():
            return path
    raise FileNotFoundError("No inputs/pixal3d_raw.ply or .glb; run `pixal3d run` first or pass --source")


# -- the authored LOD

def lod_polygons(nodes):
    """Every authored polygon (world points, cell) across all nodes."""
    return [(np.asarray(q, float), cell) for nd in nodes.values() for q, cell, _, _ in nd["faces"]]


def _plane_basis(q):
    n = np.zeros(3)
    for i in range(len(q)):  # Newell normal
        a, b = q[i], q[(i + 1) % len(q)]
        n += [(a[1] - b[1]) * (a[2] + b[2]), (a[2] - b[2]) * (a[0] + b[0]), (a[0] - b[0]) * (a[1] + b[1])]
    n /= np.linalg.norm(n) + 1e-12
    u = q[1] - q[0]
    u -= n * (u @ n)
    u /= np.linalg.norm(u) + 1e-12
    return n, u, np.cross(n, u)


def pack(polys, size, pad=PAD, fill=0.55):
    """Shelf-pack every polygon as its own chart at one texel density.

    Returns per-polygon UVs (0..1, v from the top as glTF expects), polygon normals and texels/metre."""
    charts = []
    for q, _ in polys:
        n, u, w = _plane_basis(q)
        c2 = np.column_stack([(q - q[0]) @ u, (q - q[0]) @ w])
        charts.append((n, c2 - c2.min(0), np.ptp(c2, axis=0)))
    area = sum(s[0] * s[1] for _, _, s in charts) or 1e-6
    scale = np.sqrt(fill * size * size / area)
    order = sorted(range(len(charts)), key=lambda i: -charts[i][2][1])
    while True:
        x = y = shelf = 0
        uvs, ok = [None] * len(charts), True
        for i in order:
            wpx, hpx = np.ceil(charts[i][2] * scale).astype(int) + 2 * pad
            if wpx > size:
                ok = False
                break
            if x + wpx > size:
                x, y, shelf = 0, y + shelf, 0
            if y + hpx > size:
                ok = False
                break
            uvs[i] = (charts[i][1] * scale + [x + pad, y + pad]) / size
            x, shelf = x + wpx, max(shelf, hpx)
        if ok:
            return uvs, [c[0] for c in charts], float(scale)
        scale *= 0.92


def surface_samples(polys, n=300000, seed=0):
    tris = np.array([q[[0, k, k + 1]] for q, _ in polys for k in range(1, len(q) - 1)])
    area = np.linalg.norm(np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]), axis=1) / 2
    rng = np.random.default_rng(seed)
    t = rng.choice(len(tris), n, p=area / area.sum())
    a, b = rng.random(n), rng.random(n)
    flip = a + b > 1
    a[flip], b[flip] = 1 - a[flip], 1 - b[flip]
    return tris[t, 0] + a[:, None] * (tris[t, 1] - tris[t, 0]) + b[:, None] * (tris[t, 2] - tris[t, 0])


# -- registration

def _silhouettes(pts, llo, lhi):
    """Front (x, y) and side (z, y) occupancy masks on a grid around the LOD bounds."""
    ext = float((lhi - llo).max())
    cell = ext / 240
    lo, hi = llo - 0.15 * ext, lhi + 0.15 * ext
    shape = np.ceil((hi - lo) / cell).astype(int)
    g = np.floor((pts - lo) / cell).astype(int)
    g = g[np.all((g >= 0) & (g < shape), 1)]
    out = []
    for a in (0, 2):
        m = np.zeros((shape[1], shape[a]), bool)
        m[g[:, 1], g[:, a]] = True
        m |= np.roll(m, 1, 0) | np.roll(m, -1, 0) | np.roll(m, 1, 1) | np.roll(m, -1, 1)
        out.append(m)
    return out


def fit(dense_pts, polys):
    """Map from the generated frame onto the LOD: bounds, then silhouette-IoU coordinate descent.

    Returns (to_lod callable, record dict)."""
    lod_pts = surface_samples(polys)
    allq = np.concatenate([q for q, _ in polys])
    llo, lhi = allq.min(0), allq.max(0)
    lo, hi = np.percentile(dense_pts, 0.5, axis=0), np.percentile(dense_pts, 99.5, axis=0)
    span = np.where(hi - lo > 1e-9, hi - lo, 1.0)
    centre, ext = (llo + lhi) / 2, float((lhi - llo).max())
    target = _silhouettes(lod_pts, llo, lhi)
    sub = dense_pts[:: max(1, len(dense_pts) // 400000)]
    base = llo + (sub - lo) / span * (lhi - llo)

    def score(s, o):
        f, sd = _silhouettes(centre + (base - centre) * s + o, llo, lhi)
        return ((f & target[0]).sum() / max((f | target[0]).sum(), 1)
                + (sd & target[1]).sum() / max((sd | target[1]).sum(), 1))

    s, o = np.ones(3), np.zeros(3)
    best = score(s, o)
    for step_s, step_o in FIT_STEPS:
        improved = True
        while improved:
            improved = False
            for axis in (1, 0, 2):
                for ds, do in ((step_s, 0), (-step_s, 0), (0, step_o * ext), (0, -step_o * ext)):
                    s2, o2 = s.copy(), o.copy()
                    s2[axis] += ds
                    o2[axis] += do
                    v = score(s2, o2)
                    if v > best + 1e-4:
                        best, s, o, improved = v, s2, o2, True

    def to_lod(x):
        return centre + (llo + (x - lo) / span * (lhi - llo) - centre) * s + o

    return to_lod, {"scale": s.round(4).tolist(), "offset": o.round(4).tolist(), "silhouette_iou": round(best / 2, 4)}


# -- baking

def _trace(pts, nrm, tree, ext):
    """Sphere-trace from outside along -normal against the dense points; index of first hit or -1."""
    start, eps, depth = 0.085 * ext, 0.0036 * ext, 0.085 * ext
    x = pts + nrm * start
    hit = np.full(len(pts), -1)
    travelled = np.zeros(len(pts))
    act = np.arange(len(pts))
    for _ in range(60):
        if not len(act):
            break
        d, nn = tree.query(x[act], workers=-1)
        h = d < eps
        hit[act[h]] = nn[h]
        step = np.maximum(d - eps * 0.5, 0.0007 * ext)
        x[act] -= nrm[act] * step[:, None]
        travelled[act] += step
        act = act[~h & (travelled[act] < start + depth)]
    return hit


def _clamp_into(pts, poly):
    """Points outside a 2D polygon moved to its nearest boundary point; points inside unchanged."""
    a, b = poly, np.roll(poly, -1, 0)
    ab = b - a
    rel = pts[:, None, :] - a[None]
    t = np.clip((rel * ab).sum(2) / np.maximum((ab * ab).sum(1), 1e-18), 0, 1)
    near = a[None] + t[..., None] * ab[None]
    best = near[np.arange(len(pts)), ((pts[:, None, :] - near) ** 2).sum(2).argmin(1)]
    # even-odd rule
    ya, yb = a[:, 1][None], b[:, 1][None]
    x, y = pts[:, :1], pts[:, 1:]
    cross = (ya > y) != (yb > y)
    xi = a[:, 0][None] + (y - ya) / np.where(yb != ya, yb - ya, 1e-18) * ab[:, 0][None]
    inside = (cross & (x < xi)).sum(1) % 2 == 1
    return np.where(inside[:, None], pts, best)


def _texels(polys, uvs, normals, size, density):
    """World point, polygon normal and (row, col) of every texel in each chart's padded rectangle.

    Texels map back through the polygon's plane and are clamped into the polygon, so a chart
    thinner than a texel still gets its own colour and the padding repeats the polygon's edge."""
    pts, nrm, pix = [], [], []
    for (q, _), uv, n in zip(polys, uvs, normals):
        _, u, w = _plane_basis(q)
        px = uv * size
        x0, y0 = np.floor(px.min(0)).astype(int) - PAD
        x1, y1 = np.ceil(px.max(0)).astype(int) + PAD
        cols, rows = np.meshgrid(np.arange(max(x0, 0), min(x1, size)), np.arange(max(y0, 0), min(y1, size)))
        cols, rows = cols.ravel(), rows.ravel()
        c2 = _clamp_into((np.stack([cols + 0.5, rows + 0.5], 1) - px[0]) / density,
                         np.column_stack([(q - q[0]) @ u, (q - q[0]) @ w]))
        pts.append(q[0] + c2[:, :1] * u + c2[:, 1:] * w)
        nrm.append(np.repeat(n[None], len(c2), 0))
        pix.append(np.stack([rows, cols], 1))
    return np.concatenate(pts), np.concatenate(nrm), np.concatenate(pix)


# -- facade alignment

FACADES = (0, 90, 180, -90)  # camera azimuths: front, right, back, left
FACADE_PX = 800  # pixels along the LOD's longest side
FACADE_DOT = 0.9  # how squarely a polygon must face a facade camera to follow its warp
WARP_X, WARP_Y = 0.035, 0.015  # largest shift as a share of the LOD's extent


def _profile(lab, valid, axis):
    """Per-column (axis 0) or per-row (axis 1) lightness and edge strength over the silhouette, z-scored."""
    import cv2
    L = lab[..., 0].astype(float)
    red = 0 if axis == 0 else 1
    w = np.maximum(valid.sum(red), 1)
    edge = np.abs(np.gradient(cv2.GaussianBlur(L, (0, 0), 1.5), axis=1 - red)) * valid
    f = np.stack([(L * valid).sum(red) / w, edge.sum(red) / w], 1)
    return (f - f.mean(0)) / (f.std(0) + 1e-9)


def _dtw_shift(a, g, reach):
    """Smoothed monotone shift j - i (|shift| <= reach) aligning profile `a` onto profile `g`."""
    import cv2
    n, span = len(a), 2 * reach + 1
    offs = np.arange(-reach, reach + 1)
    idx = np.clip(np.arange(n)[:, None] + offs[None], 0, len(g) - 1)
    cost = ((a[:, None, :] - g[idx]) ** 2).sum(2) + 0.02 * offs[None] ** 2
    D = cost.copy()
    back = np.zeros((n, span), int)
    for i in range(1, n):
        cand = np.stack([np.r_[np.inf, D[i - 1, :-1]], D[i - 1], np.r_[D[i - 1, 1:], np.inf]])
        k = cand.argmin(0)
        D[i] += cand[k, np.arange(span)]
        back[i] = np.arange(span) + k - 1
    off = np.zeros(n, int)
    o = int(D[-1].argmin())
    for i in range(n - 1, -1, -1):
        off[i] = o
        o = back[i, o]
    return cv2.GaussianBlur((off - reach).astype(np.float32)[None], (0, 0), 3)[0]


def facade_warps(baker, polys, cells_rgb):
    """Per side of the LOD, the in-plane shift that best lines the generated facade up with the authored one.

    Both are rendered orthographically; a monotone column mapping and a monotone row mapping are found by
    dynamic time warping their lightness and edge profiles, so posts and window bays move into place
    without tearing. Returns [(camera, pixels per metre, x shift px, y shift px)] per side."""
    import cv2
    from .kit.raster import Camera, render
    tris, cells = [], []
    for q, c in polys:
        for k in range(1, len(q) - 1):
            tris.append(q[[0, k, k + 1]])
            cells.append(c)
    tris = np.array(tris)
    allq = tris.reshape(-1, 3)
    centre, ext = (allq.min(0) + allq.max(0)) / 2, float(np.ptp(allq, axis=0).max())
    ppm = FACADE_PX / ext
    pal = {c: np.asarray(cells_rgb(c), float) / 255 for c in set(cells)}
    out = []
    for az in FACADES:
        cam = Camera(az, 0, 0, 10 * ext, ppm * 10 * ext, 0, 0, target=tuple(centre), ortho=True)
        uv, _ = cam.project(allq)
        lo = uv.min(0) - 4
        W, H = (uv.max(0) - lo + 4).astype(int)
        cam = Camera(az, 0, 0, 10 * ext, ppm * 10 * ext, -lo[0], -lo[1], target=tuple(centre), ortho=True)
        A, _, za = render(tris, cells, cam, W, H, shade=False, palette=pal, classes={"_default": 1})
        valid = ~np.isinf(za)
        uv, z = cam.project(baker.pts)
        px, py = uv[:, 0].astype(int), uv[:, 1].astype(int)
        ok = (px >= 0) & (px < W) & (py >= 0) & (py < H)
        pix = py[ok] * W + px[ok]
        order = np.lexsort((z[ok], pix))
        pix, col = pix[order], baker.col[ok][order]
        first = np.ones(len(pix), bool)
        first[1:] = pix[1:] != pix[:-1]
        G = np.zeros((H * W, 3), np.uint8)
        G[pix[first]] = (np.clip(col[first], 0, 1) * 255).astype(np.uint8)
        hole = np.ones(H * W, np.uint8)
        hole[pix[first]] = 0
        G = cv2.inpaint(G.reshape(H, W, 3), hole.reshape(H, W), 3, cv2.INPAINT_TELEA)
        A8 = (np.clip(np.where(valid[..., None], A, 0), 0, 1) * 255).astype(np.uint8)
        la, lg = cv2.cvtColor(A8, cv2.COLOR_RGB2LAB), cv2.cvtColor(G, cv2.COLOR_RGB2LAB)
        dx = _dtw_shift(_profile(la, valid, 0), _profile(lg, valid, 0), max(1, int(WARP_X * FACADE_PX)))
        dy = _dtw_shift(_profile(la, valid, 1), _profile(lg, valid, 1), max(1, int(WARP_Y * FACADE_PX)))
        out.append((cam, ppm, dx, dy))
    return out


def _warp(pts, nrm, warps):
    """Shift texel points on facade-facing polygons by their facade's warp."""
    pts = pts.copy()
    for cam, ppm, dx, dy in warps:
        m = nrm @ -cam.fwd > FACADE_DOT
        if not m.any():
            continue
        uv, _ = cam.project(pts[m])
        ix = np.clip(uv[:, 0].astype(int), 0, len(dx) - 1)
        iy = np.clip(uv[:, 1].astype(int), 0, len(dy) - 1)
        pts[m] += (dx[ix, None] * cam.right - dy[iy, None] * cam.up) / ppm
    return pts


class Baker:
    """The fitted generated surface, reused for every LOD."""

    def __init__(self, source, to_lod):
        from scipy.spatial import cKDTree
        p, self.col, vn = source
        self.pts = to_lod(p)
        self.ext = float(np.ptp(self.pts, axis=0).max())
        self.tree = cKDTree(self.pts)
        self.buckets = []
        for axis in range(3):
            for sign in (1, -1):
                sel = np.nonzero(sign * vn[:, axis] > BUCKET_DOT)[0]
                if len(sel):
                    self.buckets.append((axis, sign, sel, cKDTree(self.pts[sel])))

    def bake(self, polys, uvs, normals, size, density, warps=()):
        """Atlas (size, size, 3) floats 0..1 and the share of texels hit from outside."""
        img = np.zeros((size, size, 3))
        pts, nrm, pix = _texels(polys, uvs, normals, size, density)
        pts = _warp(pts, nrm, warps)
        hit = _trace(pts, nrm, self.tree, self.ext)
        got = hit >= 0
        img[pix[got, 0], pix[got, 1]] = self.col[hit[got]]
        dom = np.argmax(np.abs(nrm), 1)
        sgn = np.sign(nrm[np.arange(len(nrm)), dom])
        rest = ~got
        for axis, sign, sel, tree in self.buckets:
            m = (dom == axis) & (sgn == sign) & rest
            if m.any():
                _, nn = tree.query(pts[m], k=min(4, len(sel)), workers=-1)
                nn = nn.reshape(int(m.sum()), -1)
                img[pix[m, 0], pix[m, 1]] = self.col[sel[nn]].mean(1)
                rest &= ~m
        if rest.any():
            _, nn = self.tree.query(pts[rest], workers=-1)
            img[pix[rest, 0], pix[rest, 1]] = self.col[nn]
        return img, float(got.mean()), len(pts)


# -- output

def write_textured_glb(path, polys, uvs, png_bytes, name="Model", material="pixal3d_bake", generator="Lowpoly Workshop pixal3d bake"):
    """One flat-shaded mesh and one PBR material with the baked atlas embedded."""
    pos, nor, tex = [], [], []
    for (q, _), uv in zip(polys, uvs):
        n, _, _ = _plane_basis(q)
        for k in range(1, len(q) - 1):
            for j in (0, k, k + 1):
                pos.append(q[j])
                nor.append(n)
                tex.append(uv[j])
    pos, nor, tex = (np.asarray(a, np.float32) for a in (pos, nor, tex))
    idx = np.arange(len(pos), dtype=np.uint32)
    blobs = [pos.tobytes(), nor.tobytes(), tex.tobytes(), idx.tobytes(), png_bytes]
    views, off = [], 0
    for b in blobs:
        views.append({"buffer": 0, "byteOffset": off, "byteLength": len(b)})
        off += (len(b) + 3) // 4 * 4
    for v in views[:4]:
        v["target"] = 34962
    views[3]["target"] = 34963
    binc = b"".join(b + b"\0" * ((4 - len(b) % 4) % 4) for b in blobs)
    n = len(pos)
    gltf = {
        "asset": {"version": "2.0", "generator": generator},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"name": name, "mesh": 0}],
        "meshes": [{"name": name, "primitives": [{
            "attributes": {"POSITION": 0, "NORMAL": 1, "TEXCOORD_0": 2}, "indices": 3, "material": 0}]}],
        "materials": [{"name": material, "pbrMetallicRoughness": {
            "baseColorTexture": {"index": 0}, "metallicFactor": 0.0, "roughnessFactor": 1.0}}],
        "textures": [{"source": 0, "sampler": 0}],
        "samplers": [{"magFilter": 9729, "minFilter": 9987, "wrapS": 33071, "wrapT": 33071}],
        "images": [{"bufferView": 4, "mimeType": "image/png"}],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": n, "type": "VEC3",
             "min": pos.min(0).tolist(), "max": pos.max(0).tolist()},
            {"bufferView": 1, "componentType": 5126, "count": n, "type": "VEC3"},
            {"bufferView": 2, "componentType": 5126, "count": n, "type": "VEC2"},
            {"bufferView": 3, "componentType": 5125, "count": n, "type": "SCALAR"},
        ],
        "bufferViews": views,
        "buffers": [{"byteLength": len(binc)}],
    }
    write_glb(path, gltf, binc)


def _preview(path, baker, lods, size=360):
    """Front and quarter views: the fitted generated points, then each baked LOD."""
    from PIL import Image, ImageDraw
    from .kit.raster import Camera, render
    allq = np.concatenate([q for q, _ in lods[0][1]])
    llo, lhi = allq.min(0), allq.max(0)
    centre, ext = (llo + lhi) / 2, float((lhi - llo).max()) * 0.62
    views = (("front", 0, 8), ("quarter", 35, 18))
    cams = [Camera(az, el, 0, 10 * ext, size / 2 / ext * 10 * ext, size / 2, size / 2,
                   target=tuple(centre), ortho=True) for _, az, el in views]
    cols = []
    tiles = []
    sub = np.arange(0, len(baker.pts), max(1, len(baker.pts) // 3000000))
    for cam in cams:
        uv, z = cam.project(baker.pts[sub])
        px, py = uv[:, 0].astype(int), uv[:, 1].astype(int)
        ok = (px >= 0) & (px < size) & (py >= 0) & (py < size)
        pix, zz, cc = py[ok] * size + px[ok], z[ok], baker.col[sub][ok]
        order = np.lexsort((zz, pix))
        pix, cc = pix[order], cc[order]
        first = np.ones(len(pix), bool)
        first[1:] = pix[1:] != pix[:-1]
        img = np.full((size * size, 3), 0.96)
        img[pix[first]] = cc[first]
        tiles.append(img.reshape(size, size, 3))
    cols.append(("generated, fitted", tiles))
    for label, polys, uvs, tex in lods:
        tris, tuv = [], []
        for (q, _), uv in zip(polys, uvs):
            for k in range(1, len(q) - 1):
                tris.append(q[[0, k, k + 1]])
                tuv.append(uv[[0, k, k + 1]])
        tris, tuv = np.array(tris), np.array(tuv)
        tiles = []
        for cam in cams:
            rgb, _, z = render(tris, ["_"] * len(tris), cam, size, size, palette={"_": np.ones(3)},
                               classes={"_default": 1}, uvs=tuv, tex=tex)
            tiles.append(np.where(np.isinf(z)[..., None], 0.96, rgb))
        cols.append((f"{label}: {len(tris)} tris", tiles))
    sheet = Image.new("RGB", (size * len(cols), size * len(views) + 24), (255, 255, 255))
    d = ImageDraw.Draw(sheet)
    for k, (title, tiles) in enumerate(cols):
        d.text((k * size + 8, 6), title, fill=(0, 0, 0))
        for r, t in enumerate(tiles):
            sheet.paste(Image.fromarray((np.clip(t, 0, 1) * 255).astype(np.uint8)), (k * size, 24 + r * size))
    with replacing(str(path)) as tmp:
        sheet.save(tmp, format="PNG")


def _inside_or_name(path, root):
    """A project-relative path for a file inside the project, else only its file name (no absolute paths)."""
    path = Path(path).resolve()
    return path.relative_to(Path(root).resolve()).as_posix() if path.is_relative_to(Path(root).resolve()) else path.name


def bake_lods(folder, source=None, variants=None, fit_variant=None, size=1024, align=True, *,
              label="PIXAL3D", out_name="pixal3d_bake", material="pixal3d_bake", default=None, glb_options=None,
              relative_source=False):
    """Bake a dense source's colours onto the asset's outputs; returns the path of the bake record.

    The defaults are the Pixal3D bake. `base bake` passes its own label, output folder, default source and
    GLB options (front, colour order, nodes to drop)."""
    import io
    import time
    from PIL import Image
    from .kit.asset import Asset
    from .pixal3d import file_sha256
    t0 = time.monotonic()
    a = Asset(folder)
    outputs = a.outputs()
    if not outputs:
        raise ValueError("asset.json has no outputs to bake onto")
    by_variant = {str(o["variant"]) if o.get("variant") is not None else Path(o["file"]).stem: o for o in outputs}
    chosen = [str(v) for v in variants] if variants else list(by_variant)
    unknown = [v for v in chosen + ([str(fit_variant)] if fit_variant is not None else []) if v not in by_variant]
    if unknown:
        raise ValueError(f"No output with variant {unknown[0]!r}; outputs have {sorted(by_variant)}")
    if size < 64 or size & (size - 1):
        raise ValueError("--size must be a power of two of at least 64")
    src = Path(source).resolve() if source else (default or default_source)(a.dir)

    def polys_of(variant):
        o = by_variant[variant]
        return lod_polygons(a.build(o.get("variant"), o.get("scale", 1.0)))

    dense = load_source(src, **(glb_options or {}))
    ref = str(fit_variant) if fit_variant is not None else chosen[0]
    to_lod, fit_record = fit(dense[0], polys_of(ref))
    print("%s bake fit on variant %s: scale %s offset %s silhouette IoU %.3f" % (
        label, ref, fit_record["scale"], fit_record["offset"], fit_record["silhouette_iou"]), flush=True)
    baker = Baker(dense, to_lod)
    del dense
    out_dir = Path(a.out(out_name, "bake.json")).parent
    shown = (_inside_or_name(src, a.dir) if relative_source else src.as_posix())
    record = {"source": shown, "source_sha256": file_sha256(src), "fit_variant": ref,
              "fit": fit_record, "size": int(size), "outputs": []}
    previews = []
    for variant in chosen:
        polys = polys_of(variant)
        uvs, normals, density = pack(polys, size)
        warps = facade_warps(baker, polys, a.gen.ATLAS.rgb_of) if align else []
        img, hits, texels = baker.bake(polys, uvs, normals, size, density, warps)
        pixels = (np.clip(img, 0, 1) * 255).astype(np.uint8)
        stem = Path(by_variant[variant]["file"]).stem
        png, glb = out_dir / f"{stem}_bake.png", out_dir / f"{stem}_baked.glb"
        with replacing(str(png)) as tmp:
            write_png(tmp, pixels)
        buf = io.BytesIO()
        Image.fromarray(pixels).save(buf, format="PNG")
        write_textured_glb(glb, polys, uvs, buf.getvalue(), name=stem, material=material,
                           generator=f"Lowpoly Workshop {out_name.replace('_bake', '')} bake")
        tris = sum(len(q) - 2 for q, _ in polys)
        print(f"{label} baked {stem}: {tris} tris, {len(polys)} charts, {density:.0f} texels/m, "
              f"{hits:.0%} hit from outside", flush=True)
        record["outputs"].append({"variant": variant, "triangles": tris, "charts": len(polys),
                                  "texels_per_metre": round(density, 1), "texels": texels,
                                  "outside_in_hits": round(hits, 4),
                                  "facade_shift_max_m": round(max((float(np.abs(np.r_[dx, dy]).max()) / ppm
                                                                   for _, ppm, dx, dy in warps), default=0.0), 3),
                                  "texture": png.relative_to(a.dir).as_posix(),
                                  "glb": glb.relative_to(a.dir).as_posix()})
        previews.append((stem, polys, uvs, img))
    preview = out_dir / "preview.png"
    _preview(preview, baker, previews)
    record["preview"] = preview.relative_to(a.dir).as_posix()
    record["seconds"] = round(time.monotonic() - t0, 1)
    meta = out_dir / "bake.json"
    write_json(str(meta), record, indent=2)
    return meta
