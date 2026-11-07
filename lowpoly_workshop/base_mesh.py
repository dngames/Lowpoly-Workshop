"""Start a project from an existing low-poly base mesh (any GLB) instead of generating one.

    lowpoly ASSET base import PATH --name base --licence ID --credit TEXT --front -z --height 1.0 [--budget 1500]
    lowpoly ASSET base status | palette | bake

`import` copies the source GLB unchanged to `inputs/base/<name>_source.glb`, writes a provenance ledger
(`<name>.json`), and writes the normalised mesh `<name>_lowpoly.glb` (+Z front, metres, +Y up, grounded at
Y = 0, centred in X/Z) with a JSON report. Normalising is plain numpy; headless Blender runs only when the
triangle count exceeds `--budget`.

`load_glb_node` turns a normalised (or any) GLB into generator nodes. Colours come from, in priority order,
the base-colour texture through `TEXCOORD_0`, the vertex colours `COLOR_0` (linear in glTF; converted to sRGB
and multiplied by the material's `baseColorFactor`), then the material's `baseColorFactor` alone.

Skinned meshes are posed at their rest pose by linear blend skinning and the skin is dropped; glTF ignores
the mesh node's own transform for a skinned mesh, so it is ignored here too.
"""
from dataclasses import dataclass, field, replace as _replace
from pathlib import Path
import datetime
import hashlib
import io
import json
import math
import os
import re
import tempfile

import numpy as np

from .kit.atomic import replacing, write_json
from .kit.glb import CTYPE, NCOMP, accessor, load_glb, quat_to_m, write_glb
from .spec import local_path

BASE_DIR = "inputs/base"
FRONTS = ("+z", "-z", "+x", "-x")
SAFE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")
COMPRESSED = ("KHR_draco_mesh_compression", "EXT_meshopt_compression")
MIN_TRIANGLES_PER_NODE = 4


# -- colour helpers

def srgb_to_linear(c):
    c = np.clip(np.asarray(c, float), 0.0, 1.0)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(c):
    c = np.clip(np.asarray(c, float), 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1.0 / 2.4) - 0.055)


def read_rgb_path(path):
    """An RGB image file as a uint8 array, or None when the file is missing (Pillow, else Blender's own loader)."""
    path = Path(path)
    if not path.is_file():
        return None
    try:
        from PIL import Image
        with Image.open(path) as im:
            return np.asarray(im.convert("RGB"), dtype=np.uint8)
    except ImportError:
        import bpy
        img = bpy.data.images.load(str(path), check_existing=False)
        try:
            w, h = img.size
            px = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, img.channels)
            return np.clip(px[::-1, :, :3] * 255.0 + 0.5, 0, 255).astype(np.uint8)
        finally:
            bpy.data.images.remove(img)


# -- reading glTF

def _dequantise(a, dtype):
    if dtype == np.uint8:
        return a / 255.0
    if dtype == np.uint16:
        return a / 65535.0
    if dtype == np.int8:
        return np.maximum(a / 127.0, -1.0)
    if dtype == np.int16:
        return np.maximum(a / 32767.0, -1.0)
    return a


def read_accessor(js, binc, index, normalise=None):
    """An accessor as an (count, components) array. Integers become 0..1 floats when `normalise` is true,
    or, left as None, when the accessor says `normalized`. An accessor without a buffer view is all zeros."""
    spec = js["accessors"][index]
    if spec.get("sparse"):
        raise ValueError("Sparse accessors are not supported")
    n, dt = NCOMP[spec["type"]], np.dtype(CTYPE[spec["componentType"]])
    if "bufferView" not in spec or spec["count"] == 0:
        a = np.zeros((spec["count"], n), dt)
    else:
        a = accessor(js, binc, index)
    want = spec.get("normalized", False) if normalise is None else normalise
    if want and dt.kind in "iu":
        return _dequantise(a.astype(np.float64), dt.type)
    return a


def node_matrix(node):
    """A glTF node's local 4x4 matrix (column vectors) from `matrix` or translation/rotation/scale."""
    if "matrix" in node:
        return np.asarray(node["matrix"], float).reshape(4, 4).T
    m = np.eye(4)
    m[:3, :3] = quat_to_m(node.get("rotation", [0, 0, 0, 1])) * np.asarray(node.get("scale", [1, 1, 1]), float)
    m[:3, 3] = node.get("translation", [0, 0, 0])
    return m


@dataclass
class Prim:
    """One triangle primitive in world space at the rest pose.

    col is (N, 4) linear vertex colour or None; uv is (N, 2) or None; factor is the linear baseColorFactor;
    image is an index into the scene's images when the base-colour texture applies."""
    node: int
    name: str
    pos: np.ndarray
    tri: np.ndarray
    col: object = None
    uv: object = None
    factor: np.ndarray = field(default_factory=lambda: np.ones(4))
    has_material: bool = False
    image: object = None
    skinned: bool = False

    def select(self, keep):
        """The primitive with only the triangles where `keep` is true, unused vertices removed."""
        tri = self.tri[keep]
        used = np.unique(tri)
        remap = np.full(len(self.pos), -1, np.int64)
        remap[used] = np.arange(len(used))
        return _replace(self, pos=self.pos[used], tri=remap[tri],
                       col=None if self.col is None else self.col[used],
                       uv=None if self.uv is None else self.uv[used])

    def moved(self, pos):
        return _replace(self, pos=pos)


