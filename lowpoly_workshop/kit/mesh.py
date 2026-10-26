"""Low-poly mesh primitives: every part is built from flat faces in world coordinates.

Coordinates follow glTF: metres, +Y up, the asset faces +Z, its left side is +X.
A generator returns nodes {name: {"parent", "pivot", "faces", optional "rot", optional "atlas"}} where each
face is (points Nx3, atlas cell name, explicit uv or None, thin flag). Faces are oriented by an "inside"
reference point, so callers never have to think about winding order.
"""
import math

import numpy as np

X = np.array([1.0, 0.0, 0.0])
Y = np.array([0.0, 1.0, 0.0])
Z = np.array([0.0, 0.0, 1.0])


# ------------------------------------------------------------- utilities ---
def nrm(a):
    n = np.linalg.norm(a)
    return a / n if n > 1e-12 else a


def zy(p, x=0.0):
    """[z, y] param pair to a 3D point."""
    return np.array([x, p[1], p[0]], float)


def basis(d, up):
    d = nrm(np.asarray(d, float))
    u = np.asarray(up, float) - np.dot(up, d) * d
    if np.linalg.norm(u) < 1e-6:
        u = X - np.dot(X, d) * d
    u = nrm(u)
    return d, u, np.cross(d, u)


class Mesh:
    def __init__(self):
        self.faces = []

    def face(self, pts, cell, inside=None, uv=None, thin=False):
        pts = np.array(pts, float)
        if inside is not None:
            n = np.cross(pts[1] - pts[0], pts[2] - pts[0])
            if len(pts) > 3:
                n = newell(pts)
            if np.dot(n, pts.mean(0) - inside) < 0:
                pts = pts[::-1]
                if uv is not None:
                    uv = uv[::-1]
        self.faces.append((pts, cell, uv, thin))

    def tris(self):
        return sum(len(f[0]) - 2 for f in self.faces)


def newell(pts):
    n = np.zeros(3)
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        n += np.array([(a[1] - b[1]) * (a[2] + b[2]), (a[2] - b[2]) * (a[0] + b[0]),
                       (a[0] - b[0]) * (a[1] + b[1])])
    return n


def ring(c, d, u, w, rx, ry, n, phase=0.5):
    a = (np.arange(n) + phase) * 2 * math.pi / n
    return np.array([c + ry * math.cos(t) * u + rx * math.sin(t) * w for t in a])


def bridge(m, A, B, cell, inside, thin=False, cells=None):
    n = len(A)
    for k in range(n):
        k1 = (k + 1) % n
        m.face([A[k], A[k1], B[k1], B[k]], cells[k] if cells else cell, inside, thin=thin)


def cap(m, P, cell, inside, thin=False):
    m.face(P, cell, inside, thin=thin)


def tube(m, p0, p1, r0, r1=None, n=8, cell="frame", caps=(False, False), up=Y,
         top=None, rx=None, rx1=None, thin=False, phase=0.5):
    """Prism between two points; r = radius along 'up', rx = radius sideways."""
    r1 = r0 if r1 is None else r1
    rx = r0 if rx is None else rx
    rx1 = r1 if rx1 is None else rx1
    d, u, w = basis(p1 - p0, up)
    A = ring(p0, d, u, w, rx, r0, n, phase)
    B = ring(p1, d, u, w, rx1, r1, n, phase)
    cells = None
    if top:
        cells = [cell] * n
        for k, c in top.items():
            cells[k % n] = c
    inside = (p0 + p1) / 2
    for k in range(n):
        k1 = (k + 1) % n
        mid = (A[k] + A[k1] + B[k] + B[k1]) / 4
        ref = p0 + np.dot(mid - p0, d) * d
        m.face([A[k], A[k1], B[k1], B[k]], cells[k] if cells else cell, ref, thin=thin)
    if caps[0]:
        cap(m, A, cell, inside, thin)
    if caps[1]:
        cap(m, B, cell, inside, thin)
    return A, B


def sweep(m, pts, radii, n=6, cell="tape", caps=(True, True), up=Y, phase=0.5,
          thin=False, cell_fn=None, decal_seg=None):
    pts = [np.asarray(p, float) for p in pts]
    rings = []
    tans = []
    for i in range(len(pts)):
        a = pts[max(i - 1, 0)]
        b = pts[min(i + 1, len(pts) - 1)]
        tans.append(nrm(b - a))
    u = nrm(np.asarray(up, float) - np.dot(up, tans[0]) * tans[0])
    for i, p in enumerate(pts):
        t = tans[i]
        u = nrm(u - np.dot(u, t) * t)
        w = np.cross(t, u)
        scale = 1.0
        if 0 < i < len(pts) - 1:
            s0 = nrm(pts[i] - pts[i - 1])
            s1 = nrm(pts[i + 1] - pts[i])
            half = math.acos(max(-1.0, min(1.0, float(np.dot(s0, s1))))) / 2
            scale = 1.0 / max(math.cos(half), 0.5)
        r = radii[i] if hasattr(radii, "__len__") else radii
        rings.append(ring(p, t, u, w, r * scale, r * scale, n, phase))
    for i in range(len(pts) - 1):
        c = cell_fn(i) if cell_fn else cell
        uv = None
        if decal_seg and i in decal_seg:
            c, uv = decal_seg[i], [(0, 0), (0, 1), (1, 1), (1, 0)]
        for k in range(n):
            k1 = (k + 1) % n
            mid = (rings[i][k] + rings[i][k1] + rings[i + 1][k] + rings[i + 1][k1]) / 4
            seg = pts[i + 1] - pts[i]
            ref = pts[i] + np.dot(mid - pts[i], nrm(seg)) * nrm(seg)
            m.face([rings[i][k], rings[i][k1], rings[i + 1][k1], rings[i + 1][k]], c, ref,
                   thin=thin, uv=uv)
    if caps[0]:
        cap(m, rings[0], cell, pts[0] + tans[0] * 0.01, thin)
    if caps[1]:
        cap(m, rings[-1], cell, pts[-1] - tans[-1] * 0.01, thin)
    return rings


