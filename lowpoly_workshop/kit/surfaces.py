"""Coplanar overlaps on an exported model: faces that fight in the depth buffer, and faces glued
back to back (depth-aware overlap diagnostics).

- z-fighting: two faces facing the same way, within `eps` of one plane, overlapping over an area,
  that look different there (the atlas texel at the overlap, or the texture coordinate without an
  atlas). Alike, the flicker can't be seen: only hidden, drawn twice.
- back to back: opposite faces lying on each other over part of their area (glued pieces: neither
  is ever seen). A mirrored pair over the same corners is a two-sided card and is meant.
Faces on the ground (y = 0) facing down are never seen and are skipped.

Depth resolution: with a 0.25 m near plane and a 24-bit depth buffer, two layers g apart stay
ordered to about sqrt(g * 4.2e6) m. `eps_for(view_m)` is the gap a model seen from view_m needs.
A fight is only seen if the overlap still covers VISIBLE_PX pixels where it starts to flicker
(55 degree view, 1080 pixels high); smaller ones are "faint". Faces flush in one plane always count.
"""
import math

import numpy as np

PARALLEL = math.cos(math.radians(2))
DEPTH_K = 4.2e6
VISIBLE_PX = 2
PIXEL_RAD = math.radians(55) / 1080


def visible_fight(area, gap):
    """Whether a fight gap apart over area covers VISIBLE_PX pixels where it starts to flicker."""
    return math.sqrt(area) >= VISIBLE_PX * PIXEL_RAD * math.sqrt(gap * DEPTH_K)


def eps_for(view_m):
    """The layer gap (m) that stays ordered in the depth buffer at view_m metres."""
    return view_m * view_m / DEPTH_K


def _tri_uv(g, i):
    """Per-triangle corner texture coordinates of node i, in local_geo's order (or None)."""
    n = g.nodes[i]
    out = []
    for prim in g.js["meshes"][n["mesh"]]["primitives"]:
        idx = g.acc(prim["indices"]).ravel()
        if "TEXCOORD_0" not in prim["attributes"]:
            return None
        uv = g.acc(prim["attributes"]["TEXCOORD_0"]).astype(float)
        out.append(uv[idx.reshape(-1, 3)])
    return np.concatenate(out)


def soup(g, geo):
    """Triangles (n, 3, 3), their node names and corner UVs (n, 3, 2) for the posed geometry."""
    tris, names, uvs = [], [], []
    for name, t in geo.items():
        i = g.names.index(name)
        uv = _tri_uv(g, i)
        tris.append(t)
        names += [name] * len(t)
        uvs.append(uv if uv is not None else np.zeros((len(t), 3, 2)))
    if not tris:
        return np.zeros((0, 3, 3)), [], np.zeros((0, 3, 2))
    # Without an image, matching UVs do not prove matching vertex/material colours.
    # Leave these potential conflicts conservative instead of hiding them.
    return np.concatenate(tris), names, np.concatenate(uvs) if g.js.get("images") else None


