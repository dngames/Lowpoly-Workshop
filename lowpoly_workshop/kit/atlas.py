"""Colour atlas, kit mask and UVs for one asset.

Flat palette regions are square cells laid out in a grid (88 px painted, 8 px padding). Decals are
rectangles shelf-packed below the grid; a decal's painter draws its pixels and may mark kit channels.
Faces map into their cell: flat faces get a projected UV inset inside the cell, decal faces carry
explicit (u, v) in 0..1 that land inside the decal rectangle.

    ATLAS = Atlas({"frame": ("#3daa4a", "R"), "tyre": ("#3b3842", None),
                   "reflector": ("#2b2833", None, "reflector")},
                  decals={"reflector": ((256, 128), paint_reflector)})

kit mask channels: "R" main colour, "G" accent, "B" third colour (bar tape, shorts, ...).
"""
import struct
import zlib

import numpy as np

from .mesh import newell

SIZE, PITCH, CELL, INSET = 1024, 96, 88, 10


def rgb(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


class Atlas:
    def __init__(self, cells, decals=None, base="#3a4150", size=SIZE, rects=None, decal_margin=2, mask_channels="RGB"):
        """cells: name -> (hex, kit channel or None[, decal name]); decals: name -> ((w, h), painter).

        rects lets a caller pin decal rectangles (x0, y0, x1, y1) instead of shelf-packing them."""
        if mask_channels not in ("RGB","RGBA"):raise ValueError("Mask channels must be RGB or RGBA")
        self.mask_channels = mask_channels
        self.cells = {k: (v[0], v[1], v[2] if len(v) > 2 else None) for k, v in cells.items()}
        self.decals = decals or {}
        self.base = base
        self.size = size
        self._rects = dict(rects or {})
        self.decal_margin = decal_margin
        self._layout = None

    def layout(self):
        if self._layout is not None:
            return self._layout
        rects = {}
        flat = [k for k, v in self.cells.items() if v[2] is None]
        per_row = (self.size - 16) // PITCH
        for i, name in enumerate(flat):
            cx, cy = 16 + (i % per_row) * PITCH, 16 + (i // per_row) * PITCH
            rects[name] = (cx, cy, cx + CELL, cy + CELL)
        y = 16 + ((len(flat) + per_row - 1) // per_row) * PITCH
        x, shelf = 16, 0
        for name, v in self.cells.items():
            if v[2] is None:
                continue
            if name in self._rects:
                rects[name] = self._rects[name]
                continue
            w, h = self.decals[v[2]][0]
            if x + w > self.size - 16:
                x, y, shelf = 16, y + shelf + 8, 0
            rects[name] = (x, y, x + w, y + h)
            x, shelf = x + w + 8, max(shelf, h)
        for name, (x0, y0, x1, y1) in rects.items():
            if x1 > self.size or y1 > self.size:
                raise ValueError("atlas overflow: %s at %s; shrink decals or cells" % (name, rects[name]))
        self._layout = rects
        return rects

    def paint(self):
        """Colour atlas and kit mask as (size, size, 3) uint8 arrays."""
        col = np.zeros((self.size, self.size, 3), np.uint8)
        col[:] = rgb(self.base)
        kit = np.zeros((self.size,self.size,len(self.mask_channels)),np.uint8)
        chan = {k:i for i,k in enumerate(self.mask_channels)}
        for name, rect in self.layout().items():
            hexc, k, decal = self.cells[name]
            x0, y0, x1, y1 = rect
            col[y0:y1, x0:x1] = rgb(hexc)
            if k:
                kit[y0:y1, x0:x1, chan[k]] = 255
            if decal:
                self.decals[decal][1](col, kit, rect, self)
        return col, kit

    def face_uvs(self, pts, cell, uv):
        """UVs in 0..1 with v measured from the top of the image (glTF convention)."""
        x0, y0, x1, y1 = self.layout()[cell]
        S = self.size
        if uv is not None and self.cells[cell][2]:
            m = self.decal_margin
            return [((x0 + m + u * (x1 - x0 - 2 * m)) / S, (y0 + m + (1 - v) * (y1 - y0 - 2 * m)) / S)
                    for u, v in uv]
        pts = np.asarray(pts, float)
        n = newell(pts)
        n = n / (np.linalg.norm(n) + 1e-12)
        a = pts[1] - pts[0]
        a = a - np.dot(a, n) * n
        a = a / (np.linalg.norm(a) + 1e-12)
        b = np.cross(n, a)
        q = np.array([[np.dot(p - pts[0], a), np.dot(p - pts[0], b)] for p in pts])
        lo, span = q.min(0), np.maximum(np.ptp(q, 0), 1e-9)
        q = (q - lo) / span.max()
        w = (x1 - x0) - 2 * INSET
        return [((x0 + INSET + qu * w) / S, (y0 + INSET + (1 - qv) * w) / S) for qu, qv in q]

    def rgb_of(self, cell):
        return np.array(rgb(self.cells[cell][0]), float)


def stretch(img, h, w):
    """Nearest-neighbour resize of an (H, W, 3) array to (h, w, 3) without PIL (works inside Blender)."""
    ys = (np.arange(h) * img.shape[0] / h).astype(int)
    xs = (np.arange(w) * img.shape[1] / w).astype(int)
    return img[ys][:, xs]


def image_decal(path, kit_rules=None):
    """Decal painter that stretches an .npy image (made by kit.sheets quantize) into the rectangle.

    kit_rules: list of (hex colour, channel) marking pixels of that exact colour in the kit mask."""
    def paint(col, kit, rect, atlas):
        x0, y0, x1, y1 = rect
        patch = stretch(np.load(path), y1 - y0, x1 - x0)
        col[y0:y1, x0:x1] = patch
        for hexc, ch in kit_rules or []:
            m = (patch == rgb(hexc)).all(-1)
            kit[y0:y1, x0:x1, atlas.mask_channels.index(ch)][m] = 255
    return paint


def write_png(path, arr):
    """Minimal RGB/RGBA PNG writer (no PIL needed, so it also runs inside Blender)."""
    arr = np.ascontiguousarray(arr, np.uint8)
    h, w, channels = arr.shape
    if channels not in (3, 4):
        raise ValueError("PNG requires RGB or RGBA pixels")
    raw = b"".join(b"\x00" + arr[y].tobytes() for y in range(h))

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    with open(path, "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n")
        fh.write(chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6 if channels == 4 else 2, 0, 0, 0)))
        fh.write(chunk(b"sRGB", b"\x00"))
        fh.write(chunk(b"IDAT", zlib.compress(raw, 9)))
        fh.write(chunk(b"IEND", b""))
