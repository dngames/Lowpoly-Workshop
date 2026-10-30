"""Render an asset through its solved sheet cameras, or its hand-over shots, in Blender (EEVEE + outline).

blender -b --factory-startup -P render.py -- <asset_dir> views [set ...]
blender -b --factory-startup -P render.py -- <asset_dir> show

The geometry comes straight from the generator (the same faces the GLBs are built from), posed exactly
as the fit posed it, so a render overlays its sheet crop pixel for pixel.
views -> out/render/<set>/<view>.png (crop size, transparent); show -> out/render/show/<scene>_<view>.png
"""
import math
import os
import sys
import tempfile

import bpy
import numpy as np
from mathutils import Matrix, Vector

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from lowpoly_workshop.kit import rig  # noqa: E402
from lowpoly_workshop.kit.asset import Asset  # noqa: E402
from lowpoly_workshop.kit.atlas import write_png  # noqa: E402

C = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], float)
SHOW_VIEWS = {"side": (-90, 4), "front": (0, 6), "top": (0, 82), "q34": (38, 20)}


def gl2b(v):
    return Vector((v[0], -v[2], v[1]))


def setup(sc):
    try:
        sc.render.engine = "BLENDER_EEVEE_NEXT"
    except TypeError:  # Blender 5.x renamed the same engine.
        sc.render.engine = "BLENDER_EEVEE"
    sc.eevee.taa_render_samples = int(os.environ.get("LOWPOLY_RENDER_SAMPLES","32"))
    world = bpy.data.worlds.new("Ambient")
    world.use_nodes = True
    bgn = world.node_tree.nodes["Background"]
    bgn.inputs["Color"].default_value = (0.80, 0.80, 0.78, 1.0)
    bgn.inputs["Strength"].default_value = 0.85
    sc.world = world
    sun = bpy.data.objects.new("Key", bpy.data.lights.new("Key", "SUN"))
    sun.data.energy = 2.6
    sun.data.angle = math.radians(8)
    sc.collection.objects.link(sun)
    sc.render.use_freestyle = True
    sc.render.line_thickness_mode = "ABSOLUTE"
    sc.render.line_thickness = 1.1
    ls = sc.view_layers[0].freestyle_settings.linesets[0]
    if ls.linestyle is None:
        ls.linestyle = bpy.data.linestyles.new("Kit outline")
    ls.select_by_visibility = True
    ls.select_silhouette, ls.select_border, ls.select_crease = True, True, False
    ls.linestyle.color = (0.08, 0.07, 0.09)
    sc.render.film_transparent = True
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.view_settings.view_transform = "Standard"
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    return cam, sun


MATS = {}


def mat_for(atlas):
    if id(atlas) in MATS:
        return MATS[id(atlas)]
    col, _ = atlas.paint()
    path = os.path.join(tempfile.mkdtemp(), "atlas.png")
    write_png(path, col)
    img = bpy.data.images.load(path)
    img.pack()
    os.unlink(path);os.rmdir(os.path.dirname(path))
    mat = bpy.data.materials.new("atlas%d" % len(MATS))
    mat.use_nodes = True
    nt = mat.node_tree
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.interpolation = "Closest"
    bsdf = nt.nodes["Principled BSDF"]
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.85
    MATS[id(atlas)] = mat
    return mat


def show_scene(nodes, pose, default_atlas):
    """Replace the scene's meshes with the posed nodes (one object per atlas)."""
    for ob in [o for o in bpy.data.objects if o.type == "MESH"]:
        bpy.data.objects.remove(ob, do_unlink=True)
    bpy.context.scene.render.use_freestyle = not all(nd.get("smooth", False) for nd in nodes.values())
    groups = {}
    for name, nd in nodes.items():
        groups.setdefault(id(nd.get("atlas") or default_atlas), []).append(name)
    for key, names in groups.items():
        sub = {n: nodes[n] for n in names}
        full = dict(nodes)
        atlas = sub[names[0]].get("atlas") or default_atlas
        tf = rig.world_transforms(full, pose)
        verts, faces, uvs, smooth, index = [], [], [], [], {}
        for n in names:
            R, t = tf[n]
            for pts, cell, uv, thin in sub[n]["faces"]:
                q = pts @ R.T + t
                ids = []
                for p in q:                       # weld shared corners: open borders would get outlined
                    key = (n, round(p[0], 5), round(p[1], 5), round(p[2], 5))
                    if key not in index:
                        index[key] = len(verts)
                        verts.append(list(C @ p))
                    ids.append(index[key])
                if len(set(ids)) < 3:
                    continue
                fuv = atlas.face_uvs(pts, cell, uv)
                for corner in range(1, len(ids) - 1):
                    tri = [ids[0], ids[corner], ids[corner + 1]]
                    if len(set(tri)) < 3:
                        continue
                    a, b, c = (np.asarray(verts[v]) for v in tri)
                    if np.linalg.norm(np.cross(b - a, c - a)) < 1e-10:
                        continue
                    faces.append(tri)
                    uvs.append([fuv[0], fuv[corner], fuv[corner + 1]])
                    smooth.append(bool(sub[n].get("smooth", False)))
        me = bpy.data.meshes.new("scene")
        me.from_pydata(verts, [], faces)
        uvl = me.uv_layers.new(name="UVMap")
        for poly, fuv, is_smooth in zip(me.polygons, uvs, smooth):
            for k in range(poly.loop_total):
                u, v = fuv[k]
                uvl.data[poly.loop_start + k].uv = (u, 1.0 - v)
            poly.use_smooth = is_smooth
        if any(smooth):
            me.set_sharp_from_angle(angle=math.pi)
        # Keep UV corner data attached if validation removes an overlapping face.
        me.validate(clean_customdata=False)
        me.materials.append(mat_for(atlas))
        ob = bpy.data.objects.new("scene", me)
        bpy.context.scene.collection.objects.link(ob)


