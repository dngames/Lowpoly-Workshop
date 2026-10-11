"""Declarative visual features; no geometry or artistic judgement is inferred."""
import re
from .spec import local_path

STAGES = ("proportions", "construction", "appearance", "motion-export")
VIEWS = ("front", "back", "side", "quarter", "top", "below")
MODES = ("textured", "plain", "checker", "wireframe")


def image_dimensions(path):
    """Use Blender's native reader when its bundled Python has no Pillow."""
    try:
        from PIL import Image
    except ImportError:
        import bpy
        image = bpy.data.images.load(str(path), check_existing=False)
        try:
            return tuple(image.size)
        finally:
            bpy.data.images.remove(image)
    with Image.open(path) as image:
        return image.size


def enabled(spec):
    return bool(spec.get("features")) or spec.get("workflow", {}).get("enabled", False)


def validate(spec, root):
    rows = spec.get("features", [])
    if not isinstance(rows, list):
        raise ValueError("features must be an array")
    config = spec.get("workflow", {})
    if not isinstance(config, dict) or not isinstance(config.get("enabled", False), bool):
        raise ValueError("workflow.enabled must be boolean")
    outputs = {o["file"] for o in spec["outputs"]}
    refs = {r["path"]: r["source"] for r in spec.get("references", [])}
    ids = set()
    for f in rows:
        if not isinstance(f, dict):
            raise ValueError("Each feature must be an object")
        name = f.get("id", "")
        if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", name) or name in ids:
            raise ValueError("Feature ids must be unique lowercase identifiers")
        ids.add(name)
        if f.get("stage") not in STAGES:
            raise ValueError(f"Feature {name}: unknown stage")
        if not isinstance(f.get("description"), str) or not f["description"].strip():
            raise ValueError(f"Feature {name}: description is required")
        if f.get("output") not in outputs:
            raise ValueError(f"Feature {name}: output must be a declared GLB")
        if not isinstance(f.get("required", True), bool):
            raise ValueError(f"Feature {name}: required must be boolean")
        for key, allowed in (("nodes", None), ("views", VIEWS), ("modes", MODES),
                             ("poses", ("rest", *spec.get("poses", {})))):
            values = f.get(key)
            if (not isinstance(values, list) or not values or
                    any(not isinstance(v, str) or not v for v in values) or
                    len(values) != len(set(values)) or (allowed is not None and not set(values) <= set(allowed))):
                raise ValueError(f"Feature {name}: invalid {key}")
        basis = f.get("basis")
        if basis not in ("observed", "inferred"):
            raise ValueError(f"Feature {name}: basis must be observed or inferred")
        evidence = f.get("evidence", [])
        if not isinstance(evidence, list):
            raise ValueError(f"Feature {name}: evidence must be an array")
        for item in evidence:
            if not isinstance(item, dict) or item.get("path") not in refs:
                raise ValueError(f"Feature {name}: evidence must link a registered reference")
            path = local_path(root, item["path"])
            if not path.is_file():
                raise ValueError(f"Feature {name}: reference is missing")
            if basis == "observed" and refs[item["path"]] != "original":
                raise ValueError(f"Feature {name}: generated/rendered evidence cannot establish an observed feature")
            if "box" in item:
                box = item["box"]
                if (not isinstance(box, list) or len(box) != 4 or
                        any(type(v) is not int for v in box) or min(box[:2]) < 0 or
                        box[2] <= box[0] or box[3] <= box[1]):
                    raise ValueError(f"Feature {name}: invalid pixel crop")
                width, height = image_dimensions(path)
                if box[2] > width or box[3] > height:
                    raise ValueError(f"Feature {name}: crop exceeds reference")
        if basis == "observed" and not evidence:
            raise ValueError(f"Feature {name}: observed features need original evidence")
        if basis == "inferred" and (not isinstance(f.get("notes"), str) or not f["notes"].strip()):
            raise ValueError(f"Feature {name}: explain the inferred design in notes")


def regions(spec, output):
    return [dict(name="feature-" + f["id"], feature_id=f["id"], nodes=f["nodes"],
                 views=f["views"], modes=f["modes"], poses=f["poses"], margin=1.3)
            for f in spec.get("features", []) if f["output"] == output]


def requirements(spec, stage):
    """Small fixed review minimum; projects may request additional feature shots."""
    views, modes = {
        "proportions": (("front", "side"), ("plain",)),
        "construction": (("quarter", "below"), ("plain",)),
        "appearance": (("front", "back", "side"), ("textured",)),
        "motion-export": (("quarter",), ("plain",)),
    }[stage]
    poses = ("rest", *spec.get("poses", {})) if stage == "motion-export" else ("rest",)
    return [(o["file"], p, "whole", m, v) for o in spec["outputs"]
            for p in poses for m in modes for v in views]


def guided(spec, nodes):
    """Opt-in checklist for independent procedural starters, without invented references."""
    spec["workflow"] = {"enabled": True}
    spec["features"] = []
    for i, output in enumerate(spec["outputs"]):
        names = [n for n, node in nodes.items() if node["faces"]]
        for stage in STAGES:
            wanted = requirements({**spec, "outputs": [output]}, stage)
            spec["features"].append(dict(
                id=f"{stage}-{i + 1}", stage=stage, output=output["file"], nodes=names,
                description={"proportions": "Overall proportions and silhouette",
                             "construction": "Closed surfaces and intended attachments",
                             "appearance": "Surface colours, markings and UV placement",
                             "motion-export": "Declared poses and exported assembly"}[stage],
                basis="inferred", notes="Independent procedural starter design. Replace this checklist with the intended design and permitted references.",
                evidence=[], views=list(dict.fromkeys(r[4] for r in wanted)),
                modes=list(dict.fromkeys(r[3] for r in wanted)),
                poses=list(dict.fromkeys(r[1] for r in wanted))))
    return spec
