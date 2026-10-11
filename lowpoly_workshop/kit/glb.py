"""Read glTF binaries without trusting the exporter, pose their node trees, and test intersections.

    g = Glb("bike.glb")
    loc = g.sample(0.0, anim=None)            # local (R, T) per node: rest values, or a clip at time t
    geo, world = g.posed(loc)                 # world-space triangles per mesh node, world transforms
    hits = intersect(geo["Fork"], geo["Frame"])
"""
import io
from pathlib import Path
import json
import math
import struct

import numpy as np

CTYPE = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4":16}


def load_glb(path):
    data = Path(path).read_bytes()
    if len(data)<12:raise ValueError("Truncated GLB header")
    magic, ver, length = struct.unpack_from("<III", data, 0)
    if magic != 0x46546C67 or ver != 2 or length != len(data):raise ValueError("Invalid GLB header or length")
    off, js, binc = 12, None, b""
    while off < length:
        if off+8>length:raise ValueError("Truncated GLB chunk header")
        clen, ctype = struct.unpack_from("<II", data, off)
        if clen%4 or off+8+clen>length:raise ValueError("Invalid GLB chunk length")
        chunk = data[off + 8:off + 8 + clen]
        if ctype == 0x4E4F534A:
            js = json.loads(chunk)
        elif ctype == 0x004E4942:
            binc = chunk
        off += 8 + clen
    if js is None:raise ValueError("GLB JSON chunk missing")
    return js, binc


def accessor(js, binc, i):
    a = js["accessors"][i]
    bv = js["bufferViews"][a["bufferView"]]
    dt = np.dtype(CTYPE[a["componentType"]])
    n = NCOMP[a["type"]]
    start = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
    stride = bv.get("byteStride", 0) or dt.itemsize * n
    raw = np.frombuffer(binc, np.uint8, count=stride * (a["count"] - 1) + dt.itemsize * n, offset=start)
    rows = np.lib.stride_tricks.as_strided(raw, (a["count"], dt.itemsize * n), (stride, 1))
    return np.frombuffer(rows.copy().tobytes(), dt).reshape(a["count"], n)


def rot_mat(axis, deg):
    a = np.asarray(axis, float) / np.linalg.norm(axis)
    t = math.radians(deg)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(t) * K + (1 - math.cos(t)) * K @ K


def seg_tri_hits(P0, P1, A, B, C, eps=2e-4):
    """Vectorised segment/triangle crossing test (Moller-Trumbore), pairs aligned."""
    d = P1 - P0
    e1, e2 = B - A, C - A
    h = np.cross(d, e2)
    det = np.einsum("ij,ij->i", e1, h)
    ok = np.abs(det) > 1e-12
    inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
    s = P0 - A
    u = np.einsum("ij,ij->i", s, h) * inv
    q = np.cross(s, e1)
    v = np.einsum("ij,ij->i", d, q) * inv
    t = np.einsum("ij,ij->i", e2, q) * inv
    L = np.linalg.norm(d, axis=1) + 1e-12
    m = eps / L
    return ok & (u > 1e-4) & (v > 1e-4) & (u + v < 1 - 1e-4) & (t > m) & (t < 1 - m)


def intersect(TA, TB, eps=2e-4):
    """Number of intersecting triangle pairs between two triangle soups (T,3,3)."""
    if not len(TA) or not len(TB):
        return 0
    loA, hiA = TA.min(1), TA.max(1)
    loB, hiB = TB.min(1), TB.max(1)
    if (loA.min(0) > hiB.max(0)).any() or (loB.min(0) > hiA.max(0)).any():
        return 0
    hits = 0
    for s in range(0, len(TA), 256):
        la, ha = loA[s:s + 256, None], hiA[s:s + 256, None]
        ov = np.all((la <= hiB[None] + eps) & (loB[None] <= ha + eps), -1)
        ia, ib = np.nonzero(ov)
        if not len(ia):
            continue
        ia = ia + s
        a, b = TA[ia], TB[ib]
        hit = np.zeros(len(ia), bool)
        for k in range(3):
            hit |= seg_tri_hits(a[:, k], a[:, (k + 1) % 3], b[:, 0], b[:, 1], b[:, 2], eps)
            hit |= seg_tri_hits(b[:, k], b[:, (k + 1) % 3], a[:, 0], a[:, 1], a[:, 2], eps)
        hits += int(hit.sum())
    return hits