class Scene:
    """What a GLB holds, posed at rest: primitives plus the facts a report needs."""

    def __init__(self, path):
        self.path = Path(path)
        self.js, self.bin = load_glb(path)
        js = self.js
        bad = [e for e in js.get("extensionsRequired", []) if e in COMPRESSED]
        if bad:
            raise ValueError(f"{self.path.name}: needs {bad[0]}; decompress the GLB first (compressed meshes are not read)")
        self.nodes = js.get("nodes", [])
        self.parent = {c: i for i, n in enumerate(self.nodes) for c in n.get("children", [])}
        self._world = {}
        self._images = {}
        self.warnings = []
        self.prims = []
        self._read()

    # transforms
    def world(self, i):
        if i not in self._world:
            chain, k = [], i
            while k is not None:
                if len(chain) > len(self.nodes):
                    raise ValueError("Node hierarchy has a cycle")
                chain.append(k)
                k = self.parent.get(k)
            m = np.eye(4)
            for k in reversed(chain):
                m = m @ node_matrix(self.nodes[k])
            self._world[i] = m
        return self._world[i]

    def node_name(self, i):
        return self.nodes[i].get("name") or ""

    def descendants(self, i):
        out, todo = set(), [i]
        while todo:
            k = todo.pop()
            if k not in out:
                out.add(k)
                todo.extend(self.nodes[k].get("children", []))
        return out

    # images
    def image_count(self):
        return len(self.js.get("images", []))

    def image_blob(self, i):
        """(bytes, mime type) of an embedded image, or None when it is not stored in the GLB."""
        im = self.js["images"][i]
        if "bufferView" not in im:
            return None
        bv = self.js["bufferViews"][im["bufferView"]]
        o = bv.get("byteOffset", 0)
        return bytes(self.bin[o:o + bv["byteLength"]]), im.get("mimeType", "image/png")

    def texture(self, i):
        """An embedded image as RGB uint8, or None when it cannot be decoded."""
        if i not in self._images:
            tex = None
            blob = self.image_blob(i)
            try:
                from PIL import Image
                if blob is not None:
                    tex = np.asarray(Image.open(io.BytesIO(blob[0])).convert("RGB"), dtype=np.uint8)
            except ImportError:
                tex = read_rgb_path(self.path.with_name("pixal3d_atlas.png"))
            self._images[i] = tex
        return self._images[i]

    # reading
    def _roots(self):
        scenes = self.js.get("scenes")
        if scenes:
            return list(scenes[self.js.get("scene", 0)].get("nodes", []))
        return [i for i in range(len(self.nodes)) if i not in self.parent]

    def _material(self, prim):
        index = prim.get("material")
        if index is None:
            return False, np.ones(4), None, 0
        pbr = self.js["materials"][index].get("pbrMetallicRoughness", {})
        factor = np.asarray(pbr.get("baseColorFactor", [1, 1, 1, 1]), float)
        image, coord = None, 0
        bct = pbr.get("baseColorTexture")
        if bct is not None and "source" in self.js["textures"][bct["index"]]:
            image, coord = self.js["textures"][bct["index"]]["source"], bct.get("texCoord", 0)
        return True, factor, image, coord

    def _skin_matrices(self, skin_index):
        skin = self.js["skins"][skin_index]
        joints = skin["joints"]
        if "inverseBindMatrices" in skin:
            ibm = read_accessor(self.js, self.bin, skin["inverseBindMatrices"], False).astype(float)
            ibm = ibm.reshape(-1, 4, 4).transpose(0, 2, 1)
        else:
            ibm = np.tile(np.eye(4), (len(joints), 1, 1))
        if len(ibm) < len(joints):
            raise ValueError("Skin has fewer inverse bind matrices than joints")
        return np.stack([self.world(j) @ ibm[k] for k, j in enumerate(joints)])

    def _skinned(self, attrs, pos, node_world, skin_index):
        joint_m = self._skin_matrices(skin_index)
        homo = np.concatenate([pos, np.ones((len(pos), 1))], 1)
        out, total = np.zeros((len(pos), 4)), np.zeros(len(pos))
        k = 0
        while f"JOINTS_{k}" in attrs and f"WEIGHTS_{k}" in attrs:
            joints = read_accessor(self.js, self.bin, attrs[f"JOINTS_{k}"], False).astype(np.int64)
            weights = read_accessor(self.js, self.bin, attrs[f"WEIGHTS_{k}"], True).astype(float)
            for slot in range(joints.shape[1]):
                w = weights[:, slot]
                use = w > 0
                if use.any():
                    j = np.clip(joints[use, slot], 0, len(joint_m) - 1)
                    out[use] += w[use, None] * np.einsum("nij,nj->ni", joint_m[j], homo[use])
                    total[use] += w[use]
            k += 1
        if k == 0:
            raise ValueError("Skinned primitive has no JOINTS_0/WEIGHTS_0")
        loose = total < 1e-8  # unweighted vertices follow the mesh node, as no joint moves them
        out[~loose] /= total[~loose, None]
        out[loose] = homo[loose] @ node_world.T
        return out[:, :3]

    def _read(self):
        js, binc = self.js, self.bin
        seen = set()
        todo = list(self._roots())
        order = []
        while todo:
            i = todo.pop(0)
            if i in seen:
                continue
            seen.add(i)
            order.append(i)
            todo = list(self.nodes[i].get("children", [])) + todo
        for i in sorted(order):
            node = self.nodes[i]
            if "mesh" not in node:
                continue
            world = self.world(i)
            flip = np.linalg.det(world[:3, :3]) < 0
            for prim in js["meshes"][node["mesh"]]["primitives"]:
                if "KHR_draco_mesh_compression" in prim.get("extensions", {}):
                    raise ValueError("Compressed (Draco) meshes are not read; decompress the GLB first")
                mode = prim.get("mode", 4)
                if mode not in (4, 5, 6):
                    self.warnings.append(f"{self.node_name(i) or i}: a point/line primitive was ignored")
                    continue
                if prim.get("targets"):
                    self.warnings.append(f"{self.node_name(i) or i}: morph targets ignored (base shape used)")
                attrs = prim["attributes"]
                pos = read_accessor(js, binc, attrs["POSITION"]).astype(float)
                if "indices" in prim:
                    idx = read_accessor(js, binc, prim["indices"], False).ravel().astype(np.int64)
                else:
                    idx = np.arange(len(pos))
                if mode == 5:
                    idx = np.array([idx[k:k + 3] if k % 2 == 0 else idx[[k + 1, k, k + 2]]
                                    for k in range(len(idx) - 2)], np.int64).ravel()
                elif mode == 6:
                    idx = np.array([[idx[0], idx[k], idx[k + 1]] for k in range(1, len(idx) - 1)], np.int64).ravel()
                tri = idx[: len(idx) // 3 * 3].reshape(-1, 3)
                if len(tri) and (tri.max() >= len(pos) or tri.min() < 0):
                    raise ValueError("Index outside the vertex range")
                skinned = "skin" in node and "JOINTS_0" in attrs
                if skinned:
                    pos = self._skinned(attrs, pos, world, node["skin"])
                    flip = False
                else:
                    pos = (np.concatenate([pos, np.ones((len(pos), 1))], 1) @ world.T)[:, :3]
                if flip:
                    tri = tri[:, [0, 2, 1]]
                has_mat, factor, image, coord = self._material(prim)
                uv = None
                for key in (f"TEXCOORD_{coord}", "TEXCOORD_0"):
                    if key in attrs:
                        uv = read_accessor(js, binc, attrs[key]).astype(float)
                        break
                if image is None and not has_mat and uv is not None and js.get("images"):
                    image = 0  # no material at all: the file's first image is its texture
                col = None
                if "COLOR_0" in attrs:
                    col = read_accessor(js, binc, attrs["COLOR_0"], True).astype(float)
                    col = np.clip(col, 0.0, 1.0)
                    if col.shape[1] == 3:
                        col = np.concatenate([col, np.ones((len(col), 1))], 1)
                if len(tri):
                    p = Prim(i, self.node_name(i), pos, tri, col, uv, factor, has_mat, image, skinned)
                    self.prims.append(p.select(np.ones(len(tri), bool)))
        if not any(len(p.tri) for p in self.prims):
            raise ValueError(f"No mesh triangles in {self.path}")

    # facts for the report
    def skin_info(self):
        joints = set()
        skins = self.js.get("skins", [])
        for skin in skins:
            joints.update(skin["joints"])
        return {"skinned_primitives": sum(1 for p in self.prims if p.skinned), "skins": len(skins),
                "joints": len(joints)}

    def animation_names(self):
        return [a.get("name") or f"animation_{k}" for k, a in enumerate(self.js.get("animations", []))]

    def ignored_extensions(self):
        used = set(self.js.get("extensionsUsed", []))
        return sorted(e for e in used if e.startswith("KHR_materials_") and e != "KHR_materials_emissive_strength")


def read_scene(path):
    return Scene(path)


# -- colours per triangle

def _centroid_texel(tex, uv):
    h, w = tex.shape[:2]
    c = np.clip(uv.mean(axis=1), 0.0, 1.0)
    px = np.clip(np.rint(c[:, 0] * (w - 1)).astype(int), 0, w - 1)
    py = np.clip(np.rint(c[:, 1] * (h - 1)).astype(int), 0, h - 1)
    return tex[py, px].astype(float)


def colour_source(scene, prim, order=("texture", "vertex", "factor")):
    """Which colour source applies to a primitive: 'texture', 'vertex', 'factor' or 'none'."""
    for kind in order:
        if kind == "texture" and prim.image is not None and prim.uv is not None and scene.texture(prim.image) is not None:
            return kind
        if kind == "vertex" and prim.col is not None:
            return kind
        if kind == "factor" and prim.has_material:
            return kind
    return "none"


def vertex_colours(scene, prim, order=("texture", "vertex", "factor")):
    """(sRGB 0..1 per vertex, source). Texture colours are sampled at each vertex's UV."""
    source = colour_source(scene, prim, order)
    n = len(prim.pos)
    if source == "texture":
        tex = scene.texture(prim.image) / 255.0
        h, w = tex.shape[:2]
        return tex[np.clip((prim.uv[:, 1] % 1.0 * h).astype(int), 0, h - 1),
                   np.clip((prim.uv[:, 0] % 1.0 * w).astype(int), 0, w - 1)], source
    if source == "vertex":
        return linear_to_srgb(prim.col[:, :3] * prim.factor[:3]), source
    if source == "factor":
        return np.tile(linear_to_srgb(prim.factor[:3]), (n, 1)), source
    return None, source


def triangle_colours(scene, prim, order=("texture", "vertex", "factor")):
    """(sRGB 0..255 per triangle, source). Vertex colours average in linear light, then convert."""
    source = colour_source(scene, prim, order)
    t = prim.tri
    if source == "texture":
        return _centroid_texel(scene.texture(prim.image), prim.uv[t]), source
    if source == "vertex":
        lin = (prim.col[:, :3] * prim.factor[:3])[t].mean(axis=1)
        return linear_to_srgb(lin) * 255.0, source
    if source == "factor":
        return np.tile(linear_to_srgb(prim.factor[:3]) * 255.0, (len(t), 1)), source
    return None, source


def colour_sources(scene):
    """{source: {"primitives": n, "triangles": n}} over every primitive of the scene."""
    out = {}
    for p in scene.prims:
        s = out.setdefault(colour_source(scene, p), {"primitives": 0, "triangles": 0})
        s["primitives"] += 1
        s["triangles"] += int(len(p.tri))
    return dict(sorted(out.items()))


# -- node layout

def sanitise_name(raw, fallback):
    name = re.sub(r"[^A-Za-z0-9_-]+", "_", raw or "").strip("_")
    return name or fallback


def unique_names(raws, fallback):
    """Sanitised names, made unique in order by a numeric suffix (`Leg`, `Leg_2`, ...)."""
    out, taken = [], set()
    for k, raw in enumerate(raws):
        base = sanitise_name(raw, f"{fallback}_{k}")
        name, n = base, 2
        while name in taken:
            name, n = f"{base}_{n}", n + 1
        taken.add(name)
        out.append(name)
    return out


def node_groups(prims, separate, merged_name):
    """[(name, source name, [prims])] in glTF node order, or one merged group."""
    if not separate:
        return [(merged_name, "", list(prims))]
    nodes = sorted({p.node for p in prims})
    raws = [next(p.name for p in prims if p.node == i) for i in nodes]
    return [(n, raw, [p for p in prims if p.node == i]) for i, n, raw in zip(nodes, unique_names(raws, merged_name), raws)]


# -- loader for gen.py

def _extract_glb_triangles_and_uvs(glb_path):
    """(triangles (T,3,3), per-corner uvs (T,3,2) or zeros, texture RGB or None) of every mesh in a GLB."""
    scene = read_scene(glb_path)
    tris, uvs, tex = [], [], None
    for p in scene.prims:
        tris.append(p.pos[p.tri])
        uvs.append(p.uv[p.tri] if p.uv is not None else np.zeros((len(p.tri), 3, 2)))
        if tex is None and p.image is not None:
            tex = scene.texture(p.image)
    return np.concatenate(tris), np.concatenate(uvs), tex


def _prim_faces(scene, prim, mode, atlas, flat_cells, flat_rgbs, default_cell):
    pts = prim.pos[prim.tri]
    area = np.linalg.norm(np.cross(pts[:, 1] - pts[:, 0], pts[:, 2] - pts[:, 0]), axis=1)
    keep = np.nonzero(area > 1e-10)[0]
    faces = []
    if mode == "palette":
        rgb, source = triangle_colours(scene, prim)
        if rgb is not None and flat_rgbs is not None and len(flat_cells) > 1:
            best = ((rgb[keep][:, None, :] - flat_rgbs[None]) ** 2).sum(axis=2).argmin(axis=1)
            chosen = [flat_cells[b] for b in best]
        else:
            chosen = [default_cell] * len(keep)
        for k, cell in zip(keep, chosen):
            faces.append((pts[k], cell, None, False))
        return faces
    uvs = prim.uv[prim.tri] if prim.uv is not None else np.zeros((len(prim.tri), 3, 2))
    for k in keep:
        uv_w = np.empty((3, 2), dtype=float)
        uv_w[:, 0] = np.clip(uvs[k][:, 0], 0.0, 1.0)
        uv_w[:, 1] = np.clip(1.0 - uvs[k][:, 1], 0.0, 1.0)
        uv_area = abs(np.linalg.det(np.stack([uv_w[1] - uv_w[0], uv_w[2] - uv_w[0]])))
        if uv_area < 1e-6:
            centre = np.clip(uv_w.mean(axis=0), 0.01, 0.98)
            uv_w = np.array([centre, [centre[0] + 0.005, centre[1]], [centre[0], centre[1] + 0.005]], dtype=float)
        faces.append((pts[k], default_cell, uv_w, False))
    return faces


def load_glb_node(
    glb_path,
    node_name="Model",
    atlas=None,
    cell=None,
    mode="palette",
    parent=None,
    pivot=(0.0, 0.0, 0.0),
    smooth=False,
    *,
    separate_nodes=False,
):
    """Load a `.glb` (a Pixal3D/Blender result or an imported base mesh) as a Workshop generator node dict.

    - `mode="palette"`: every triangle takes the nearest flat palette cell in `atlas` (`uv=None`) to its colour:
      the base-colour texture sampled through `TEXCOORD_0`, else the mean of its `COLOR_0` vertex colours
      (linear in glTF, converted to sRGB and multiplied by the material's `baseColorFactor`), else the
      material's `baseColorFactor`. A mesh with none of these takes the first flat cell. Flat cells guarantee
      zero decal UV distortion and full compatibility with flat palette/kit-mask contracts.
    - `mode="decal"`: assigns `cell` (a decal cell in `atlas`) and converts glTF `TEXCOORD_0` `(u, v)` to
      Workshop decal UVs `(u, 1 - v)` with non-degenerate fallback for any collapsed UV triangle.
    - `separate_nodes=True`: one Workshop node per glTF mesh node, named after it (sanitised, made unique),
      so a head or a weapon can be edited, replaced or dropped in `gen.py`. Otherwise one merged node.

    Skinned meshes are placed at their rest pose and the skin is dropped.
    """
    if mode not in ("palette", "decal"):
        raise ValueError("mode must be 'palette' or 'decal'")
    if atlas is None:
        raise ValueError("load_glb_node needs the generator's atlas")
    scene = read_scene(glb_path)
    flat_cells = [k for k, v in atlas.cells.items() if v[2] is None]
    flat_rgbs = np.array([atlas.rgb_of(k) for k in flat_cells], dtype=float) if flat_cells else None
    default_cell = cell or (flat_cells[0] if flat_cells else next(iter(atlas.cells)))
    nodes = {}
    for name, _, prims in node_groups(scene.prims, separate_nodes, node_name):
        faces = []
        for p in prims:
            faces.extend(_prim_faces(scene, p, mode, atlas, flat_cells, flat_rgbs, default_cell))
        if faces or not separate_nodes:
            nodes[name] = {"parent": parent, "pivot": np.asarray(pivot, dtype=float), "faces": faces,
                           "smooth": bool(smooth)}
    if not any(n["faces"] for n in nodes.values()):
        raise ValueError(f"No mesh triangles in {glb_path}")
    return nodes


# -- palette proposal

_HUES = (("red", 15), ("orange", 40), ("yellow", 68), ("green", 165), ("cyan", 200), ("blue", 255),
         ("purple", 295), ("pink", 340), ("red", 361))


def colour_name(rgb):
    """A plain name for an sRGB colour (0..255), such as `dark_red` or `light_grey`."""
    import colorsys
    r, g, b = (float(c) / 255.0 for c in rgb)
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    if s < 0.12 or v < 0.1:
        return "black" if v < 0.16 else "dark_grey" if v < 0.4 else "grey" if v < 0.7 else "light_grey" if v < 0.92 else "white"
    hue = next(name for name, top in _HUES if h * 360 < top)
    if hue == "orange" and v < 0.62:
        hue = "brown"
    if hue == "yellow" and v < 0.55:
        hue = "olive"
    return ("dark_" if v < 0.4 else "light_" if v > 0.85 and s < 0.5 else "") + hue


def _median_cut(colours, weights, cells):
    boxes = [np.arange(len(colours))]
    while len(boxes) < cells:
        best, score = None, 0.0
        for k, b in enumerate(boxes):
            if len(b) < 2:
                continue
            spread = np.ptp(colours[b], axis=0).max()
            if spread * weights[b].sum() > score:
                best, score = k, spread * weights[b].sum()
        if best is None:
            break
        b = boxes.pop(best)
        axis = int(np.ptp(colours[b], axis=0).argmax())
        order = b[np.argsort(colours[b][:, axis], kind="stable")]
        cum = np.cumsum(weights[order])
        cut = int(np.clip(np.searchsorted(cum, cum[-1] / 2), 0, len(order) - 2))
        boxes += [order[: cut + 1], order[cut + 1:]]
    return boxes


def propose_palette(source, cells=8, order=("texture", "vertex", "factor")):
    """Propose `cells` flat palette cells from a base mesh's own colours (area-weighted median cut, then a
    few k-means passes). `source` is a GLB path or a `Scene`. Returns [{"name", "hex", "share"}], largest first;
    fewer cells come back when the mesh has fewer distinct colours. Feed it to `Atlas` with `palette_cells`."""
    if cells < 1:
        raise ValueError("cells must be at least 1")
    scene = source if isinstance(source, Scene) else read_scene(source)
    rgb, area = [], []
    for p in scene.prims:
        c, _ = triangle_colours(scene, p, order)
        if c is None:
            continue
        t = p.pos[p.tri]
        rgb.append(np.rint(c))
        area.append(np.linalg.norm(np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]), axis=1) / 2)
    if not rgb:
        raise ValueError("The mesh has no colours (no texture, COLOR_0 or material colour) to propose a palette from")
    rgb, area = np.concatenate(rgb), np.concatenate(area)
    keep = area > 1e-14
    rgb, area = rgb[keep], area[keep]
    uniq, inv = np.unique(rgb, axis=0, return_inverse=True)
    weight = np.zeros(len(uniq))
    np.add.at(weight, inv.ravel(), area)
    boxes = _median_cut(uniq, weight, cells)
    centres = np.array([(uniq[b] * weight[b, None]).sum(0) / weight[b].sum() for b in boxes])
    for _ in range(8):
        near = ((uniq[:, None, :] - centres[None]) ** 2).sum(2).argmin(1)
        for k in range(len(centres)):
            m = near == k
            if m.any():
                centres[k] = (uniq[m] * weight[m, None]).sum(0) / weight[m].sum()
    near = ((uniq[:, None, :] - centres[None]) ** 2).sum(2).argmin(1)
    merged = {}
    for k, c in enumerate(np.clip(np.rint(centres), 0, 255).astype(int)):
        share = float(weight[near == k].sum())
        if share > 0:
            key = tuple(int(v) for v in c)
            merged[key] = merged.get(key, 0.0) + share
    ranked = sorted(merged.items(), key=lambda kv: (-kv[1], kv[0]))
    names = unique_names([colour_name(c) for c, _ in ranked], "colour")
    total = sum(merged.values())
    return [{"name": n, "hex": "#%02x%02x%02x" % c, "share": round(s / total, 4)} for n, (c, s) in zip(names, ranked)]


