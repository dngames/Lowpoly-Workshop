"""Build every output of an asset in Blender: .blend, .glb, atlas and kit mask PNGs.

blender -b --factory-startup -P build.py -- <asset_dir> [output file ...]

Per output (asset.json "outputs"): variant, scale, nodes / exclude, origin (another node whose pivot
becomes this file's origin, e.g. a helmet built around the head), kit_mask, clips (true to export the
generator's clips as glTF animations). Node rest rotations ("rot") are kept; glTF axes are +Y up.
"""
import os
import sys

import bpy
import numpy as np
from mathutils import Matrix

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from lowpoly_workshop.kit.atomic import replacing
from lowpoly_workshop.kit import rig  # noqa: E402
from lowpoly_workshop.kit.asset import Asset  # noqa: E402
from lowpoly_workshop.kit.atlas import write_png  # noqa: E402

C4 = np.eye(4)
C4[:3, :3] = [[1, 0, 0], [0, 0, -1], [0, 1, 0]]        # glTF -> Blender axes


def to_b(M):
    return Matrix((C4 @ M @ C4.T).tolist())


def clear():
    for coll in (bpy.data.objects, bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.actions):
        for item in list(coll):
            coll.remove(item)


def material(atlas, folder, stem, kit_name, vehicle=False):
    col, kit = atlas.paint()
    if vehicle:
        from lowpoly_workshop.kit.vehicle_atlas import pack_vehicle_atlas
        if kit_name: raise ValueError('vehicle paint mask belongs in atlas alpha')
        col = pack_vehicle_atlas(col, kit)
    pa = os.path.join(folder, stem + "_atlas.png")
    write_png(pa, col)
    if kit_name:
        write_png(os.path.join(folder, kit_name), kit)
    img = bpy.data.images.load(pa)
    img.name = stem + "_atlas.png"
    img.pack()
    mat = bpy.data.materials.new("vehicle" if vehicle else stem + "_material")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.interpolation = "Linear" if vehicle else "Closest"
    if vehicle:
        colour = nt.nodes.new("ShaderNodeVertexColor")
        colour.layer_name = "Color"
        multiply = nt.nodes.new("ShaderNodeMixRGB")
        multiply.blend_type = "MULTIPLY"
        multiply.inputs[0].default_value = 1.0
        nt.links.new(tex.outputs["Color"], multiply.inputs[1])
        nt.links.new(colour.outputs["Color"], multiply.inputs[2])
        nt.links.new(multiply.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Metallic"].default_value = 0.0
    bsdf.inputs["Roughness"].default_value = 0.85
    if kit_name:
        mat["kitMask"] = kit_name
    return mat


def node_object(name, node, mat, atlas):
    if node["faces"]:
        return mesh_object(name, node, mat, atlas)
    ob = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(ob)
    ob.rotation_mode = "QUATERNION"
    ob.empty_display_type = "PLAIN_AXES"
    ob.empty_display_size = 0.04
    return ob


def mesh_object(name, node, mat, atlas):
    verts, index, faces, uvs, thin, cells = [], {}, [], [], [], []
    pv, R = node["pivot"], node.get("rot", np.eye(3))
    for pts, cell, uv, is_thin in node["faces"]:
        fuv = atlas.face_uvs(pts, cell, uv)
        if node.get("runtime_uv"):
            from lowpoly_workshop.kit.runtime_uv import face_uvs
            fuv = face_uvs(pts, uv, node["vertex_surfaces"][cell])
        ids = []
        for p in pts:
            key = (round(p[0], 5), round(p[1], 5), round(p[2], 5), bool(is_thin))
            if key not in index:
                index[key] = len(verts)
                verts.append(R.T @ (p - pv))
                thin.append(1.0 if is_thin else 0.0)
            ids.append(index[key])
        if len(set(ids)) < 3:
            continue
        for corner in range(1, len(ids) - 1):
            tri = [ids[0], ids[corner], ids[corner + 1]]
            if len(set(tri)) < 3:
                continue
            a, b, c = (np.asarray(verts[v]) for v in tri)
            if np.linalg.norm(np.cross(b - a, c - a)) < 1e-10:
                continue
            faces.append(tri)
            uvs.append([fuv[0], fuv[corner], fuv[corner + 1]])
            cells.append(cell)
    me = bpy.data.meshes.new(name)
    V = np.array(verts) @ C4[:3, :3].T
    me.from_pydata(V.tolist(), [], faces)
    uvl = me.uv_layers.new(name="UVMap")
    for poly, fuv in zip(me.polygons, uvs):
        for k in range(poly.loop_total):
            u, v = fuv[k]
            uvl.data[poly.loop_start + k].uv = (u, 1.0 - v)
        poly.use_smooth = bool(node.get("smooth", False))
    # Keep UV corner data attached if validation removes an overlapping face.
    cell_index = me.attributes.new("CellIndex", "INT", "FACE")
    cell_index.data.foreach_set("value", list(range(len(faces))))
    me.validate(clean_customdata=False)
    attr = me.attributes.new("_THIN", "FLOAT", "POINT")
    attr.data.foreach_set("value", thin)
    if node.get("smooth", False):
        me.set_sharp_from_angle(angle=np.pi)
    if node.get("vertex_surfaces"):
        # Opt-in consumer-independent palette export: COLOR_0 and named runtime surfaces, no atlas.
        surfaces = node["vertex_surfaces"]
        names = sorted({surfaces[cell] for cell in cells})
        for surface_name in names:
            surface = bpy.data.materials.get(surface_name) or bpy.data.materials.new(surface_name)
            surface.use_nodes = True
            bsdf = surface.node_tree.nodes["Principled BSDF"]
            colour = surface.node_tree.nodes.get("PaletteColor")
            if colour is None:
                colour = surface.node_tree.nodes.new("ShaderNodeVertexColor")
                colour.name = "PaletteColor"
                colour.layer_name = "Color"
                surface.node_tree.links.new(colour.outputs["Color"], bsdf.inputs["Base Color"])
            bsdf.inputs["Roughness"].default_value = 0.85
            me.materials.append(surface)
        colour = me.color_attributes.new(name="Color", type="FLOAT_COLOR", domain="CORNER")
        for poly in me.polygons:
            cell = cells[me.attributes["CellIndex"].data[poly.index].value]
            poly.material_index = names.index(surfaces[cell])
            rgb = np.asarray(atlas.rgb_of(cell), float) / 255
            linear = np.where(rgb <= .04045, rgb / 12.92, ((rgb + .055) / 1.055) ** 2.4)
            for j in poly.loop_indices:
                colour.data[j].color = (*linear, 1.0)
        me.color_attributes.active_color = colour
    elif node.get("vehicle"):
        from lowpoly_workshop.kit.vehicle_atlas import fallback_linear
        spec = node["vehicle"]
        colour = me.color_attributes.new(name="Color", type="FLOAT_COLOR", domain="CORNER")
        for poly in me.polygons:
            i = me.attributes["CellIndex"].data[poly.index].value
            rgb = fallback_linear(node["vehicle_atlas_rgb"], uvs[i], cells[i],
                                  spec["paint_cells"], spec["paint_linear"])
            for j in poly.loop_indices: colour.data[j].color = (*rgb, 1.0)
        me.color_attributes.active_color = colour
        me.materials.append(mat)
    else:
        me.materials.append(mat)
    me.attributes.remove(me.attributes["CellIndex"])
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.rotation_mode = "QUATERNION"
    return ob


def world_matrices(nodes, pose, origin):
    """Object world matrices (glTF axes) of every node for a rig pose."""
    tf = rig.world_transforms(nodes, pose)
    out = {}
    for n, nd in nodes.items():
        Rw, tw = tf[n]
        M = np.eye(4)
        M[:3, :3] = Rw @ nd.get("rot", np.eye(3))
        M[:3, 3] = Rw @ nd["pivot"] + tw - origin
        out[n] = M
    return out


def key_clips(objs, nodes, clips, origin):
    """One NLA track per clip, plus "Stand" (rest) that stays active so the file exports in rest pose."""
    sc = bpy.context.scene

    def key(pose, frame):
        W = world_matrices(nodes, pose, origin)
        for n, ob in objs.items():
            p = nodes[n]["parent"]
            L = np.linalg.inv(W[p]) @ W[n] if p in objs else W[n]
            Lb = to_b(L)
            ob.rotation_quaternion = Lb.to_quaternion()
            ob.keyframe_insert("rotation_quaternion", frame=frame)
            if p not in objs:
                ob.location = Lb.translation
                ob.keyframe_insert("location", frame=frame)

    def to_track(name, start):
        for ob in objs.values():
            ad = ob.animation_data
            act = ad.action
            act.name = name + "_" + ob.name
            for fc in act.fcurves:
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"
            tr = ad.nla_tracks.new()
            tr.name = name
            st = tr.strips.new(name, start, act)
            st.extrapolation = "NOTHING" if name != "Stand" else "HOLD"
            ad.action = None

    fps = 24
    for name, clip in clips.items():
        fps = clip.get("fps", 24)
        for f, pose in enumerate(clip["frames"]):
            key(pose, f + 1)
        to_track(name, 1)
    key({}, -20)
    key({}, -19)
    to_track("Stand", -20)
    sc.render.fps = fps
    sc.frame_set(-20)


def build_output(a, out):
    clear()
    path = a.path(out["file"])
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)
    stem = os.path.splitext(os.path.basename(path))[0]
    variant, k = out.get("variant"), out.get("scale", 1.0)
    p = a.params(variant)
    nodes_all = a.build(variant, k)
    want = [n for n in nodes_all if n in out.get("nodes", list(nodes_all)) and n not in out.get("exclude", [])]
    nodes = {n: dict(nodes_all[n]) for n in want}
    origin = nodes_all[out["origin"]]["pivot"] if out.get("origin") else np.zeros(3)
    atlas = a.gen.ATLAS
    surfaces = out.get("vertex_surfaces")
    vehicle = out.get("vehicle")
    if vehicle and surfaces: raise ValueError('vehicle and vertex_surfaces cannot be combined')
    if surfaces:
        for nd in nodes.values():
            nd["vertex_surfaces"] = surfaces
            nd["runtime_uv"] = bool(out.get("runtime_uv", False))
    if vehicle:
        atlas_rgb, _ = atlas.paint()
        for nd in nodes.values():
            nd["vehicle"] = vehicle
            nd["vehicle_atlas_rgb"] = atlas_rgb
    mat = None if surfaces else material(atlas, folder, stem, out.get("kit_mask"), bool(vehicle))
    objs = {n: node_object(n, nodes[n], mat, atlas) for n in want}
    W = world_matrices(nodes_all, {}, origin)
    for n in want:                       # generator order lists parents before children
        ob = objs[n]
        par = nodes[n]["parent"]
        if par in objs:
            ob.parent = objs[par]
            ob.matrix_parent_inverse.identity()
        ob.matrix_world = to_b(W[n])
        bpy.context.view_layer.update()
    if hasattr(a.gen, "extras"):
        for n, kv in (a.gen.extras(p, k) or {}).items():
            if n in objs:
                for key, val in kv.items():
                    objs[n][key] = val
    clips = a.gen.clips(nodes_all, p) if (out.get("clips") and hasattr(a.gen, "clips")) else {}
    if clips:
        key_clips(objs, nodes_all, clips, origin)
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(folder, stem + ".blend"))
    with replacing(path) as temporary:
        bpy.ops.export_scene.gltf(
            filepath=temporary, export_format="GLB", export_yup=True, export_apply=True, export_extras=True,
            export_attributes=True, export_texcoords=True, export_normals=True, export_tangents=False,
            export_materials="EXPORT", export_image_format="AUTO", export_cameras=False, export_lights=False,
            export_animations=bool(clips), export_animation_mode="NLA_TRACKS", export_anim_slide_to_zero=True,
            export_optimize_animation_size=False, export_optimize_animation_keep_anim_object=True,
            export_skins=False, export_morph=False, use_selection=False,
            **({"export_vertex_color": "ACTIVE"} if vehicle else {}))
    for f in os.listdir(folder):
        if f.endswith(".blend1"):
            os.remove(os.path.join(folder, f))
    print("BUILT", out["file"], "%d nodes" % len(want), "clips %s" % sorted(clips))


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    a = Asset(argv[0])
    pick = set(argv[1:])
    for out in a.outputs():
        if not pick or out["file"] in pick:
            build_output(a, out)


if __name__ == "__main__":
    main()
