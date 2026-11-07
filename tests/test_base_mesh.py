import contextlib
import io
import json
import tempfile
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))  # tests/synthetic_glb.py

from lowpoly_workshop import base_mesh, pixal3d
from lowpoly_workshop.cli import main
from lowpoly_workshop.kit.atlas import Atlas
from lowpoly_workshop.spec import validate_nodes
from lowpoly_workshop.templates import create
from synthetic_glb import GlbBuilder, box, disc, single_mesh

GREY = Atlas({"dark": ("#404040", None), "mid": ("#808080", None), "light": ("#c0c0c0", None)})


def linear(srgb):
    return float(base_mesh.srgb_to_linear(srgb / 255.0))


def cells_of(nodes):
    return [cell for nd in nodes.values() for _, cell, _, _ in nd["faces"]]


def quiet(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        main(argv)
    return out.getvalue(), err.getvalue()


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.asset = create(self.root / "prop", "static-prop")
        self.src = self.root / "src"
        self.src.mkdir()

    def triangle_glb(self, name, colour, dtype="<f4", factor=None):
        """One triangle whose three vertices carry `colour` (rows of RGB or RGBA)."""
        g = GlbBuilder()
        mat = g.material(factor) if factor is not None else None
        extra = {"material": mat} if mat is not None else {}
        pos = [[0, 0, 0], [1, 0, 0], [0, 1, 0]]
        g.node("Tri", mesh=g.mesh([dict(pos=pos, tri=[[0, 1, 2]], color=(colour, dtype), **extra)]))
        return g.write(self.src / name)

    def import_prop(self, path, **kw):
        kw.setdefault("name", "prop")
        return base_mesh.import_base(self.asset, path, **kw)

    def ledger(self, name="prop"):
        return json.loads((self.asset / "inputs/base" / f"{name}.json").read_text())

    def report(self, name="prop"):
        return json.loads((self.asset / "inputs/base" / f"{name}_lowpoly.json").read_text())


class ColourSourceTests(Fixture):
    def test_color0_is_linear_and_matched_to_palette_in_srgb(self):
        mid = linear(128)  # linear 0.2158 is sRGB 128; read as sRGB it would be 55 and pick "dark"
        for dtype, rows in (("<f4", [[mid] * 3] * 3),
                            ("<f4", [[mid, mid, mid, 0.3]] * 3),
                            ("u1", [[round(mid * 255)] * 3] * 3),
                            ("u1", [[round(mid * 255)] * 3 + [90]] * 3),
                            ("<u2", [[round(mid * 65535)] * 4] * 3)):
            with self.subTest(dtype=dtype, width=len(rows[0])):
                path = self.triangle_glb("c.glb", np.array(rows), dtype)
                nodes = base_mesh.load_glb_node(path, atlas=GREY)
                self.assertEqual(cells_of(nodes), ["mid"])

    def test_vertex_colours_average_in_linear_light(self):
        # corners 0, 0, 1 (linear): the mean is 1/3 linear = sRGB 157 (nearest "mid"); averaging the sRGB values
        # instead would give 85 (nearest "dark")
        rows = [[0, 0, 0], [0, 0, 0], [1, 1, 1]]
        path = self.triangle_glb("avg.glb", np.array(rows))
        self.assertEqual(cells_of(base_mesh.load_glb_node(path, atlas=GREY)), ["mid"])

    def test_base_color_factor_multiplies_vertex_colours(self):
        path = self.triangle_glb("f.glb", np.ones((3, 3)), factor=[linear(128)] * 3 + [1.0])
        self.assertEqual(cells_of(base_mesh.load_glb_node(path, atlas=GREY)), ["mid"])
        path = self.triangle_glb("f2.glb", np.full((3, 3), 0.5), factor=[2 * linear(128), 2 * linear(128), 2 * linear(128), 1])
        # 0.5 * 2*0.2158 = 0.2158 linear
        self.assertEqual(cells_of(base_mesh.load_glb_node(path, atlas=GREY)), ["mid"])

    def test_material_factor_alone_and_no_colour_at_all(self):
        g = GlbBuilder()
        light = g.material([linear(190)] * 3 + [1.0])
        pos, tri = box((0, 0, 0), (1, 1, 1))
        g.node("Lit", mesh=g.mesh([dict(pos=pos, tri=tri, material=light)]))
        nodes = base_mesh.load_glb_node(g.write(self.src / "m.glb"), atlas=GREY)
        self.assertEqual(set(cells_of(nodes)), {"light"})
        plain = single_mesh(self.src / "p.glb", *box((0, 0, 0), (1, 1, 1)))
        self.assertEqual(set(cells_of(base_mesh.load_glb_node(plain, atlas=GREY))), {"dark"})  # first flat cell

    def test_texture_wins_over_vertex_colour_and_factor(self):
        img = Image.new("RGB", (4, 4), (192, 192, 192))
        g = GlbBuilder()
        mat = g.material([1, 0, 0, 1], image=img)
        pos = [[0, 0, 0], [1, 0, 0], [0, 1, 0]]
        uv = [[0.5, 0.5]] * 3
        g.node("T", mesh=g.mesh([dict(pos=pos, tri=[[0, 1, 2]], uv=uv, material=mat,
                                      color=(np.array([[0.0, 0.0, 0.0]] * 3), "<f4"))]))
        path = g.write(self.src / "t.glb")
        self.assertEqual(cells_of(base_mesh.load_glb_node(path, atlas=GREY)), ["light"])
        self.assertEqual(base_mesh.colour_sources(base_mesh.read_scene(path))["texture"]["primitives"], 1)

    def test_decal_mode_keeps_working_with_texture_uvs(self):
        img = Image.new("RGB", (8, 8), (120, 90, 60))
        tex = self.root / "tex.png"
        img.save(tex)
        atlas = pixal3d.make_decal_atlas(tex, cell="surface", size=512)
        pos, tri = box((0, 0, 0), (1, 1, 1))
        uv = np.random.default_rng(1).random((8, 2))
        path = single_mesh(self.src / "d.glb", pos, tri, uv=uv)
        nodes = base_mesh.load_glb_node(path, atlas=atlas, cell="surface", mode="decal")
        self.assertEqual(len(validate_nodes(nodes, atlas)["Model"]["faces"]), 12)


class SkinTests(Fixture):
    def skinned(self, weights, mesh_translation=(5, 0, 0)):
        """A triangle skinned to two joints that sit 1 m and 3 m above their bind pose."""
        g = GlbBuilder()
        j0 = g.node("J0", translation=[0, 1, 0], root=False)
        j1 = g.node("J1", translation=[0, 3, 0], root=False)
        root = g.node("Armature", children=[j0, j1])
        skin = g.skin([j0, j1], ibm=[np.eye(4), np.eye(4)])  # bind pose at the origin
        pos = [[0, 0, 0], [1, 0, 0], [0, 0, 1]]
        prim = dict(pos=pos, tri=[[0, 1, 2]], joints=([[0, 1, 0, 0]] * 3, "<u1"), weights=(weights, "<f4"))
        # glTF ignores this node's own transform for a skinned mesh
        g.node("Body", mesh=g.mesh([prim]), skin=skin, translation=list(mesh_translation),
               rotation=[0.0, 0.7071068, 0.0, 0.7071068])
        g.animation("Walk", j0)
        g.animation("Idle", j1)
        self.assertEqual(root, 2)
        return g.write(self.src / "skin.glb")

    def test_rest_pose_skinning_ignores_mesh_node_and_applies_joints(self):
        scene = base_mesh.read_scene(self.skinned([[1, 0, 0, 0]] * 3))
        pts = scene.prims[0].pos
        np.testing.assert_allclose(pts, [[0, 1, 0], [1, 1, 0], [0, 1, 1]], atol=1e-9)
        self.assertTrue(scene.prims[0].skinned)

    def test_blended_weights(self):
        scene = base_mesh.read_scene(self.skinned([[0.5, 0.5, 0, 0]] * 3))
        np.testing.assert_allclose(scene.prims[0].pos[:, 1], [2, 2, 2], atol=1e-9)

    def test_unskinned_mesh_keeps_its_node_transform(self):
        g = GlbBuilder()
        g.node("Plain", mesh=g.mesh([dict(pos=[[0, 0, 0], [1, 0, 0], [0, 1, 0]], tri=[[0, 1, 2]])]),
               translation=[5, 0, 0])
        scene = base_mesh.read_scene(g.write(self.src / "plain.glb"))
        np.testing.assert_allclose(scene.prims[0].pos[:, 0], [5, 6, 5])

    def test_import_reports_joints_and_clips_and_drops_the_skin(self):
        self.import_prop(self.skinned([[1, 0, 0, 0]] * 3))
        report = self.report()
        self.assertEqual(report["skin"], {"skinned_primitives": 1, "skins": 1, "joints": 2})
        self.assertEqual(report["animations"], ["Walk", "Idle"])
        self.assertTrue(any("skin" in w for w in report["warnings"]))
        out = base_mesh.read_scene(self.asset / "inputs/base/prop_lowpoly.glb")
        self.assertNotIn("skins", out.js)
        self.assertNotIn("animations", out.js)
        self.assertEqual(base_mesh.bounds_of(out.prims)[0][1], 0.0)

    def test_hierarchy_scale_matrix_and_mirroring(self):
        g = GlbBuilder()
        child = g.node("Child", mesh=g.mesh([dict(pos=[[0, 0, 0], [1, 0, 0], [0, 1, 0]], tri=[[0, 1, 2]])]),
                       translation=[1, 0, 0], root=False)
        g.node("Parent", scale=[2, 2, 2], children=[child])
        m = np.eye(4)
        m[:3, 3] = [0, 0, 7]
        g.node("Matrix", mesh=g.mesh([dict(pos=[[0, 0, 0], [1, 0, 0], [0, 1, 0]], tri=[[0, 1, 2]])]),
               matrix=m.T.ravel().tolist())
        g.node("Mirror", mesh=g.mesh([dict(pos=[[0, 0, 0], [1, 0, 0], [0, 1, 0]], tri=[[0, 1, 2]])]),
               scale=[-1, 1, 1])
        scene = base_mesh.read_scene(g.write(self.src / "h.glb"))
        by = {p.name: p for p in scene.prims}
        np.testing.assert_allclose(by["Child"].pos, [[2, 0, 0], [4, 0, 0], [2, 2, 0]])
        np.testing.assert_allclose(by["Matrix"].pos[:, 2], [7, 7, 7])
        t = by["Mirror"].pos[by["Mirror"].tri[0]]
        normal = np.cross(t[1] - t[0], t[2] - t[0])
        self.assertGreater(normal[2], 0)  # mirrored winding is repaired, the face still looks along +z


class NodeLayoutTests(Fixture):
    def parts_glb(self):
        g = GlbBuilder()
        for name, lo in (("Head", (0, 1, 0)), ("Head", (2, 1, 0)), ("Axe/Blade 1", (4, 0, 0)), (None, (6, 0, 0))):
            pos, tri = box(lo, [v + 1 for v in lo])
            g.node(name, mesh=g.mesh([dict(pos=pos, tri=tri)]))
        return g.write(self.src / "parts.glb")

    def test_separate_nodes_are_named_after_gltf_nodes_sanitised_and_unique(self):
        nodes = base_mesh.load_glb_node(self.parts_glb(), node_name="Hero", atlas=GREY, separate_nodes=True)
        self.assertEqual(list(nodes), ["Head", "Head_2", "Axe_Blade_1", "Hero_3"])
        for nd in nodes.values():
            self.assertEqual(len(nd["faces"]), 12)
        validate_nodes(nodes, GREY)

    def test_merged_node_is_the_default(self):
        nodes = base_mesh.load_glb_node(self.parts_glb(), node_name="Hero", atlas=GREY)
        self.assertEqual(list(nodes), ["Hero"])
        self.assertEqual(len(nodes["Hero"]["faces"]), 48)

    def test_import_separate_nodes_keeps_one_node_per_source_node(self):
        self.import_prop(self.parts_glb(), separate_nodes=True)
        out = self.asset / "inputs/base/prop_lowpoly.glb"
        nodes = base_mesh.load_glb_node(out, atlas=GREY, separate_nodes=True)
        self.assertEqual(list(nodes), ["Head", "Head_2", "Axe_Blade_1", "prop_3"])
        self.assertEqual([n["name"] for n in self.report()["nodes"]], list(nodes))
        base_mesh.import_base(self.asset, self.parts_glb(), "all")
        self.assertEqual(list(base_mesh.load_glb_node(self.asset / "inputs/base/all_lowpoly.glb", atlas=GREY)), ["Model"])


class DropTests(Fixture):
    def figure_glb(self, name="fig.glb", plinth_node="Plinth", one_node=False, plinth_r=0.6, plinth_h=0.1):
        g = GlbBuilder()
        fp, ft = box((-0.2, plinth_h, -0.1), (0.2, 1.0, 0.1))
        pp, pt = disc(plinth_r, 0.0, plinth_h)
        if one_node:
            pos = np.concatenate([fp, pp])
            tri = np.concatenate([ft, pt + len(fp)])
            g.node("Both", mesh=g.mesh([dict(pos=pos, tri=tri)]))
        else:
            g.node("Figure", mesh=g.mesh([dict(pos=fp, tri=ft)]))
            g.node(plinth_node, mesh=g.mesh([dict(pos=pp, tri=pt)]))
        return g.write(self.src / name)

    def test_drop_node_by_name_reports_and_removes_it(self):
        self.import_prop(self.figure_glb(), drop_node=["Plinth"])
        report = self.report()
        self.assertEqual(report["nodes_dropped"], [{"name": "Plinth", "triangles": 64, "reason": "drop-node"}])
        self.assertEqual(report["triangles"]["source"], 76)
        self.assertEqual(report["triangles"]["final"], 12)
        lo, hi = base_mesh.bounds_of(base_mesh.read_scene(self.asset / "inputs/base/prop_lowpoly.glb").prims)
        self.assertAlmostEqual(lo[1], 0.0)  # grounded on the figure's own feet
        self.assertEqual(self.ledger()["parameters"]["drop_node"], ["Plinth"])

    def test_drop_node_takes_the_children_and_refuses_unknown_names(self):
        g = GlbBuilder()
        pos, tri = box((0, 0, 0), (1, 1, 1))
        kid = g.node("Gem", mesh=g.mesh([dict(pos=pos, tri=tri)]), root=False)
        g.node("Group", children=[kid])
        g.node("Keep", mesh=g.mesh([dict(pos=pos + 3, tri=tri)]))
        path = g.write(self.src / "g.glb")
        self.import_prop(path, drop_node=["Group"])
        self.assertEqual(self.report()["nodes_dropped"][0]["triangles"], 12)
        with self.assertRaisesRegex(ValueError, "No glTF node named 'Nope'"):
            self.import_prop(path, name="other", drop_node=["Nope"])
        with self.assertRaisesRegex(ValueError, "no geometry"):
            self.import_prop(path, name="other", drop_node=["Group", "Keep"])
        self.assertFalse((self.asset / "inputs/base/other.json").exists())

    def test_drop_plinth_node_level(self):
        self.import_prop(self.figure_glb(plinth_node="Disc"), drop_plinth=True)
        dropped = self.report()["nodes_dropped"]
        self.assertEqual(len(dropped), 1)
        self.assertEqual((dropped[0]["name"], dropped[0]["reason"], dropped[0]["triangles"]),
                         ("Disc", "plinth-node", 64))
        self.assertEqual(self.report()["triangles"]["final"], 12)

    def test_drop_plinth_component_level_inside_one_node(self):
        self.import_prop(self.figure_glb(one_node=True), drop_plinth=True)
        dropped = self.report()["nodes_dropped"][0]
        self.assertEqual((dropped["reason"], dropped["triangles"]), ("plinth-component", 64))
        self.assertEqual(self.report()["triangles"]["final"], 12)

    def test_drop_plinth_refuses_when_unsure(self):
        def refused(path, pattern):
            with self.assertRaisesRegex(base_mesh.PlinthRefused, pattern):
                self.import_prop(path, name="no", drop_plinth=True)
            self.assertFalse((self.asset / "inputs/base/no.json").exists())  # nothing written

        # one connected piece: nothing to separate
        pos, tri = box((0, 0, 0), (1, 2, 1))
        refused(single_mesh(self.src / "one.glb", pos, tri), "only one piece")
        # two pieces on the ground side by side: which one is the base?
        g = GlbBuilder()
        for k, lo in enumerate(((0, 0, 0), (3, 0, 0))):
            p, t = box(lo, [v + s for v, s in zip(lo, (1, 0.1, 1))])
            g.node(f"Slab{k}", mesh=g.mesh([dict(pos=p, tri=t)]))
        refused(g.write(self.src / "pair.glb"), "more than one piece reaches the lowest level")
        # the lowest piece is tall, not a flat base
        g = GlbBuilder()
        for name, lo, hi in (("Leg", (0, 0, 0), (0.3, 0.9, 0.3)), ("Torso", (-0.2, 0.9, -0.2), (0.5, 1.5, 0.5))):
            p, t = box(lo, hi)
            g.node(name, mesh=g.mesh([dict(pos=p, tri=t)]))
        refused(g.write(self.src / "tall.glb"), "not a plinth")
        # a wide flat piece that the rest overhangs
        refused(self.figure_glb("small.glb", plinth_r=0.1), "overhangs|not much wider")

    def test_plinth_and_drop_node_are_exclusive(self):
        with self.assertRaisesRegex(ValueError, "not both"):
            self.import_prop(self.figure_glb(), drop_plinth=True, drop_node=["Plinth"])


class NormaliseTests(Fixture):
    def test_front_matrices_turn_the_front_to_plus_z(self):
        for front, direction in (("+z", (0, 0, 1)), ("-z", (0, 0, -1)), ("+x", (1, 0, 0)), ("-x", (-1, 0, 0))):
            np.testing.assert_allclose(base_mesh.front_matrix(front) @ direction, [0, 0, 1], atol=1e-12)
            np.testing.assert_allclose(base_mesh.front_matrix(front) @ [0, 1, 0], [0, 1, 0])
        np.testing.assert_allclose(base_mesh.front_matrix("x") @ (1, 0, 0), [0, 0, 1])
        with self.assertRaises(ValueError):
            base_mesh.front_matrix("up")

    def test_front_height_ground_and_centre(self):
        # a wedge in centimetres, nose pointing +X, floating and off-centre
        pos = np.array([[10, 50, 30], [10, 250, 30], [10, 250, 70], [10, 50, 70], [110, 50, 50], [110, 250, 50]], float)
        tri = np.array([[0, 1, 2], [0, 2, 3], [0, 4, 1], [1, 4, 5], [3, 2, 5], [3, 5, 4], [1, 5, 2], [0, 3, 4]])
        path = single_mesh(self.src / "w.glb", pos, tri)
        self.import_prop(path, front="+x", height=2.0)
        scene = base_mesh.read_scene(self.asset / "inputs/base/prop_lowpoly.glb")
        lo, hi = base_mesh.bounds_of(scene.prims)
        np.testing.assert_allclose([lo[1], hi[1]], [0.0, 2.0], atol=1e-6)
        self.assertAlmostEqual((lo[0] + hi[0]) / 2, 0.0, places=6)
        self.assertAlmostEqual((lo[2] + hi[2]) / 2, 0.0, places=6)
        # the nose that pointed along +X now points along +Z: the long side of the wedge runs along Z
        self.assertAlmostEqual(hi[2] - lo[2], 100 * 0.01, places=5)
        self.assertAlmostEqual(hi[0] - lo[0], 40 * 0.01, places=5)
        nose = scene.prims[0].pos[:, 2].max()
        self.assertGreater(nose, 0)
        self.assertEqual(self.report()["height_m"], 2.0)

    def test_without_height_the_scale_is_kept(self):
        pos, tri = box((0, 5, 0), (1, 7, 1))
        self.import_prop(single_mesh(self.src / "s.glb", pos, tri))
        lo, hi = base_mesh.bounds_of(base_mesh.read_scene(self.asset / "inputs/base/prop_lowpoly.glb").prims)
        np.testing.assert_allclose([lo[1], hi[1]], [0.0, 2.0], atol=1e-6)

    def test_vertex_colours_survive_normalising(self):
        mid = linear(128)
        pos, tri = box((0, 0, 0), (1, 1, 1))
        path = single_mesh(self.src / "c.glb", pos, tri, color=(np.full((8, 4), [mid, mid, mid, 1.0]), "<f4"))
        self.import_prop(path, height=3.0)
        out = self.asset / "inputs/base/prop_lowpoly.glb"
        self.assertEqual(set(cells_of(base_mesh.load_glb_node(out, atlas=GREY))), {"mid"})
        self.assertEqual(self.report()["colour_sources"], {"vertex": {"primitives": 1, "triangles": 12}})


class LedgerTests(Fixture):
    def test_source_copied_unchanged_and_provenance_recorded(self):
        pos, tri = box((0, 0, 0), (1, 1, 1))
        path = single_mesh(self.src / "orig.glb", pos, tri)
        before = path.read_bytes()
        result = self.import_prop(path, licence="CC-BY-4.0", credit="A. Maker", source_url="https://example.org/m/1",
                                  front="-z", height=1.5, budget=100)
        self.assertEqual(result["source"].read_bytes(), before)
        self.assertEqual(path.read_bytes(), before)
        ledger = self.ledger()
        import hashlib
        self.assertEqual(ledger["source"]["sha256"], hashlib.sha256(before).hexdigest())
        self.assertEqual((ledger["licence"], ledger["credit"], ledger["source"]["url"]),
                         ("CC-BY-4.0", "A. Maker", "https://example.org/m/1"))
        self.assertEqual(ledger["source"]["file"], "inputs/base/prop_source.glb")
        self.assertEqual(ledger["parameters"], {"front": "-z", "height_m": 1.5, "budget": 100, "drop_plinth": False,
                                                "drop_node": [], "separate_nodes": False})
        self.assertEqual(ledger["triangles"], {"before": 12, "after": 12})
        self.assertEqual(ledger["tool"]["name"], "lowpoly-workshop")
        self.assertTrue(ledger["imported_at"].endswith("Z"))
        self.assertNotIn(str(self.root), json.dumps(ledger))  # no absolute paths
        self.assertNotIn(str(self.root), (self.asset / "inputs/base/prop_lowpoly.json").read_text())

    def test_a_different_file_is_refused_until_replace_and_the_replacement_is_recorded(self):
        a = single_mesh(self.src / "a.glb", *box((0, 0, 0), (1, 1, 1)))
        b = single_mesh(self.src / "b.glb", *box((0, 0, 0), (2, 2, 2)))
        self.import_prop(a, licence="CC0-1.0", credit="first")
        with self.assertRaisesRegex(ValueError, "--replace"):
            self.import_prop(b)
        self.assertEqual((self.asset / "inputs/base/prop_source.glb").read_bytes(), a.read_bytes())
        self.import_prop(b, replace=True, licence="CC-BY-4.0", credit="second")
        self.assertEqual((self.asset / "inputs/base/prop_source.glb").read_bytes(), b.read_bytes())
        ledger = self.ledger()
        self.assertEqual((ledger["licence"], ledger["credit"]), ("CC-BY-4.0", "second"))
        self.assertEqual(len(ledger["history"]), 1)
        event = ledger["history"][0]
        self.assertEqual((event["event"], event["previous_licence"], event["previous_credit"]),
                         ("replaced", "CC0-1.0", "first"))
        import hashlib
        self.assertEqual(event["previous_sha256"], hashlib.sha256(a.read_bytes()).hexdigest())
        self.assertEqual(a.read_bytes(), single_mesh(self.src / "a2.glb", *box((0, 0, 0), (1, 1, 1))).read_bytes())

    def test_replacing_does_not_inherit_the_old_licence(self):
        a = single_mesh(self.src / "a.glb", *box((0, 0, 0), (1, 1, 1)))
        b = single_mesh(self.src / "b.glb", *box((0, 0, 0), (2, 2, 2)))
        self.import_prop(a, licence="CC0-1.0", credit="first")
        self.import_prop(b, replace=True)
        self.assertEqual((self.ledger()["licence"], self.ledger()["credit"]), (None, None))

    def test_the_same_file_can_be_imported_again_with_other_parameters(self):
        a = single_mesh(self.src / "a.glb", *box((0, 0, 0), (1, 1, 1)))
        self.import_prop(a, licence="CC0-1.0", credit="me", height=1.0)
        stamp = self.ledger()["imported_at"]
        self.import_prop(a, height=2.0)
        ledger = self.ledger()
        self.assertEqual((ledger["licence"], ledger["credit"]), ("CC0-1.0", "me"))
        self.assertEqual(ledger["parameters"]["height_m"], 2.0)
        self.assertEqual(ledger["imported_at"], stamp)
        self.assertEqual([h["event"] for h in ledger["history"]], ["reimported"])
        self.assertEqual(ledger["history"][0]["previous_parameters"]["height_m"], 1.0)

    def test_a_failed_import_writes_nothing(self):
        a = single_mesh(self.src / "a.glb", *box((0, 0, 0), (1, 1, 1)))
        with self.assertRaises(ValueError):
            self.import_prop(a, height=-1)
        with self.assertRaises(ValueError):
            self.import_prop(self.src / "a.glb", name="bad name")
        bad = self.src / "not.glb"
        bad.write_bytes(b"not a glb at all")
        with self.assertRaises(ValueError):
            self.import_prop(bad)
        with self.assertRaises(FileNotFoundError):
            self.import_prop(self.src / "missing.glb")
        self.assertFalse((self.asset / "inputs/base").exists())

    def test_status_reports_a_modified_source(self):
        a = single_mesh(self.src / "a.glb", *box((0, 0, 0), (1, 1, 1)))
        self.import_prop(a)
        self.assertTrue(base_mesh.status(self.asset, "prop")["source_matches_ledger"])
        (self.asset / "inputs/base/prop_source.glb").write_bytes(b"changed")
        self.assertFalse(base_mesh.status(self.asset, "prop")["source_matches_ledger"])
        b = single_mesh(self.src / "b.glb", *box((0, 0, 0), (2, 2, 2)))
        with self.assertRaisesRegex(ValueError, "--replace"):
            self.import_prop(b)


class ReductionTests(Fixture):
    def dense_glb(self):
        g = GlbBuilder()
        for k in range(2):
            p, t = disc(0.5, 0.0, 1.0, n=24 if k else 12)
            g.node(f"Part{k}", mesh=g.mesh([dict(pos=p + [k * 2, 0, 0], tri=t,
                                                 color=(np.tile([[0.2 + 0.4 * k, 0.1, 0.1]], (len(p), 1)), "<f4"))]))
        return g.write(self.src / "dense.glb")

    def test_normalising_needs_no_blender_when_the_mesh_fits_the_budget(self):
        def forbidden(*a, **k):
            raise AssertionError("Blender must not be looked up")
        pos, tri = box((0, 0, 0), (1, 1, 1))
        with patch("lowpoly_workshop.pipeline.find_blender", side_effect=forbidden):
            self.import_prop(single_mesh(self.src / "s.glb", pos, tri), budget=12, height=1.0)
        self.assertFalse(self.report()["triangles"]["reduced"])

    def test_reduction_without_blender_fails_clearly_and_writes_nothing(self):
        with patch("lowpoly_workshop.pipeline.find_blender", side_effect=FileNotFoundError("Blender not found.")):
            with self.assertRaises(FileNotFoundError) as caught:
                self.import_prop(self.dense_glb(), budget=40)
        message = str(caught.exception)
        self.assertIn("needs Blender", message)
        self.assertIn("KIT_BLENDER", message)
        self.assertIn("--budget", message)
        self.assertFalse((self.asset / "inputs/base").exists())
        with patch("lowpoly_workshop.pipeline.find_blender", side_effect=FileNotFoundError("nope")):
            with self.assertRaises(SystemExit) as exit_info, contextlib.redirect_stderr(io.StringIO()) as err:
                main([str(self.asset), "base", "import", str(self.dense_glb()), "--budget", "40"])
        self.assertEqual(exit_info.exception.code, 2)
        self.assertIn("needs Blender", err.getvalue())

    def test_reduction_budget_is_split_across_nodes_and_colours_are_carried_over(self):
        calls = []

        def fake_reduce(tris, budget, name, workdir):
            calls.append((name, len(tris), budget))
            return tris[:budget]  # stands in for Blender's collapse: a subset of the source triangles

        with patch.object(base_mesh, "_require_blender", return_value="blender"), \
                patch.object(base_mesh, "_reduce_with_blender", side_effect=fake_reduce):
            self.import_prop(self.dense_glb(), budget=40, height=1.0, separate_nodes=True)
        self.assertEqual([c[0] for c in calls], ["Part0", "Part1"])
        self.assertEqual(sum(c[2] for c in calls), 40)
        self.assertLess(calls[0][2], calls[1][2])  # the coarser part keeps fewer triangles
        report = self.report()
        self.assertTrue(report["triangles"]["reduced"])
        self.assertEqual(report["triangles"]["final"], 40)
        self.assertEqual(report["triangles"]["source"], 12 * 4 + 24 * 4)
        scene = base_mesh.read_scene(self.asset / "inputs/base/prop_lowpoly.glb")
        lo, hi = base_mesh.bounds_of(scene.prims)
        self.assertAlmostEqual(lo[1], 0.0)
        self.assertAlmostEqual(hi[1], 1.0)
        for prim, expect in zip(scene.prims, (0.2, 0.6)):
            self.assertEqual(base_mesh.colour_source(scene, prim), "vertex")
            np.testing.assert_allclose(prim.col[:, 0], expect, atol=1e-6)
        self.assertTrue(any("textures were dropped" in w for w in report["warnings"]))

    def test_budget_too_small_for_the_nodes(self):
        with patch.object(base_mesh, "_require_blender", return_value="blender"):
            with self.assertRaisesRegex(ValueError, "too small"):
                self.import_prop(self.dense_glb(), budget=6, separate_nodes=True)

    def test_blender_reduction_script_shares_the_pixal3d_code(self):
        from lowpoly_workshop import reduce
        config = {"raw_glb": "a.glb", "low_glb": "b.glb", "atlas_png": "c.png", "report_json": "d.json",
                  "budget": 50, "height": 0.0, "node_name": "N", "ground": False, "rotate_front": False,
                  "planar_deg": 3.0, "weld_dist": 1e-4, "normalize": False}
        code = reduce.reduce_code(config)
        compile(code, "reduce", "exec")
        self.assertIn("LowpolyBudget", code)
        self.assertIn('"normalize": false', code)
        pix = pixal3d.blender_mcp_decimate_code(self.asset, budget=400, height=0.5, node_name="Crate", ground=True)
        self.assertNotIn("normalize", pix.split("CFG = json.loads(")[1].split("\n")[0])  # Pixal3D config unchanged


class PaletteTests(Fixture):
    def three_colour_glb(self):
        g = GlbBuilder()
        for k, srgb in enumerate(((200, 40, 40), (40, 160, 60), (30, 40, 200))):
            pos, tri = box((k * 2, 0, 0), (k * 2 + 1, 1, 1))
            col = np.tile([[linear(c) for c in srgb]], (8, 1))
            g.node(f"N{k}", mesh=g.mesh([dict(pos=pos, tri=tri, color=(col, "<f4"))]))
        return g.write(self.src / "three.glb")

    def test_palette_proposal_recovers_the_base_colours(self):
        proposal = base_mesh.propose_palette(self.three_colour_glb(), 3)
        self.assertEqual(sorted(p["hex"] for p in proposal), sorted(["#c82828", "#28a03c", "#1e28c8"]))
        self.assertAlmostEqual(sum(p["share"] for p in proposal), 1.0, places=3)
        self.assertEqual(len({p["name"] for p in proposal}), 3)
        self.assertEqual(proposal, base_mesh.propose_palette(self.three_colour_glb(), 3))  # deterministic
        cells = base_mesh.palette_cells(proposal, channels=("R", "G"))
        atlas = Atlas(cells)
        nodes = base_mesh.load_glb_node(self.three_colour_glb(), atlas=atlas, separate_nodes=True)
        self.assertEqual(len({cells_of({k: v})[0] for k, v in nodes.items()}), 3)  # each part gets its own cell

    def test_fewer_colours_than_cells_and_merging(self):
        proposal = base_mesh.propose_palette(self.three_colour_glb(), 12)
        self.assertEqual(len(proposal), 3)
        self.assertEqual(len(base_mesh.propose_palette(self.three_colour_glb(), 1)), 1)

    def test_names_and_errors(self):
        self.assertEqual(base_mesh.colour_name((200, 40, 40)), "red")
        self.assertEqual(base_mesh.colour_name((20, 20, 20)), "black")
        self.assertEqual(base_mesh.colour_name((128, 128, 128)), "grey")
        self.assertEqual(base_mesh.colour_name((250, 250, 250)), "white")
        plain = single_mesh(self.src / "plain.glb", *box((0, 0, 0), (1, 1, 1)))
        with self.assertRaisesRegex(ValueError, "no colours"):
            base_mesh.propose_palette(plain, 4)


class CliTests(Fixture):
    def test_import_status_palette_and_flags(self):
        g = GlbBuilder()
        pos, tri = box((0, 0, 0), (1, 2, 1))
        col = np.tile([[0.7, 0.1, 0.1]], (8, 1))
        g.node("Body", mesh=g.mesh([dict(pos=pos, tri=tri, color=(col, "<f4"))]))
        path = g.write(self.src / "cli.glb")
        out, err = quiet([str(self.asset), "base", "import", str(path), "--name", "hero", "--front", "-z",
                          "--height", "1", "--licence", "CC0-1.0", "--credit", "Someone",
                          "--source-url", "https://example.org/x", "--separate-nodes"])
        self.assertIn("BASE imported inputs/base/hero_lowpoly.glb 12 -> 12 triangles", out)
        self.assertEqual(self.ledger("hero")["parameters"]["front"], "-z")
        status, _ = quiet([str(self.asset), "base", "status", "--name", "hero"])
        self.assertTrue(json.loads(status)["source_matches_ledger"])
        palette, _ = quiet([str(self.asset), "base", "palette", "--name", "hero", "--cells", "2"])
        self.assertEqual(json.loads(palette)[0]["hex"], "#da5959")
        _, warning = quiet([str(self.asset), "base", "import", str(path), "--name", "other"])
        self.assertIn("no --licence", warning)
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()) as err:
            main([str(self.asset), "base", "import", str(path), "--name", "n3", "--drop-node", "Nope", "--licence", "x"])
        self.assertIn("No glTF node named 'Nope'", err.getvalue())
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            main([str(self.asset), "base", "import", str(path), "--drop-plinth", "--drop-node", "A"])
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            main([str(self.asset), "base", "bogus"])