def palette_cells(proposal, channels=()):
    """`Atlas` cells from a proposal: {name: (hex, kit channel or None)}; `channels` go to the largest cells."""
    return {p["name"]: (p["hex"], channels[k] if k < len(channels) else None) for k, p in enumerate(proposal)}


# -- normalising

def front_matrix(front):
    """Rotation about +Y that turns the model's `front` direction into +Z."""
    front = _front(front)
    return {"+z": np.eye(3),
            "-z": np.array([[-1.0, 0, 0], [0, 1, 0], [0, 0, -1]]),
            "+x": np.array([[0.0, 0, -1], [0, 1, 0], [1, 0, 0]]),
            "-x": np.array([[0.0, 0, 1], [0, 1, 0], [-1, 0, 0]])}[front]


def _front(front):
    f = str(front).strip().lower()
    f = f if f[:1] in "+-" else "+" + f
    if f not in FRONTS:
        raise ValueError(f"front must be one of {', '.join(FRONTS)}")
    return f


def bounds_of(prims):
    pts = np.concatenate([p.pos for p in prims])
    return pts.min(axis=0), pts.max(axis=0)


def triangle_count(prims):
    return int(sum(len(p.tri) for p in prims))


def rotate(prims, front):
    r = front_matrix(front)
    return [p.moved(p.pos @ r.T) for p in prims]