def hexa(m, c, axes, half, cell, skip=(), cells=None, thin=False, uvs=None):
    """Box; axes = 3 unit vectors, half = half sizes. Face keys: +x -x +y -y +z -z."""
    c = np.asarray(c, float)
    keys = ["+x", "-x", "+y", "-y", "+z", "-z"]
    for i in range(3):
        for s, key in ((1, keys[2 * i]), (-1, keys[2 * i + 1])):
            if key in skip:
                continue
            j, k = (i + 1) % 3, (i + 2) % 3
            fc = c + s * half[i] * axes[i]
            pts = [fc + a * half[j] * axes[j] + b * half[k] * axes[k]
                   for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
            uv = None
            if uvs and key in uvs:
                uv = uvs[key] or [(0, 0), (1, 0), (1, 1), (0, 1)]
            m.face(pts, (cells or {}).get(key, cell), c, uv=uv, thin=thin)


def loft(m, rings, cells, caps=(True, True), thin=False, cap_cells=None):
    rings = [np.asarray(r, float) for r in rings]
    for i in range(len(rings) - 1):
        ref = (rings[i].mean(0) + rings[i + 1].mean(0)) / 2
        cell = cells[i] if isinstance(cells, (list, tuple)) else cells
        n = len(rings[i])
        for k in range(n):
            k1 = (k + 1) % n
            m.face([rings[i][k], rings[i][k1], rings[i + 1][k1], rings[i + 1][k]], cell, ref,
                   thin=thin)
    cc = cap_cells or (cells[0] if isinstance(cells, (list, tuple)) else cells,
                       cells[-1] if isinstance(cells, (list, tuple)) else cells)
    if caps[0]:
        m.face(rings[0], cc[0], rings[1].mean(0), thin=thin)
    if caps[1]:
        m.face(rings[-1], cc[1], rings[-2].mean(0), thin=thin)


def scaled(nodes, k):
    """Uniformly scaled copy of built nodes (geometry and pivots about the origin)."""
    out = {}
    for name, nd in nodes.items():
        out[name] = dict(nd, pivot=np.asarray(nd["pivot"]) * k,
                         faces=[(pts * k, cell, uv, thin) for pts, cell, uv, thin in nd["faces"]])
    return out


def triangles(nodes, names=None):
    """Flatten to arrays: tris (T,3,3), cell names (T), node names (T)."""
    tris, cells, owner = [], [], []
    for name, nd in nodes.items():
        if names and name not in names:
            continue
        for pts, cell, uv, thin in nd["faces"]:
            for i in range(1, len(pts) - 1):
                tris.append([pts[0], pts[i], pts[i + 1]])
                cells.append(cell)
                owner.append(name)
    return np.array(tris), cells, owner


def tri_count(node):
    return sum(len(f[0]) - 2 for f in node["faces"])


def triangulate_profile(points):
    """Triangulate one simple, non-self-intersecting 2D profile, including concave caps.

    Returns indices into the original profile. No repeated closing point or zero-length
    edges; collinear points may be retained when they do not prevent a valid ear.
    """
    p = np.asarray(points, dtype=float)
    if p.ndim != 2 or p.shape[1] != 2 or len(p) < 3 or not np.isfinite(p).all():
        raise ValueError('A profile needs at least three finite 2D points')
    cross = lambda a, b: a[0] * b[1] - a[1] * b[0]
    scale = max(float(np.ptp(p, axis=0).max()), 1e-12)
    epsilon = np.finfo(float).eps * scale * scale * 32
    area = sum(cross(p[i], p[(i + 1) % len(p)]) for i in range(len(p)))
    if abs(area) <= epsilon:
        raise ValueError('Profile has zero area')
    sign = 1 if area > 0 else -1
    remaining, out = list(range(len(p))), []
    while len(remaining) > 3:
        for j, b in enumerate(remaining):
            a, c = remaining[j - 1], remaining[(j + 1) % len(remaining)]
            if cross(p[b] - p[a], p[c] - p[b]) * sign <= epsilon:
                continue
            def contains(k):
                return all(cross(p[v] - p[u], p[k] - p[u]) * sign >= -epsilon
                           for u, v in [(a, b), (b, c), (c, a)])
            if any(contains(k) for k in remaining if k not in [a, b, c]):
                continue
            out.append([a, b, c])
            remaining.pop(j)
            break
        else:
            raise ValueError('Profile cannot be triangulated; check crossings or repeated points')
    return out + [remaining]