class GeneratorTests(Fixture):
    def test_a_project_generator_can_start_from_the_imported_base(self):
        from lowpoly_workshop.kit.asset import Asset
        from lowpoly_workshop.kit.mesh import triangles
        from lowpoly_workshop.quality import topology

        g = GlbBuilder()
        for name, lo, srgb in (("Head", (0, 1, 0), (200, 40, 40)), ("Body", (0, 0, 0), (40, 60, 200)),
                               ("Sword", (2, 0, 0), (90, 90, 90))):
            pos, tri = box(lo, [v + 1 for v in lo])
            col = np.tile([[linear(c) for c in srgb]], (8, 1))
            g.node(name, mesh=g.mesh([dict(pos=pos, tri=tri, color=(col, "<f4"))]))
        self.import_prop(g.write(self.src / "hero.glb"), height=2.0, separate_nodes=True)
        (self.asset / "gen.py").write_text(
            """from pathlib import Path
from lowpoly_workshop.base_mesh import load_glb_node, palette_cells, propose_palette
from lowpoly_workshop.kit.atlas import Atlas

BASE = Path(__file__).resolve().parent / "inputs/base/prop_lowpoly.glb"
ATLAS = Atlas(palette_cells(propose_palette(BASE, cells=3)))

def params(variant=None, overrides=None):
    return dict(overrides or {})

def build(p):
    nodes = load_glb_node(BASE, atlas=ATLAS, separate_nodes=True)
    del nodes["Sword"]
    return nodes
""", encoding="utf-8")
        spec = json.loads((self.asset / "asset.json").read_text())
        spec["relations"] = []
        (self.asset / "asset.json").write_text(json.dumps(spec))
        nodes = Asset(self.asset).build()
        self.assertEqual(list(nodes), ["Head", "Body"])
        self.assertEqual(len({c for nd in nodes.values() for _, c, _, _ in nd["faces"]}), 2)
        for name in nodes:
            stats = topology(triangles({name: nodes[name]})[0])
            self.assertEqual((stats["boundary_edges"], stats["nonmanifold_edges"]), (0, 0))