def ground_and_centre(prims, height=None):
    """Scale so the model is `height` tall (when given), put its lowest point on Y = 0 and centre X/Z."""
    lo, hi = bounds_of(prims)
    scale = 1.0
    if height is not None:
        if hi[1] - lo[1] <= 1e-9:
            raise ValueError("The mesh has no height to scale")
        scale = float(height) / float(hi[1] - lo[1])
    shift = np.array([(lo[0] + hi[0]) / 2, lo[1], (lo[2] + hi[2]) / 2])
    return [p.moved((p.pos - shift) * scale) for p in prims], scale


def drop_nodes(scene, prims, names):
    """Remove every primitive under the glTF nodes called `names`. Returns (kept, [{"name", "triangles"}])."""
    wanted = list(dict.fromkeys(names))
    drop, report = set(), []
    for name in wanted:
        hits = [i for i in range(len(scene.nodes)) if scene.node_name(i) == name]
        if not hits:
            have = sorted({p.name for p in prims if p.name})
            raise ValueError(f"No glTF node named {name!r}; mesh nodes are {have}")
        under = set().union(*(scene.descendants(i) for i in hits))
        gone = [p for p in prims if p.node in under]
        if not gone:
            raise ValueError(f"glTF node {name!r} carries no mesh to drop")
        drop |= under
        report.append({"name": name, "triangles": triangle_count(gone), "reason": "drop-node"})
    kept = [p for p in prims if p.node not in drop]
    if not kept:
        raise ValueError("Dropping those nodes would leave no geometry")
    return kept, report


