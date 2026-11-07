"""Headless-Blender polygon reduction shared by the Pixal3D and base-mesh paths.

`reduce_code(config)` returns deterministic Blender Python (for `tools.blender.execute_blender_code` or
`blender -b -P`). It imports `raw_glb`, optionally rotates it 180 deg about the vertical (`rotate_front`),
welds close vertices, dissolves near-planar faces and reduces the result to `budget` triangles with the
UV-preserving Collapse Decimate modifier, then optionally (`normalize`, default on) scales to `height`,
centres X/Z and grounds the lowest point, and writes `low_glb` plus a JSON report.

Config keys: raw_glb, low_glb, atlas_png, report_json, budget, height, node_name, ground, rotate_front,
planar_deg, weld_dist and the optional normalize (default true). The module itself never imports bpy; only
the returned source does, so it loads in plain Python.
"""
import json


def reduce_code(config):
    """Blender Python source that reduces `config["raw_glb"]` as described in the module docstring."""
    return f"""import hashlib, json, math, os, tempfile
from pathlib import Path
import bpy, bmesh
from mathutils import Matrix, Vector

CFG = json.loads({json.dumps(config)!r})
raw_path = Path(CFG["raw_glb"])
if not raw_path.is_file():
    raise FileNotFoundError(f"Missing source GLB: {{raw_path}}")

before_objs = set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=str(raw_path))
imported = [o for o in bpy.data.objects if o not in before_objs]
mesh_objs = [o for o in imported if o.type == "MESH"]
if not mesh_objs:
    raise RuntimeError("No mesh objects found in the imported GLB")

bpy.ops.object.select_all(action="DESELECT")
for o in mesh_objs:
    o.select_set(True)
bpy.context.view_layer.objects.active = mesh_objs[0]
if len(mesh_objs) > 1:
    bpy.ops.object.join()
ob = bpy.context.view_layer.objects.active
ob.name = CFG["node_name"]
ob.data.name = CFG["node_name"]

for o in list(imported):
    if o != ob and o.name in bpy.data.objects:
        bpy.data.objects.remove(o, do_unlink=True)
ob.parent = None
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# Pixal3D writes models facing -Z in glTF (+Y in Blender); rotate 180 deg around Z so front is +Z in glTF.
if CFG["rotate_front"]:
    ob.rotation_mode = "XYZ"
    ob.rotation_euler = (0.0, 0.0, math.pi)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)

bm = bmesh.new()
bm.from_mesh(ob.data)
if CFG["weld_dist"] > 0:
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=float(CFG["weld_dist"]))
bmesh.ops.triangulate(bm, faces=bm.faces)
raw_tris = len(bm.faces)
bm.to_mesh(ob.data)
bm.free()

if CFG["planar_deg"] > 0 and len(ob.data.polygons) > CFG["budget"]:
    mod_planar = ob.modifiers.new("PlanarClean", "DECIMATE")
    mod_planar.decimate_type = "DISSOLVE"
    mod_planar.angle_limit = math.radians(float(CFG["planar_deg"]))
    mod_planar.delimit = {{"UV"}}
    bpy.ops.object.modifier_apply(modifier=mod_planar.name)

bm = bmesh.new()
bm.from_mesh(ob.data)
bmesh.ops.triangulate(bm, faces=bm.faces)
bm.to_mesh(ob.data)
bm.free()

cur_tris = len(ob.data.polygons)
if cur_tris > CFG["budget"]:
    mod_dec = ob.modifiers.new("LowpolyBudget", "DECIMATE")
    mod_dec.decimate_type = "COLLAPSE"
    mod_dec.use_collapse_triangulate = True
    mod_dec.ratio = max(0.001, min(1.0, (CFG["budget"] - 2) / float(cur_tris)))
    bpy.ops.object.modifier_apply(modifier=mod_dec.name)

bm = bmesh.new()
bm.from_mesh(ob.data)
bmesh.ops.triangulate(bm, faces=bm.faces)
while len(bm.faces) > CFG["budget"]:
    bm.to_mesh(ob.data)
    mod_extra = ob.modifiers.new("LowpolyBudgetTrim", "DECIMATE")
    mod_extra.decimate_type = "COLLAPSE"
    mod_extra.use_collapse_triangulate = True
    mod_extra.ratio = max(0.01, (CFG["budget"] - 2) / float(len(bm.faces)))
    bpy.ops.object.modifier_apply(modifier=mod_extra.name)
    bm.clear()
    bm.from_mesh(ob.data)
    bmesh.ops.triangulate(bm, faces=bm.faces)
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
bm.to_mesh(ob.data)
bm.free()

if CFG.get("normalize", True):
    # Scale to target height in metres (Blender Z is glTF Y) and center X/Y; ground Z=0 if requested.
    coords = [v.co.copy() for v in ob.data.vertices]
    xs = [c.x for c in coords]
    ys = [c.y for c in coords]
    zs = [c.z for c in coords]
    span_z = max(zs) - min(zs)
    scale = (CFG["height"] / span_z) if (CFG["height"] > 0 and span_z > 1e-6) else 1.0
    cx = 0.5 * (min(xs) + max(xs))
    cy = 0.5 * (min(ys) + max(ys))
    cz = min(zs) if CFG["ground"] else 0.5 * (min(zs) + max(zs))
    for v in ob.data.vertices:
        v.co.x = (v.co.x - cx) * scale
        v.co.y = (v.co.y - cy) * scale
        v.co.z = (v.co.z - cz) * scale
    ob.data.update()
    ob.location = (0.0, 0.0, 0.0)
    ob.rotation_mode = "QUATERNION"
    ob.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
    ob.scale = (1.0, 1.0, 1.0)

# Save embedded base-color image as a square PNG for Workshop's atlas pipeline if present.
atlas_path = Path(CFG["atlas_png"])
atlas_path.parent.mkdir(parents=True, exist_ok=True)
saved_atlas = False
for mat in ob.data.materials:
    if not mat or not mat.use_nodes:
        continue
    for node in mat.node_tree.nodes:
        if node.type == "TEX_IMAGE" and node.image is not None:
            img = node.image
            w, h = img.size
            if w > 0 and h > 0:
                if w != h:
                    side = max(w, h)
                    img.scale(side, side)
                img.filepath_raw = str(atlas_path)
                img.file_format = "PNG"
                img.save()
                saved_atlas = True
                break
    if saved_atlas:
        break

low_path = Path(CFG["low_glb"])
low_path.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.object.select_all(action="DESELECT")
ob.select_set(True)
bpy.context.view_layer.objects.active = ob
tmp_fd, tmp_glb = tempfile.mkstemp(prefix=".pixal3d-low-", suffix=".glb", dir=str(low_path.parent))
os.close(tmp_fd)
try:
    bpy.ops.export_scene.gltf(
        filepath=tmp_glb,
        export_format="GLB",
        use_selection=True,
        export_yup=True,
        export_apply=True,
        export_texcoords=True,
        export_normals=True,
        export_materials="EXPORT",
        export_image_format="AUTO",
        export_cameras=False,
        export_lights=False,
    )
    os.replace(tmp_glb, low_path)
finally:
    if os.path.exists(tmp_glb):
        os.unlink(tmp_glb)

final_tris = len(ob.data.polygons)
xs = [v.co.x for v in ob.data.vertices]
ys = [v.co.y for v in ob.data.vertices]
zs = [v.co.z for v in ob.data.vertices]
report = {{
    "node_name": CFG["node_name"],
    "raw_triangles": int(raw_tris),
    "lowpoly_triangles": int(final_tris),
    "budget": int(CFG["budget"]),
    "height_m": round(float(max(zs) - min(zs)), 5),
    "bounds_gltf_m": [
        [round(float(min(xs)), 5), round(float(min(zs)), 5), round(float(min(-y for y in ys)), 5)],
        [round(float(max(xs)), 5), round(float(max(zs)), 5), round(float(max(-y for y in ys)), 5)],
    ],
    "raw_sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
    "lowpoly_sha256": hashlib.sha256(low_path.read_bytes()).hexdigest(),
    "atlas_saved": bool(saved_atlas and atlas_path.is_file()),
}}
Path(CFG["report_json"]).write_text(json.dumps(report, indent=2) + "\\n", encoding="utf-8")
print("DECIMATED", low_path.name, f"{{raw_tris}} -> {{final_tris}} tris (budget {{CFG['budget']}})")
"""