class BackCompatTests(Fixture):
    def test_loader_is_still_importable_from_pixal3d(self):
        from lowpoly_workshop.pixal3d import _extract_glb_triangles_and_uvs, load_glb_node
        self.assertIs(load_glb_node, base_mesh.load_glb_node)
        pos, tri = box((0, 0, 0), (1, 1, 1))
        path = single_mesh(self.src / "s.glb", pos, tri, uv=np.zeros((8, 2)))
        tris, uvs, tex = _extract_glb_triangles_and_uvs(path)
        self.assertEqual((tris.shape, uvs.shape, tex), ((12, 3, 3), (12, 3, 2), None))

    def test_textured_palette_sampling_is_unchanged(self):
        # per-triangle: the texel under the centroid UV, nearest flat cell in squared RGB distance
        img = Image.new("RGB", (4, 4), (0, 0, 0))
        img.putpixel((3, 0), (190, 190, 190))
        g = GlbBuilder()
        mat = g.material([1, 1, 1, 1], image=img)
        pos = [[0, 0, 0], [1, 0, 0], [0, 1, 0]]
        g.node("T", mesh=g.mesh([dict(pos=pos, tri=[[0, 1, 2]], uv=[[1.0, 0.0]] * 3, material=mat)]))
        nodes = base_mesh.load_glb_node(g.write(self.src / "t.glb"), atlas=GREY)
        self.assertEqual(cells_of(nodes), ["light"])