class PlinthRefused(ValueError):
    """Raised when `--drop-plinth` cannot find a base it is sure about."""


def _components(prims):
    """Per primitive, a connected-component id of each triangle (vertices welded by position, across primitives)."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    pts = np.concatenate([p.pos for p in prims])
    span = float(np.ptp(pts, axis=0).max()) or 1.0
    _, weld = np.unique(np.round(pts / (span * 1e-6)).astype(np.int64), axis=0, return_inverse=True)
    weld = weld.ravel()
    offsets = np.cumsum([0] + [len(p.pos) for p in prims])
    tris = np.concatenate([p.tri + o for p, o in zip(prims, offsets)])
    w = weld[tris]
    n = int(weld.max()) + 1
    edges = np.concatenate([w[:, [0, 1]], w[:, [1, 2]]])
    graph = coo_matrix((np.ones(len(edges)), (edges[:, 0], edges[:, 1])), shape=(n, n))
    _, label = connected_components(graph, directed=False)
    tri_label = label[w[:, 0]]
    out, k = [], 0
    for p in prims:
        out.append(tri_label[k:k + len(p.tri)])
        k += len(p.tri)
    return out


def _plinth_check(part_lo, part_hi, rest_lo, rest_hi, lo_all, hi_all):
    """Why a candidate is not a plinth, or None when it is one (all rules must hold)."""
    height = hi_all[1] - lo_all[1]
    ph = part_hi[1] - part_lo[1]
    ext = part_hi[[0, 2]] - part_lo[[0, 2]]
    if ph > 0.3 * height:
        return f"it is {ph / height:.0%} of the model's height (a plinth is at most 30%)"
    if ph * 3 > ext.min():
        return f"it is not much wider than tall (height {ph:.4g} m, narrowest width {ext.min():.4g} m)"
    if abs(rest_lo[1] - part_hi[1]) > 0.05 * height:
        return "the rest of the model does not sit on its top"
    tol = 0.05 * ext.max()
    if (rest_lo[[0, 2]] < part_lo[[0, 2]] - tol).any() or (rest_hi[[0, 2]] > part_hi[[0, 2]] + tol).any():
        return "the rest of the model overhangs it"
    return None


def detect_plinth(scene, prims):
    """Find a display plinth: the lowest glTF node, else the lowest connected component, that is much wider
    than tall and sits under everything else. Returns (kept prims, report). Raises `PlinthRefused` rather than
    guess when the model is a single piece, when more than one piece reaches the lowest level, or when the
    lowest piece does not look like a base."""
    lo_all, hi_all = bounds_of(prims)
    height = hi_all[1] - lo_all[1]
    if height <= 1e-9:
        raise PlinthRefused("the model has no height")
    reasons = []

    def attempt(kind, parts):
        # parts: [(label, [(prim index, triangle mask)])]
        if len(parts) < 2:
            reasons.append(f"{kind}: only one piece")
            return None
        spans = []
        for label, sel in parts:
            pts = np.concatenate([prims[i].pos[prims[i].tri[m]].reshape(-1, 3) for i, m in sel])
            spans.append((pts.min(axis=0), pts.max(axis=0)))
        order = sorted(range(len(parts)), key=lambda k: (spans[k][0][1], spans[k][1][1]))
        c = order[0]
        for k in order[1:]:
            if spans[k][0][1] - spans[c][0][1] <= 0.02 * height:
                reasons.append(f"{kind}: more than one piece reaches the lowest level ({parts[c][0]!r} and {parts[k][0]!r})")
                return None
        rest_lo = np.min([spans[k][0] for k in order[1:]], axis=0)
        rest_hi = np.max([spans[k][1] for k in order[1:]], axis=0)
        why = _plinth_check(spans[c][0], spans[c][1], rest_lo, rest_hi, lo_all, hi_all)
        if why:
            reasons.append(f"{kind}: the lowest piece {parts[c][0]!r} is not a plinth: {why}")
            return None
        return c, parts[c], spans[c]

    by_node = {}
    for i, p in enumerate(prims):
        by_node.setdefault(p.node, []).append((i, np.ones(len(p.tri), bool)))
    node_parts = [(prims[sel[0][0]].name or f"node {n}", sel) for n, sel in sorted(by_node.items())]
    kind, found = "node", attempt("node", node_parts)
    if found is None:
        labels = _components(prims)
        count = int(max((l.max() for l in labels if len(l)), default=-1)) + 1
        comp_parts = []
        for c in range(count):
            sel = [(i, labels[i] == c) for i in range(len(prims)) if (labels[i] == c).any()]
            names = sorted({prims[i].name or f"node {prims[i].node}" for i, _ in sel})
            comp_parts.append((f"component of {'/'.join(names)}", sel))
        kind, found = "component", attempt("component", comp_parts)
    if found is None:
        raise PlinthRefused("no plinth removed: " + "; ".join(reasons) + ". Name the node with --drop-node instead.")
    _, (label, sel), (lo, hi) = found
    drop = {i: m for i, m in sel}
    kept, gone = [], 0
    for i, p in enumerate(prims):
        if i in drop:
            gone += int(drop[i].sum())
            if (~drop[i]).any():
                kept.append(p.select(~drop[i]))
        else:
            kept.append(p)
    ph = float(hi[1] - lo[1])
    report = {"name": label, "triangles": gone, "reason": f"plinth-{kind}",
              "height_m": round(ph, 5), "width_m": [round(float(v), 5) for v in (hi - lo)[[0, 2]]],
              "share_of_height": round(ph / float(height), 4)}
    return kept, report


# -- writing GLBs

class _Buffer:
    def __init__(self):
        self.data = bytearray()
        self.views, self.accessors = [], []

    def view(self, blob, target=None):
        self.data += b"\0" * ((4 - len(self.data) % 4) % 4)
        v = {"buffer": 0, "byteOffset": len(self.data), "byteLength": len(blob)}
        if target:
            v["target"] = target
        self.data += blob
        self.views.append(v)
        return len(self.views) - 1

    def array(self, a, ctype, kind, target=34962, bounds=False):
        a = np.ascontiguousarray(a)
        acc = {"bufferView": self.view(a.tobytes(), target), "componentType": ctype, "count": int(len(a)), "type": kind}
        if bounds:
            acc["min"], acc["max"] = a.min(axis=0).astype(float).tolist(), a.max(axis=0).astype(float).tolist()
        self.accessors.append(acc)
        return len(self.accessors) - 1


def write_prims_glb(path, groups, scene=None, generator="Lowpoly Workshop base import"):
    """Write [(node name, source name, [Prim])] as a GLB: one node and mesh per group, no skin, no animation.
    Vertex colours, UVs, base-colour factors and embedded base-colour textures carry over."""
    buf = _Buffer()
    materials, mat_key, textures, images, image_of = [], {}, [], [], {}
    meshes, nodes = [], []
    for name, raw, prims in groups:
        out = []
        for p in prims:
            if not len(p.tri):
                continue
            attrs = {"POSITION": buf.array(p.pos.astype(np.float32), 5126, "VEC3", bounds=True)}
            tex_index = None
            blob = scene.image_blob(p.image) if (scene is not None and p.image is not None and p.uv is not None) else None
            if blob is not None:
                attrs["TEXCOORD_0"] = buf.array(p.uv.astype(np.float32), 5126, "VEC2")
                if p.image not in image_of:
                    images.append({"bufferView": buf.view(blob[0]), "mimeType": blob[1]})
                    textures.append({"source": len(images) - 1})
                    image_of[p.image] = len(textures) - 1
                tex_index = image_of[p.image]
            if p.col is not None:
                attrs["COLOR_0"] = buf.array(p.col.astype(np.float32), 5126, "VEC4")
            entry = {"attributes": attrs}
            if p.has_material or tex_index is not None:
                key = (tuple(np.round(p.factor, 6).tolist()), tex_index)
                if key not in mat_key:
                    pbr = {"baseColorFactor": [float(v) for v in key[0]], "metallicFactor": 0.0, "roughnessFactor": 1.0}
                    if tex_index is not None:
                        pbr["baseColorTexture"] = {"index": tex_index}
                    materials.append({"name": f"material_{len(materials)}", "pbrMetallicRoughness": pbr})
                    mat_key[key] = len(materials) - 1
                entry["material"] = mat_key[key]
            idx = p.tri.astype(np.uint16 if len(p.pos) < 65535 else np.uint32).ravel()
            entry["indices"] = buf.array(idx, 5123 if idx.dtype == np.uint16 else 5125, "SCALAR", target=34963)
            out.append(entry)
        if not out:
            continue
        meshes.append({"name": name, "primitives": out})
        node = {"name": name, "mesh": len(meshes) - 1}
        if raw and raw != name:
            node["extras"] = {"source_name": raw}
        nodes.append(node)
    if not nodes:
        raise ValueError("Nothing to write: the mesh has no triangles")
    js = {"asset": {"version": "2.0", "generator": generator}, "scene": 0,
          "scenes": [{"nodes": list(range(len(nodes)))}], "nodes": nodes, "meshes": meshes,
          "accessors": buf.accessors, "bufferViews": buf.views, "buffers": [{"byteLength": len(buf.data)}]}
    if materials:
        js["materials"] = materials
    if images:
        js["images"], js["textures"] = images, textures
        js["samplers"] = [{"magFilter": 9729, "minFilter": 9987}]
        for t in textures:
            t["sampler"] = 0
    write_glb(path, js, bytes(buf.data))


# -- reduction (the only step that needs Blender)

def _require_blender(triangles, budget):
    from .pipeline import find_blender
    try:
        return find_blender()
    except FileNotFoundError as error:
        raise FileNotFoundError(
            f"The mesh has {triangles} triangles, over the budget of {budget}, and reducing it needs Blender, "
            f"which was not found ({error}). Install Blender 4.5 and set KIT_BLENDER, or raise --budget to "
            f"at least {triangles} to import it unreduced.") from None


def _reduce_with_blender(tris, budget, name, workdir):
    """Reduce a triangle soup (T,3,3) to at most `budget` triangles with headless Blender; geometry only."""
    from .pipeline import blender
    workdir = Path(workdir)
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", name) or "part"
    raw, low = workdir / f"{safe}_raw.glb", workdir / f"{safe}_reduced.glb"
    pts = tris.reshape(-1, 3)
    write_prims_glb(raw, [(safe, "", [Prim(0, safe, pts, np.arange(len(pts)).reshape(-1, 3))])])
    config = {"raw_glb": str(raw), "low_glb": str(low), "atlas_png": str(workdir / f"{safe}_atlas.png"),
              "report_json": str(workdir / f"{safe}_report.json"), "budget": int(budget), "height": 0.0,
              "node_name": safe, "ground": False, "rotate_front": False, "planar_deg": 3.0,
              "weld_dist": 1e-4, "normalize": False}
    cfg = workdir / f"{safe}_config.json"
    cfg.write_text(json.dumps(config), encoding="utf-8")
    blender("reduce_mesh.py", str(cfg))
    if not low.is_file():
        raise RuntimeError("Blender finished without writing the reduced mesh")
    scene = read_scene(low)
    return np.concatenate([p.pos[p.tri] for p in scene.prims])


def _allocate(counts, budget):
    """Triangles each node may keep, in proportion to its size, summing to at most `budget`."""
    total = sum(counts)
    if budget < MIN_TRIANGLES_PER_NODE * len(counts):
        raise ValueError(f"--budget {budget} is too small for {len(counts)} separate nodes "
                         f"(at least {MIN_TRIANGLES_PER_NODE} each)")
    exact = [budget * c / total for c in counts]
    shares = [max(MIN_TRIANGLES_PER_NODE, int(e)) for e in exact]
    for k in sorted(range(len(shares)), key=lambda j: (-(exact[j] - int(exact[j])), j)):
        if sum(shares) < budget and shares[k] < counts[k]:
            shares[k] += 1
    while sum(shares) > budget:
        k = max(range(len(shares)), key=lambda j: shares[j] - MIN_TRIANGLES_PER_NODE)
        shares[k] -= 1
    return shares


def _soup(scene, prims):
    """Triangles (T,3,3), their sRGB 0..255 colours (T,3) or None, from primitives (no colour reads as white)."""
    tris, cols, any_colour = [], [], False
    for p in prims:
        tris.append(p.pos[p.tri])
        c, _ = triangle_colours(scene, p)
        any_colour |= c is not None
        cols.append(np.full((len(p.tri), 3), 255.0) if c is None else c)
    return np.concatenate(tris), (np.concatenate(cols) if any_colour else None)


def _outward(new, old):
    """Flip reduced triangles whose normal disagrees with the nearest source triangle's."""
    def normals(t):
        n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
        return n / (np.linalg.norm(n, axis=1, keepdims=True) + 1e-18)
    from scipy.spatial import cKDTree
    near = cKDTree(old.mean(axis=1)).query(new.mean(axis=1))[1]
    bad = (normals(new) * normals(old)[near]).sum(axis=1) < 0
    new = new.copy()
    new[bad] = new[bad][:, [0, 2, 1]]
    return new, near