def quat_to_m(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


class Glb:
    def __init__(self, path):
        self.js, self.bin = load_glb(path)
        self.path = path
        self.nodes = self.js["nodes"]
        self.names = [n.get("name") for n in self.nodes]
        self.parent = {}
        for i, n in enumerate(self.nodes):
            for c in n.get("children", []):
                self.parent[c] = i

    def acc(self, i):
        return accessor(self.js, self.bin, i)

    def local_geo(self, i):
        n = self.nodes[i]
        tris = []
        for prim in self.js["meshes"][n["mesh"]]["primitives"]:
            P = self.acc(prim["attributes"]["POSITION"]).astype(float)
            idx = self.acc(prim["indices"]).ravel()
            tris.append(P[idx.reshape(-1, 3)])
        return np.concatenate(tris)

    def sample(self, t=0.0, anim=None):
        """Local (R, T) per node at time t of an animation (rest values where not animated)."""
        loc = {}
        for i, n in enumerate(self.nodes):
            R = quat_to_m(n.get("rotation", [0, 0, 0, 1]))
            T = np.array(n.get("translation", [0, 0, 0]), float)
            loc[i] = [R, T]
        if anim is None or not self.js.get("animations"):
            return loc
        a = self.js["animations"][anim]
        for ch in a["channels"]:
            s = a["samplers"][ch["sampler"]]
            ti = self.acc(s["input"]).ravel()
            vo = self.acc(s["output"])
            k = int(np.clip(np.searchsorted(ti, t) - 1, 0, len(ti) - 2))
            f = float(np.clip((t - ti[k]) / max(ti[k + 1] - ti[k], 1e-9), 0, 1))
            v = vo[k] * (1 - f) + vo[k + 1] * f
            node, path = ch["target"]["node"], ch["target"]["path"]
            if path == "rotation":
                v = v / np.linalg.norm(v)
                loc[node][0] = quat_to_m(v)
            elif path == "translation":
                loc[node][1] = v
        return loc

    def world(self, loc):
        out = {}

        def get(i):
            if i in out:
                return out[i]
            R, T = loc[i]
            if i in self.parent:
                PR, PT = get(self.parent[i])
                out[i] = (PR @ R, PR @ T + PT)
            else:
                out[i] = (R, T)
            return out[i]
        for i in range(len(self.nodes)):
            get(i)
        return out

    def posed(self, loc, skip=()):
        W = self.world(loc)
        geo = {}
        for i, n in enumerate(self.nodes):
            if "mesh" not in n or n["name"] in skip:
                continue
            R, T = W[i]
            geo[n["name"]] = self.local_geo(i) @ R.T + T
        return geo, W

    def extras(self, name):
        return self.nodes[self.names.index(name)].get("extras", {})

    def images(self):
        from PIL import Image
        out = []
        for im in self.js.get("images", []):
            bv = self.js["bufferViews"][im["bufferView"]]
            o = bv.get("byteOffset", 0)
            out.append(Image.open(io.BytesIO(self.bin[o:o + bv["byteLength"]])))
        return out

    def anim_index(self, name):
        for k, a in enumerate(self.js.get("animations", [])):
            if a.get("name") == name:
                return k
        return None

    def thin_mask(self, i):
        """Per-triangle _THIN flags of a mesh node (False where the attribute is missing)."""
        out = []
        for prim in self.js["meshes"][self.nodes[i]["mesh"]]["primitives"]:
            idx = self.acc(prim["indices"]).ravel().reshape(-1, 3)
            if "_THIN" in prim["attributes"]:
                t = self.acc(prim["attributes"]["_THIN"]).ravel()
                out.append(t[idx].max(1) > 0.5)
            else:
                out.append(np.zeros(len(idx), bool))
        return np.concatenate(out)