class BakeTests(Fixture):
    def dense_source(self, front_matrix):
        """A micro-triangle copy of the project's crate with COLOR_0 (linear): red front, blue elsewhere."""
        from lowpoly_workshop import pixal3d_bake
        from lowpoly_workshop.kit.asset import Asset

        polys = pixal3d_bake.lod_polygons(Asset(self.asset).build())
        tris = np.array([q[[0, k, k + 1]] for q, _ in polys for k in range(1, len(q) - 1)])
        n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
        n /= np.linalg.norm(n, axis=1, keepdims=True)
        pts = pixal3d_bake.surface_samples(polys, n=40000)
        owner = np.argmin(np.abs(np.einsum("tj,sj->st", n, pts) - (n * tris[:, 0]).sum(1)), axis=1)
        nn = n[owner]
        u = np.cross(nn, [0.3, 0.5, 0.7])
        u /= np.linalg.norm(u, axis=1, keepdims=True)
        w = np.cross(nn, u)
        micro = np.stack([pts, pts + 0.002 * u, pts + 0.002 * w], axis=1) @ front_matrix.T
        red, blue = [linear(220), linear(30), linear(30)], [linear(30), linear(40), linear(200)]
        col = np.repeat(np.where((nn[:, 2] > 0.9)[:, None], red, blue), 3, axis=0)
        flat = micro.reshape(-1, 3)
        return single_mesh(self.src / "dense.glb", flat, np.arange(len(flat)).reshape(-1, 3),
                           color=(col, "<f4"))

    def baked_front_is_red(self, record_path):
        from lowpoly_workshop.kit.glb import Glb
        record = json.loads(Path(record_path).read_text())
        g = Glb(self.asset / record["outputs"][0]["glb"])
        tex = np.asarray(g.images()[0].convert("RGB"), float)
        prim = g.js["meshes"][0]["primitives"][0]
        P = g.acc(prim["attributes"]["POSITION"]).reshape(-1, 3, 3)
        UV = g.acc(prim["attributes"]["TEXCOORD_0"]).reshape(-1, 3, 2)
        seen = 0
        for tri, uv in zip(P, UV):
            normal = np.cross(tri[1] - tri[0], tri[2] - tri[0])
            c = uv.mean(0) * tex.shape[1::-1]
            r, gr, b = tex[int(c[1]), int(c[0])]
            if normal[2] / np.linalg.norm(normal) > 0.9:
                self.assertGreater(r, b)
                self.assertAlmostEqual(r, 220, delta=6)  # linear 0.716 read back as sRGB, not raw 183
                seen += 1
            else:
                self.assertGreater(b, r)
        self.assertGreater(seen, 0)
        return record

    def test_bake_from_the_original_base_uses_its_front_and_vertex_colours(self):
        facing_x = base_mesh.front_matrix("+x").T  # the file's model faces +X; Workshop wants +Z
        source = self.dense_source(facing_x)
        self.import_prop(source, front="+x", licence="CC0-1.0")
        out, _ = quiet([str(self.asset), "base", "bake", "--name", "prop", "--source",
                        str(self.asset / "inputs/base/prop_source.glb"), "--size", "256"])
        record = self.baked_front_is_red(self.asset / "out/base_bake/bake.json")
        self.assertGreater(record["fit"]["silhouette_iou"], 0.85)
        self.assertEqual(record["source"], "inputs/base/prop_source.glb")  # relative, never absolute
        self.assertTrue((self.asset / record["preview"]).is_file())
        self.assertIn("BASE baked", out)

    def test_bake_defaults_to_the_normalised_mesh_and_accepts_an_outside_source_with_front(self):
        source = self.dense_source(base_mesh.front_matrix("-z").T)
        self.import_prop(source, front="-z")
        quiet([str(self.asset), "base", "bake", "--name", "prop", "--size", "256"])
        self.baked_front_is_red(self.asset / "out/base_bake/bake.json")
        quiet([str(self.asset), "base", "bake", "--name", "prop", "--source", str(source), "--front=-z", "--size", "256"])
        record = self.baked_front_is_red(self.asset / "out/base_bake/bake.json")
        self.assertEqual(record["source"], "dense.glb")  # outside the project: file name only

    def test_bake_without_an_import_or_source_says_what_to_do(self):
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()) as err:
            main([str(self.asset), "base", "bake"])
        self.assertIn("base import", err.getvalue())


if __name__ == "__main__":
    unittest.main()