def reduce_groups(scene, groups, budget, workdir):
    """Reduce the groups to `budget` triangles in total. Colours are re-attached afterwards from the nearest
    source triangle as per-triangle vertex colours; textures do not survive a reduction (use `base bake`)."""
    counts = [triangle_count(g[2]) for g in groups]
    shares = _allocate(counts, budget)
    out = []
    for (name, raw, prims), count, share in zip(groups, counts, shares):
        if count <= share:
            out.append((name, raw, prims))
            continue
        tris, rgb = _soup(scene, prims)
        low, near = _outward(_reduce_with_blender(tris, share, name, workdir), tris)
        pts = low.reshape(-1, 3)
        col = None
        if rgb is not None:
            lin = srgb_to_linear(rgb[near] / 255.0)
            col = np.repeat(np.concatenate([lin, np.ones((len(lin), 1))], 1), 3, axis=0)
        out.append((name, raw, [Prim(prims[0].node, prims[0].name, pts, np.arange(len(pts)).reshape(-1, 3), col)]))
    return out


# -- the import

def _utc_now():
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    when = datetime.datetime.fromtimestamp(int(epoch), datetime.timezone.utc) if epoch else datetime.datetime.now(datetime.timezone.utc)
    return when.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _rel(root, path):
    return Path(path).resolve().relative_to(Path(root).resolve()).as_posix()


