"""Versioned project contracts. Validate before executing a generator."""
from pathlib import Path
import json
import math
import re
from pathlib import PureWindowsPath

KINDS = ("static-prop", "hollow-prop", "wearable", "articulated", "character")

def local_path(root, value):
    root = Path(root).resolve()
    if not isinstance(value, str) or not value or (Path(value).is_absolute() or PureWindowsPath(value).drive):
        raise ValueError(f"Expected a nonempty project-relative path: {value!r}")
    path = (root / value).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"Path escapes project: {value}")
    return path

def finite(value, size=None):
    import numpy as np
    a = np.asarray(value, float)
    if not np.isfinite(a).all() or (size is not None and a.shape != (size,)):
        raise ValueError(f"Expected {size or 'finite'} finite values: {value}")
    return a

def validate(spec, root):
    if spec.get("schema_version") != 2:
        raise ValueError("schema_version must be 2; see docs/migration.md")
    if spec.get("kind") not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}")
    if not isinstance(spec.get("name"), str) or not spec["name"]:
        raise ValueError("name is required")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*",spec["name"]):raise ValueError("name must be a safe identifier")
    local_path(root, spec.get("generator", "gen.py"))
    output_root=local_path(root,spec.get("out_dir","out"))
    if output_root==Path(root).resolve():raise ValueError("out_dir must be a dedicated subdirectory")
    outputs = spec.get("outputs", [])
    if not outputs:
        raise ValueError("At least one output is required")
    seen = set()
    for out in outputs:
        p = local_path(root, out["file"])
        if not p.is_relative_to(output_root):raise ValueError("Outputs must be inside out_dir")
        if p.suffix.lower() != ".glb" or p in seen:
            raise ValueError("Output paths must be distinct .glb files")
        seen.add(p)
        if out.get("scale", 1) <= 0 or not math.isfinite(out.get("scale", 1)):
            raise ValueError("scale must be finite and positive")
        if out.get("kit_mask"):
            local_path(p.parent, out["kit_mask"])
        if out.get("skin"):
            raise ValueError("Use the skin command for skeletal exports; ordinary outputs are rigid")
    for st in spec.get("sets", {}).values():
        local_path(root, st["image"])
        for view in st["views"].values():
            if "box" in view:
                box = finite(view["box"], 4)
                if min(box[:2]) < 0 or box[2] <= box[0] or box[3] <= box[1]:
                    raise ValueError("Invalid view crop")
    for ref in spec.get("references", []):
        local_path(root, ref["path"])
        if ref.get("source") not in ("original", "generated", "rendered"):
            raise ValueError("reference source must be original, generated or rendered")
    for pose in spec.get("poses", {}).values():
        for key,value in pose.items():
            if key=="_root_for":continue
            if key.startswith("_hide_"):continue
            array=finite(value)
            if array.shape not in ((3,),(3,3)):raise ValueError("Pose requires Euler vector or rotation matrix")
    for relation in spec.get("relations", []):
        if relation.get("type") not in ("connected", "clear", "fit", "support"):
            raise ValueError("Unknown relation type")
        if relation["type"] in ("fit", "support"):
            finite(relation["direction"], 3)
            if not relation.get("samples"):
                raise ValueError("fit/support relations require explicit world-space samples")
            for p in relation["samples"]:
                finite(p, 3)
        for field in ("max_gap", "min_gap", "min", "max"):
            if field in relation and (not math.isfinite(relation[field]) or relation[field] < 0):
                raise ValueError(f"{field} must be finite and nonnegative")
    review=spec.get('review',{})
    if not set(review.get('views',[]))<=set(('front','back','side','quarter','top','below')):raise ValueError('Unknown review view')
    if not set(review.get('modes',[]))<=set(('textured','plain','checker','wireframe')):raise ValueError('Unknown review mode')
    if not 64<=review.get('size',512)<=4096:raise ValueError('Review size must be 64..4096')
    for region in review.get("regions", []):
        if not region.get("nodes") and not region.get("bounds"):
            raise ValueError("Review region needs nodes or bounds")
        if 'bounds' in region:
            bounds=finite(region['bounds'])
            if bounds.shape!=(2,3) or not (bounds[1]>bounds[0]).all():raise ValueError('Invalid review bounds')
        if region.get('margin',1.3)<=0:raise ValueError('Review margin must be positive')
    from .features import validate as validate_features
    validate_features(spec, root)
    return spec

def load_profile(name):
    if not name or "/" in name or "\\" in name:
        raise ValueError("profile must be a bundled profile name")
    return json.loads((Path(__file__).parent / "profiles" / (name + ".json")).read_text())

def read_spec(folder):
    root = Path(folder).resolve()
    spec = json.loads((root / "asset.json").read_text(encoding="utf-8-sig"))
    validate(spec, root)
    load_profile(spec.get("profile", "portable"))
    return spec

def validate_nodes(nodes, atlas):
    import numpy as np
    if not isinstance(nodes, dict) or not nodes:
        raise ValueError("Generator must return nonempty nodes")
    active, visited, order = set(), set(), []
    def visit(name):
        if name in active:
            raise ValueError(f"Parent cycle at {name}")
        if name in visited:
            return
        active.add(name)
        nd = nodes[name]
        parent = nd.get("parent")
        if parent is not None:
            if parent not in nodes:
                raise ValueError(f"Unknown parent of {name}: {parent}")
            visit(parent)
        finite(nd["pivot"], 3)
        r = np.asarray(nd.get("rot", np.eye(3)), float)
        if r.shape != (3, 3) or not np.isfinite(r).all() or not np.allclose(r.T @ r, np.eye(3), atol=1e-5) or np.linalg.det(r) < .999:
            raise ValueError(f"Invalid rest rotation: {name}")
        for pts, cell, uv, thin in nd["faces"]:
            points = np.asarray(pts, float)
            if points.ndim != 2 or points.shape[1] != 3 or len(points) < 3 or not np.isfinite(points).all():
                raise ValueError(f"Invalid face: {name}")
            atl = nd.get("atlas") or atlas
            if cell not in atl.cells:
                raise ValueError(f"Unknown atlas cell: {name}/{cell}")
            if uv is not None and (np.shape(uv) != (len(points), 2) or not np.isfinite(uv).all() or np.min(uv) < 0 or np.max(uv) > 1):
                raise ValueError(f"Invalid decal UV: {name}/{cell}")
        active.remove(name)
        visited.add(name)
        order.append(name)
    for name in nodes:
        visit(name)
    # Parent-first order is a guarantee, regardless of dictionary insertion order.
    return {name: nodes[name] for name in order}