def _clip_area(A, B):
    """Area of the overlap of two coplanar 2D triangles (Sutherland-Hodgman) and its centre."""
    def ccw(P):
        a = (P[1][0] - P[0][0]) * (P[2][1] - P[0][1]) - (P[1][1] - P[0][1]) * (P[2][0] - P[0][0])
        return P if a >= 0 else P[::-1]
    A, poly = ccw(list(A)), ccw(list(B))
    for i in range(3):
        p, q = A[i], A[(i + 1) % 3]
        side = lambda r: (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
        out = []
        for k in range(len(poly)):
            a, b = poly[k], poly[(k + 1) % len(poly)]
            sa, sb = side(a), side(b)
            if sa >= 0:
                out.append(a)
            if (sa >= 0) != (sb >= 0):
                s = sa / (sa - sb)
                out.append((a[0] + (b[0] - a[0]) * s, a[1] + (b[1] - a[1]) * s))
        poly = out
        if not poly:
            return 0.0, None
    if len(poly) < 3:
        return 0.0, None
    area = 0.5 * sum(poly[k][0] * poly[(k + 1) % len(poly)][1] - poly[(k + 1) % len(poly)][0] * poly[k][1]
                     for k in range(len(poly)))
    return area, (sum(p[0] for p in poly) / len(poly), sum(p[1] for p in poly) / len(poly))


def _weights(T, p):
    v0, v1, v2 = T[1] - T[0], T[2] - T[0], p - T[0]
    d00, d01, d11 = v0 @ v0, v0 @ v1, v1 @ v1
    d20, d21 = v2 @ v0, v2 @ v1
    den = d00 * d11 - d01 * d01 or 1.0
    v = (d11 * d20 - d01 * d21) / den
    w = (d00 * d21 - d01 * d20) / den
    return np.array([1 - v - w, v, w])


def _texel(tex, uv):
    h, w = tex.shape[:2]
    return tex[int(math.floor(uv[1] * h)) % h, int(math.floor(uv[0] * w)) % w, :3].astype(int)


def overlaps(tris, names, uvs=None, eps=0.001, min_area=1e-6, ground=0.0, tol=0.002, tex=None):
    """{'zfight': [...], 'faint': [...], 'hidden': [...], 'back_to_back': [...]}, each pair as
    (node_a, node_b, area m^2, gap m, point), summed per node pair, largest first."""
    tris = np.asarray(tris, float)
    n = len(tris)
    out = {"zfight": {}, "hidden": {}, "back_to_back": {}}
    if n == 0:
        return {k: [] for k in ("zfight", "faint", "hidden", "back_to_back")}
    cr = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    area2 = np.linalg.norm(cr, axis=1)
    nor = cr / np.maximum(area2, 1e-12)[:, None]
    lo = tris.min(axis=1) - eps
    hi = tris.max(axis=1) + eps
    size = np.sort((hi - lo).max(axis=1))[n // 2]
    cell = min(5.0, max(0.01, 2 * size))
    grid = {}
    for t in range(n):
        a, b = np.floor(lo[t] / cell).astype(int), np.floor(hi[t] / cell).astype(int)
        for x in range(a[0], b[0] + 1):
            for y in range(a[1], b[1] + 1):
                for z in range(a[2], b[2] + 1):
                    grid.setdefault((x, y, z), []).append(t)
    under = (nor[:, 1] < -0.9) & (np.abs(tris[:, 0, 1] - ground) <= tol) if ground is not None else np.zeros(n, bool)
    for ta in range(n):
        if area2[ta] < 1e-12 or under[ta]:
            continue
        a, b = np.floor(lo[ta] / cell).astype(int), np.floor(hi[ta] / cell).astype(int)
        cand = set()
        for x in range(a[0], b[0] + 1):
            for y in range(a[1], b[1] + 1):
                for z in range(a[2], b[2] + 1):
                    cand.update(grid.get((x, y, z), ()))
        A = tris[ta]
        for tb in cand:
            if tb <= ta or area2[tb] < 1e-12:
                continue
            facing = nor[ta] @ nor[tb]
            if abs(facing) < PARALLEL:
                continue
            gap = np.abs((tris[tb] - A[0]) @ nor[ta]).max()
            if gap > eps:
                continue
            opposite = facing < 0
            if opposite and all(np.linalg.norm(tris[tb] - p, axis=1).min() <= 2 * eps for p in A):
                continue  # a two-sided card
            u = (A[1] - A[0]) / np.linalg.norm(A[1] - A[0])
            v = np.cross(nor[ta], u)
            flat = lambda T: [((p - A[0]) @ u, (p - A[0]) @ v) for p in T]
            area, c = _clip_area(flat(A), flat(tris[tb]))
            if area <= min_area or area <= 1e-3 * min(area2[ta], area2[tb]) / 2:
                continue
            at = A[0] + u * c[0] + v * c[1]
            kind = "back_to_back"
            if not opposite:
                kind = "zfight"
                if uvs is not None:
                    ua = _weights(A, at) @ uvs[ta]
                    ub = _weights(tris[tb], at) @ uvs[tb]
                    if tex is not None:
                        same = np.abs(_texel(tex, ua) - _texel(tex, ub)).max() <= 8
                    else:
                        same = np.abs(ua - ub).max() <= 1 / 512
                    if same:
                        kind = "hidden"
            key = tuple(sorted((names[ta], names[tb])))
            e = out[kind].setdefault(key, [key[0], key[1], 0.0, 0.0, at])
            e[2] += area
            e[3] = max(e[3], gap)
    res = {k: sorted(v.values(), key=lambda e: -e[2]) for k, v in out.items()}
    fights = res.pop("zfight")
    res["zfight"] = [e for e in fights if visible_fight(e[2], e[3])]
    res["faint"] = [e for e in fights if not visible_fight(e[2], e[3])]
    return res


def gpu_vertices(g):
    """(vertices the GPU transforms, distinct positions) over every mesh of the file."""
    verts, seen = 0, set()
    for m in g.js.get("meshes", []):
        for prim in m["primitives"]:
            P = g.acc(prim["attributes"]["POSITION"]).astype(float)
            verts += len(P)
            seen.update(map(tuple, np.round(P * 1e5).astype(np.int64).tolist()))
    return verts, len(seen)