def base_paths(folder, name):
    if not isinstance(name, str) or not SAFE_NAME.fullmatch(name):
        raise ValueError("--name must be a safe identifier (letters, digits, '_' and '-')")
    root = local_path(folder, BASE_DIR)
    return {"dir": root, "source": root / f"{name}_source.glb", "lowpoly": root / f"{name}_lowpoly.glb",
            "report": root / f"{name}_lowpoly.json", "ledger": root / f"{name}.json"}


def read_ledger(folder, name="base"):
    path = base_paths(folder, name)["ledger"]
    if not path.is_file():
        raise FileNotFoundError(f"No base mesh ledger {_rel(folder, path)}; run `base import` first")
    return json.loads(path.read_text(encoding="utf-8"))


def prepare(scene, front="+z", height=None, drop_plinth=False, drop_node=(), scale_to=True):
    """Pose, drop, face and ground a scene's primitives. Returns (prims, report parts)."""
    prims, dropped = list(scene.prims), []
    if drop_plinth and drop_node:
        raise ValueError("Use --drop-plinth or --drop-node, not both")
    if drop_node:
        prims, dropped = drop_nodes(scene, prims, drop_node)
    elif drop_plinth:
        prims, plinth = detect_plinth(scene, prims)
        dropped = [plinth]
    after_drop = triangle_count(prims)
    prims = rotate(prims, front)
    prims, scale = ground_and_centre(prims, height if scale_to else None)
    return prims, {"dropped": dropped, "after_drop": after_drop, "scale": scale}


