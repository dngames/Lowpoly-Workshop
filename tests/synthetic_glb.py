"""First-party synthetic GLB builder for tests: nodes (TRS, matrix, children), meshes with vertex colours,
UVs, materials and an embedded image, skins and animations. Nothing here comes from a third-party model."""
import io
import json
import struct
from pathlib import Path

import numpy as np

CTYPES = {"f4": 5126, "u1": 5121, "u2": 5123, "u4": 5125, "i2": 5122, "i1": 5120}
KINDS = {1: "SCALAR", 2: "VEC2", 3: "VEC3", 4: "VEC4", 16: "MAT4"}


class GlbBuilder:
    def __init__(self):
        self.bin = bytearray()
        self.views, self.accessors = [], []
        self.nodes, self.meshes, self.materials, self.skins, self.animations = [], [], [], [], []
        self.images, self.textures = [], []
        self.roots = []

    def blob(self, data):
        self.bin += b"\0" * ((4 - len(self.bin) % 4) % 4)
        self.views.append({"buffer": 0, "byteOffset": len(self.bin), "byteLength": len(data)})
        self.bin += data
        return len(self.views) - 1

    def accessor(self, array, dtype, normalized=False):
        a = np.asarray(array, dtype=dtype)
        a = a.reshape(len(a), -1)
        spec = {"bufferView": self.blob(a.tobytes()), "componentType": CTYPES[np.dtype(dtype).str[1:]],
                "count": len(a), "type": KINDS[a.shape[1]]}
        if normalized:
            spec["normalized"] = True
        self.accessors.append(spec)
        return len(self.accessors) - 1

    def material(self, factor=None, image=None, extensions=None):
        pbr = {}
        if factor is not None:
            pbr["baseColorFactor"] = list(factor)
        if image is not None:
            buf = io.BytesIO()
            image.save(buf, format="PNG")
            self.images.append({"bufferView": self.blob(buf.getvalue()), "mimeType": "image/png"})
            self.textures.append({"source": len(self.images) - 1})
            pbr["baseColorTexture"] = {"index": len(self.textures) - 1}
        m = {"pbrMetallicRoughness": pbr}
        if extensions:
            m["extensions"] = extensions
        self.materials.append(m)
        return len(self.materials) - 1

    def mesh(self, prims):
        """prims: dicts with pos, tri and optional color=(array, dtype), uv, material, joints=(array, dtype),
        weights=(array, dtype)."""
        out = []
        for p in prims:
            attrs = {"POSITION": self.accessor(p["pos"], "<f4")}
            if "color" in p:
                arr, dtype = p["color"]
                attrs["COLOR_0"] = self.accessor(arr, dtype, normalized=np.dtype(dtype).kind == "u")
            if "uv" in p:
                attrs["TEXCOORD_0"] = self.accessor(p["uv"], "<f4")
            if "joints" in p:
                attrs["JOINTS_0"] = self.accessor(*p["joints"])
                attrs["WEIGHTS_0"] = self.accessor(*p["weights"], normalized=np.dtype(p["weights"][1]).kind == "u")
            entry = {"attributes": attrs, "indices": self.accessor(np.asarray(p["tri"]).ravel(), "<u4")}
            if "material" in p:
                entry["material"] = p["material"]
            out.append(entry)
        self.meshes.append({"primitives": out})
        return len(self.meshes) - 1

    def node(self, name=None, mesh=None, skin=None, translation=None, rotation=None, scale=None, matrix=None,
             children=(), root=True):
        n = {}
        for key, value in (("name", name), ("mesh", mesh), ("skin", skin), ("translation", translation),
                           ("rotation", rotation), ("scale", scale), ("matrix", matrix)):
            if value is not None:
                n[key] = value
        if children:
            n["children"] = list(children)
        self.nodes.append(n)
        if root:
            self.roots.append(len(self.nodes) - 1)
        return len(self.nodes) - 1

    def skin(self, joints, ibm=None):
        s = {"joints": list(joints)}
        if ibm is not None:  # row-major 4x4 matrices; glTF stores them column-major
            s["inverseBindMatrices"] = self.accessor(np.asarray(ibm, "<f4").transpose(0, 2, 1).reshape(len(ibm), 16), "<f4")
        self.skins.append(s)
        return len(self.skins) - 1

    def animation(self, name, node):
        t = self.accessor([0.0, 1.0], "<f4")
        v = self.accessor([[0, 0, 0], [0, 1, 0]], "<f4")
        self.animations.append({"name": name, "samplers": [{"input": t, "output": v}],
                                "channels": [{"sampler": 0, "target": {"node": node, "path": "translation"}}]})

    def write(self, path):
        js = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": self.roots}], "nodes": self.nodes,
              "buffers": [{"byteLength": len(self.bin)}], "bufferViews": self.views, "accessors": self.accessors}
        for key, items in (("meshes", self.meshes), ("materials", self.materials), ("skins", self.skins),
                           ("animations", self.animations), ("images", self.images), ("textures", self.textures)):
            if items:
                js[key] = items
        text = json.dumps(js, separators=(",", ":")).encode()
        text += b" " * ((4 - len(text) % 4) % 4)
        binc = bytes(self.bin) + b"\0" * ((4 - len(self.bin) % 4) % 4)
        total = 12 + 8 + len(text) + 8 + len(binc)
        Path(path).write_bytes(struct.pack("<III", 0x46546C67, 2, total) + struct.pack("<II", len(text), 0x4E4F534A)
                               + text + struct.pack("<II", len(binc), 0x004E4942) + binc)
        return Path(path)


def box(lo, hi):
    """(positions (8,3), triangles (12,3)) of a closed outward-facing cuboid."""
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    pos = np.array([[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],
                    [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]], float)
    tri = np.array([[0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7], [0, 1, 5], [0, 5, 4],
                    [3, 6, 2], [3, 7, 6], [0, 4, 7], [0, 7, 3], [1, 2, 6], [1, 6, 5]])
    return pos, tri


def disc(radius, y0, y1, n=16):
    """A closed cylinder standing between y0 and y1, centred on the Y axis."""
    ang = np.linspace(0, 2 * np.pi, n, endpoint=False)
    ring = np.stack([radius * np.cos(ang), np.zeros(n), radius * np.sin(ang)], 1)
    pos = np.concatenate([ring + [0, y0, 0], ring + [0, y1, 0], [[0, y0, 0], [0, y1, 0]]])
    tri = []
    for k in range(n):
        a, b = k, (k + 1) % n
        tri += [[a, b, n + b], [a, n + b, n + a], [2 * n, b, a], [2 * n + 1, n + a, n + b]]
    return pos, np.array(tri)


def single_mesh(path, pos, tri, **extra):
    """One mesh node 'Model' with one primitive; `extra` keys go to the primitive (color, uv, material...)."""
    g = GlbBuilder()
    g.node("Model", mesh=g.mesh([dict(pos=pos, tri=tri, **extra)]))
    return g.write(path)
