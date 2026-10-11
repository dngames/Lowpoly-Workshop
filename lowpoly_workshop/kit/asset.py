"""An asset project: asset.json (sheets, views, outputs, contract) plus gen.py (the generator).

gen.py must define
    ATLAS                       kit.atlas.Atlas for its cells
    params(variant=None, overrides=None) -> dict
    build(p) -> nodes           {name: {"parent", "pivot", "faces", optional "rot"}}
and may define
    extras(p, scale) -> {node: {key: value}}          glTF extras written on nodes (e.g. mount points)
    clips(nodes, p) -> {name: {"fps": 24, "frames": [pose, ...]}}   rigid-node animation clips
    fit_scene(set, view, extra, ctx) -> (nodes, pose)  what a sheet view shows (default: the set's variant at rest)
    fit_extra(set, view) -> {"init": [...], "steps": [...], "limits": [[lo, hi], ...]}   extra fit parameters
    show_scenes(ctx) -> {name: (nodes, pose, target_y)}  hand-over shots
"""
import importlib.util
import hashlib
from pathlib import Path
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from . import mesh  # noqa: E402

_GENS = {}


def load_gen(path):
    """Import a gen.py by file path (cached), so assets can depend on each other."""
    path = os.path.abspath(path)
    source=Path(path).read_bytes()
    key=(path,hashlib.sha256(source).hexdigest())
    if key not in _GENS:
        name = "gen_%d" % len(_GENS)
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        exec(compile(source,path,"exec"),mod.__dict__)
        _GENS[key] = mod
    return _GENS[key]


class Asset:
    def __init__(self, folder):
        self.dir = os.path.abspath(folder)
        from lowpoly_workshop.spec import read_spec
        self.spec = read_spec(self.dir)
        self.gen = load_gen(os.path.join(self.dir, self.spec.get("generator", "gen.py")))
        self._cache = {}
        self.overrides = {}

    # -- paths
    def path(self, *parts):
        from lowpoly_workshop.spec import local_path
        return str(local_path(self.dir, os.path.join(*parts)))

    def out(self, *parts):
        p = self.path(self.spec.get("out_dir", "out"), *parts)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        return p

    # -- geometry
    def params(self, variant=None):
        return self.gen.params(variant, self.overrides or None)

    def build(self, variant=None, scale=1.0):
        key = (variant, scale, json.dumps(self.overrides, sort_keys=True))
        if key not in self._cache:
            nodes = self.gen.build(self.params(variant))
            from lowpoly_workshop.spec import validate_nodes
            nodes = validate_nodes(nodes, self.gen.ATLAS)
            if scale != 1.0:
                nodes = mesh.scaled(nodes, scale)
            for nd in nodes.values():
                nd.setdefault("rot", np.eye(3))
                nd.setdefault("atlas", self.gen.ATLAS)
            self._cache[key] = nodes
        return self._cache[key]

    def outputs(self):
        return self.spec.get("outputs", [])

    # -- sheets
    def sets(self):
        return self.spec.get("sets", {})

    def views(self, set_name):
        st = self.sets()[set_name]
        return list(st["views"].keys())

    def crop_box(self, set_name, view):
        st = self.sets()[set_name]
        v = st["views"][view]
        if "box" in v:
            return v["box"]
        g = st["grid"]                       # {"cell": [w, h], "crop_h": h, "cells": {view: [row, col]}}
        r, c = v["cell"]
        w, h = g["cell"]
        return [c * w, r * h, c * w + w, r * h + g.get("crop_h", h)]

    def sheet(self, set_name, view):
        from PIL import Image
        st = self.sets()[set_name]
        with Image.open(self.path(st["image"])) as source:
            return np.asarray(source.convert("RGB").crop(tuple(self.crop_box(set_name, view))))

    def classes(self, set_name):
        st = self.sets()[set_name]
        pal = self.spec["palettes"][st.get("palette", "default")]
        return {int(k): v for k, v in pal.items() if not k.startswith("_")}, pal.get("_line_class")

    def cell_classes(self):
        """Model atlas cell -> sheet class id ("_default" for cells not listed)."""
        out = {"_default": int(self.spec.get("default_class", 1))}
        for k, v in self.spec.get("cell_class", {}).items():
            out[k] = int(v)
        return out

    def class_names(self):
        return {int(k): v for k, v in self.spec.get("class_names", {}).items()}

    def target(self):
        return tuple(self.spec.get("camera_target", [0.0, 0.5, 0.0]))

    # -- what a view shows
    def scene(self, set_name, view, extra):
        st = self.sets()[set_name]
        if hasattr(self.gen, "fit_scene"):
            nodes, pose = self.gen.fit_scene(set_name, view, list(extra), self)
        else:
            nodes, pose = self.build(st.get("variant"), st.get("scale", 1.0)), {}
        hide = set(st.get("hide", []))
        only = st.get("only")
        nodes = {k: v for k, v in nodes.items() if k not in hide and (not only or k in only)}
        return nodes, pose

    def extra_spec(self, set_name, view):
        if hasattr(self.gen, "fit_extra"):
            return self.gen.fit_extra(set_name, view) or {"init": [], "steps": [], "limits": []}
        return {"init": [], "steps": [], "limits": []}

    def palette(self, nodes):
        """Cell -> rgb for every atlas used by the nodes."""
        pal = {}
        for nd in nodes.values():
            atl = nd.get("atlas") or self.gen.ATLAS
            for c in atl.cells:
                pal.setdefault(c, atl.rgb_of(c))
        return pal

    # -- solved cameras
    def cam_file(self, set_name, view):
        return self.path("cams", set_name, view + ".json")

    def cam(self, set_name, view):
        f = self.cam_file(set_name, view)
        return json.loads(Path(f).read_text()) if os.path.exists(f) else None