def import_base(folder, source, name="base", *, source_url=None, licence=None, credit=None, front="+z",
                height=None, budget=None, drop_plinth=False, drop_node=(), separate_nodes=False, replace=False):
    """Import `source` (a GLB) as the project's base mesh. Returns a dict of the written project paths.

    Nothing is written until every step has succeeded, and the source file is never modified."""
    folder = Path(folder).resolve()
    paths = base_paths(folder, name)
    front = _front(front)
    drop_node = list(drop_node or ())
    if height is not None and not (math.isfinite(height) and height > 0):
        raise ValueError("--height must be a positive number of metres")
    if budget is not None and budget < MIN_TRIANGLES_PER_NODE:
        raise ValueError(f"--budget must be at least {MIN_TRIANGLES_PER_NODE} triangles")
    src = Path(source)
    if not src.is_file():
        raise FileNotFoundError(f"Base mesh not found: {source}")
    blob = src.read_bytes()
    digest = _sha256(blob)
    load_glb(src)  # a readable GLB, before anything is copied

    old = None
    if paths["ledger"].is_file():
        old = json.loads(paths["ledger"].read_text(encoding="utf-8"))
    existing = paths["source"].read_bytes() if paths["source"].is_file() else None
    held = old["source"]["sha256"] if old else (_sha256(existing) if existing is not None else None)
    different = held is not None and held != digest
    if different and not replace:
        raise ValueError(f"inputs/base/{name} already holds a different base mesh (sha256 {held[:12]}...); "
                         f"pass --replace to replace it, or choose another --name")

    scene = read_scene(src)
    prims, info = prepare(scene, front, height, drop_plinth, drop_node)
    before = triangle_count(scene.prims)
    groups = node_groups(prims, separate_nodes, name)
    reduced = budget is not None and info["after_drop"] > budget
    if reduced:
        _require_blender(info["after_drop"], budget)
        with tempfile.TemporaryDirectory(prefix="base-reduce-") as work:
            groups = reduce_groups(scene, groups, budget, work)
        flat = iter(ground_and_centre([p for g in groups for p in g[2]], height)[0])
        groups = [(n, raw, [next(flat) for _ in ps]) for n, raw, ps in groups]
    final = [p for g in groups for p in g[2]]
    lo, hi = bounds_of(final)

    report = {
        "name": name,
        "source": {"sha256": digest, "front": front, "triangles": before},
        "height_m": round(float(hi[1] - lo[1]), 5),
        "bounds_m": {"min": [round(float(v), 5) for v in lo], "max": [round(float(v), 5) for v in hi]},
        "triangles": {"source": before, "after_drop": info["after_drop"], "final": triangle_count(final),
                      "budget": budget, "reduced": bool(reduced)},
        "colour_sources": colour_sources(scene),
        "nodes_dropped": info["dropped"],
        "nodes": [{"name": n, "source_name": raw, "triangles": triangle_count(ps)} for n, raw, ps in groups],
        "skin": scene.skin_info(),
        "animations": scene.animation_names(),
        "warnings": list(scene.warnings) + (
            ["vertex colours were rebuilt per triangle by the reduction; textures were dropped"] if reduced else []),
        "extensions_ignored": scene.ignored_extensions(),
    }
    if scene.skin_info()["skins"]:
        report["warnings"].append("the skin and its animations were dropped; the mesh is at its rest pose")

    parameters = {"front": front, "height_m": height, "budget": budget, "drop_plinth": bool(drop_plinth),
                  "drop_node": drop_node, "separate_nodes": bool(separate_nodes)}
    now = _utc_now()
    same = old is not None and not different
    ledger = {
        "schema_version": 1,
        "name": name,
        "source": {
            "file": _rel(folder, paths["source"]),
            "original_name": src.name,
            "original_path": _rel(folder, src) if src.resolve().is_relative_to(folder) else None,
            "url": source_url if source_url is not None else (old["source"].get("url") if same else None),
            "sha256": digest,
            "bytes": len(blob),
        },
        "licence": licence if licence is not None else (old.get("licence") if same else None),
        "credit": credit if credit is not None else (old.get("credit") if same else None),
        "imported_at": old["imported_at"] if same else now,
        "tool": {"name": "lowpoly-workshop", "version": _version()},
        "parameters": parameters,
        "triangles": {"before": before, "after": triangle_count(final)},
        "outputs": {"lowpoly": _rel(folder, paths["lowpoly"]), "report": _rel(folder, paths["report"])},
        "history": list(old.get("history", [])) if old else [],
    }
    if old and different:
        ledger["history"].append({"event": "replaced", "at": now, "previous_sha256": held,
                                  "previous_original_name": old["source"].get("original_name"),
                                  "previous_licence": old.get("licence"), "previous_credit": old.get("credit")})
    elif old:
        ledger["history"].append({"event": "reimported", "at": now, "previous_parameters": old.get("parameters")})
    if existing is not None and old is None and different:
        ledger["history"].append({"event": "replaced", "at": now, "previous_sha256": held})

    paths["dir"].mkdir(parents=True, exist_ok=True)
    if existing != blob:
        with replacing(str(paths["source"])) as tmp:
            Path(tmp).write_bytes(blob)
    write_prims_glb(paths["lowpoly"], groups, scene if not reduced else None)
    write_json(str(paths["report"]), report, indent=2)
    write_json(str(paths["ledger"]), ledger, indent=2)
    return {"ledger": paths["ledger"], "source": paths["source"], "lowpoly": paths["lowpoly"],
            "report": paths["report"], "triangles": report["triangles"], "warnings": report["warnings"]}


def _version():
    from . import __version__
    return __version__


def status(folder, name="base"):
    """The ledger plus whether the stored source and normalised mesh still match their recorded hashes."""
    folder = Path(folder).resolve()
    paths = base_paths(folder, name)
    ledger = read_ledger(folder, name)
    ok = paths["source"].is_file() and _sha256(paths["source"].read_bytes()) == ledger["source"]["sha256"]
    return {"ledger": ledger, "source_matches_ledger": bool(ok), "lowpoly_present": paths["lowpoly"].is_file()}


def bake_base(folder, source=None, name="base", variants=None, fit_variant=None, size=1024, align=True,
              front=None, drop_node=None, drop_plinth=None):
    """Bake any source mesh's colours onto the asset's hand-built LODs; returns the path of the bake record.

    The default source is the normalised `inputs/base/<name>_lowpoly.glb`. A different `source` may be the
    original base: when it is the stored `<name>_source.glb`, its front and dropped nodes default to the
    ledger's parameters; otherwise give `front` (default +z) and `drop_node`/`drop_plinth` yourself.
    Colours are the base-colour texture, else `COLOR_0`, else the material colour."""
    from .pixal3d_bake import bake_lods
    folder = Path(folder).resolve()
    paths = base_paths(folder, name)
    if source is None:
        if not paths["lowpoly"].is_file():
            raise FileNotFoundError(f"No {_rel(folder, paths['lowpoly'])}; run `base import` first or pass --source")
        source = paths["lowpoly"]
    source = Path(source).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Bake source not found: {source.name}")
    given = {"front": front, "drop_node": drop_node, "drop_plinth": drop_plinth}
    options = {"front": "+z", "drop_node": (), "drop_plinth": False}
    if source == paths["source"].resolve() and paths["ledger"].is_file():
        params = read_ledger(folder, name)["parameters"]
        options.update(front=params["front"], drop_node=tuple(params["drop_node"]), drop_plinth=params["drop_plinth"])
    options.update({k: v for k, v in given.items() if v})
    options["order"] = ("texture", "vertex", "factor")
    return bake_lods(folder, source, variants, fit_variant, size, align, label="BASE", out_name="base_bake",
                     material="base_bake", glb_options=options, relative_source=True)