def aim(cam, sun, target, az, el, roll, dist):
    a, e, r = map(math.radians, (az, el, roll))
    d = np.array([math.cos(e) * math.sin(a), math.sin(e), math.cos(e) * math.cos(a)])
    right = np.array([math.cos(a), 0.0, -math.sin(a)])
    up = np.array([-math.sin(e) * math.sin(a), math.cos(e), -math.sin(e) * math.cos(a)])
    cr, sr = math.cos(r), math.sin(r)
    right, up = cr * right + sr * up, -sr * right + cr * up
    rb, ub, fb = gl2b(right), gl2b(up), gl2b(-d)
    M = Matrix((rb, ub, -fb)).transposed().to_4x4()
    M.translation = gl2b(np.asarray(target) + d * dist)
    cam.matrix_world = M
    L = (-0.45 * rb + 0.75 * ub + 0.55 * (-fb)).normalized()
    sun.rotation_euler = L.to_track_quat("Z", "Y").to_euler()


def render_views(a, sets, cam, sun):
    sc = bpy.context.scene
    for st in sets:
        for view in a.views(st):
            entry = a.cam(st, view)
            if not entry:
                continue
            v = entry["cam"]
            nodes, pose = a.scene(st, view, v[7:])
            show_scene(nodes, pose, a.gen.ATLAS)
            x0, y0, x1, y1 = a.crop_box(st, view)
            W, H = x1 - x0, y1 - y0
            az, el, roll, dist, s, cx, cy = v[:7]
            aim(cam, sun, a.target(), az, el, roll, dist)
            cd = cam.data
            cd.type, cd.sensor_fit, cd.sensor_width = "PERSP", "AUTO", 36.0
            cd.lens = s * dist * 36.0 / max(W, H)
            cd.shift_x = (W / 2 - cx) / max(W, H)
            cd.shift_y = (cy - H / 2) / max(W, H)
            geometry, _ = rig.posed_triangles(nodes, pose)
            reach = float(np.linalg.norm(geometry.reshape(-1, 3) - np.asarray(a.target()), axis=1).max()) + 1
            cd.clip_start = max(0.05, dist - max(6., reach))
            cd.clip_end = dist + max(8., reach)
            sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100
            sc.render.filepath = a.out("render", st, view + ".png")
            bpy.ops.render.render(write_still=True)
            print("RENDERED", st, view, flush=True)


def render_show(a, cam, sun):
    sc = bpy.context.scene
    width, height = a.spec.get("show_resolution", [900, 700])
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = width, height, 100
    views = a.spec.get("show_views", SHOW_VIEWS)
    scenes = a.gen.show_scenes(a) if hasattr(a.gen, "show_scenes") else {
        "rest": (a.build(a.outputs()[0].get("variant"), a.outputs()[0].get("scale", 1.0)), {}, None)}
    for name, (nodes, pose, focus) in scenes.items():
        show_scene(nodes, pose, a.gen.ATLAS)
        T, _ = rig.posed_triangles(nodes, pose)
        P = T.reshape(-1, 3)
        lo, hi = P.min(0), P.max(0)
        target = (lo + hi) / 2 if focus is None else np.asarray(focus)
        span = float(np.max(hi - lo))
        for view, (az, el) in views.items():
            aim(cam, sun, target, az, el, 0, span * 6 + 6)
            cam.data.type = "ORTHO"
            cam.data.ortho_scale = span * 1.25 * max(1, sc.render.resolution_x / sc.render.resolution_y)
            cam.data.clip_start, cam.data.clip_end = 0.1, span * 12 + 20
            sc.render.filepath = a.out("render", "show", "%s_%s.png" % (name, view))
            bpy.ops.render.render(write_still=True)
            print("SHOT", name, view, flush=True)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    a = Asset(argv[0])
    sc = bpy.context.scene
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    cam, sun = setup(sc)
    if argv[1] == "views":
        render_views(a, argv[2:] or list(a.sets()), cam, sun)
    else:
        render_show(a, cam, sun)


if __name__ == "__main__":
    main()
