import contextlib
import io
import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from PIL import Image, ImageDraw

from lowpoly_workshop import pixal3d
from lowpoly_workshop.cli import main
from lowpoly_workshop.kit.atlas import Atlas
from lowpoly_workshop.kit.mesh import triangles
from lowpoly_workshop.quality import topology, uv_diagnostics
from lowpoly_workshop.spec import read_spec, validate_nodes
from lowpoly_workshop.templates import create


def _make_minimal_glb(path, verts, tris, uvs=None):
    """Write a minimal valid glTF 2.0 binary (.glb) with one mesh node for unit tests."""
    v_arr = np.asarray(verts, dtype=np.float32).reshape(-1, 3)
    i_arr = np.asarray(tris, dtype=np.uint16).reshape(-1, 3)
    u_arr = (
        np.asarray(uvs, dtype=np.float32).reshape(-1, 2)
        if uvs is not None
        else np.zeros((len(v_arr), 2), dtype=np.float32)
    )
    v_bytes = v_arr.tobytes()
    u_bytes = u_arr.tobytes()
    i_bytes = i_arr.tobytes()
    while len(i_bytes) % 4:
        i_bytes += b"\x00"
    bin_chunk = v_bytes + u_bytes + i_bytes
    while len(bin_chunk) % 4:
        bin_chunk += b"\x00"

    gltf = {
        "asset": {"version": "2.0"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"name": "PixalMesh", "mesh": 0}],
        "meshes": [
            {
                "name": "PixalMesh",
                "primitives": [
                    {
                        "attributes": {"POSITION": 0, "TEXCOORD_0": 1},
                        "indices": 2,
                    }
                ],
            }
        ],
        "buffers": [{"byteLength": len(bin_chunk)}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": len(v_bytes)},
            {"buffer": 0, "byteOffset": len(v_bytes), "byteLength": len(u_bytes)},
            {"buffer": 0, "byteOffset": len(v_bytes) + len(u_bytes), "byteLength": len(i_arr.tobytes())},
        ],
        "accessors": [
            {
                "bufferView": 0,
                "componentType": 5126,
                "count": len(v_arr),
                "type": "VEC3",
                "min": v_arr.min(axis=0).tolist(),
                "max": v_arr.max(axis=0).tolist(),
            },
            {
                "bufferView": 1,
                "componentType": 5126,
                "count": len(u_arr),
                "type": "VEC2",
            },
            {
                "bufferView": 2,
                "componentType": 5123,
                "count": int(i_arr.size),
                "type": "SCALAR",
            },
        ],
    }
    js_bytes = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    while len(js_bytes) % 4:
        js_bytes += b" "
    total_len = 12 + 8 + len(js_bytes) + 8 + len(bin_chunk)
    header = struct.pack("<III", 0x46546C67, 2, total_len)
    c0 = struct.pack("<II", len(js_bytes), 0x4E4F534A) + js_bytes
    c1 = struct.pack("<II", len(bin_chunk), 0x004E4942) + bin_chunk
    Path(path).write_bytes(header + c0 + c1)


class Pixal3DTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.asset = create(self.root / "crate", "static-prop")
        # Create a synthetic reference image with a distinct foreground box on a light background
        im = Image.new("RGB", (128, 128), (240, 240, 240))
        draw = ImageDraw.Draw(im)
        draw.rectangle([32, 24, 96, 104], fill=(96, 151, 118))
        for view in ("front", "right", "back", "left"):
            im.save(self.asset / "ref" / f"{view}.png")
        spec = read_spec(self.asset)
        spec["references"] = [
            {"path": f"ref/{view}.png", "source": "original", "view": view}
            for view in ("front", "right", "back", "left")
        ]
        (self.asset / "asset.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")

    def _populate_models(self, directory, family="sv"):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        files = []
        for name in pixal3d.required_model_files(family):
            p = directory / name
            p.write_bytes(b"GGUF-mock-" + name.encode("utf-8"))
            files.append({"name": name, "size_bytes": p.stat().st_size})
        manifest = {
            "schema_version": 1,
            "model_set": f"pixal3d-{family}-q8_0",
            "version": "v1",
            "model_family": family,
            "files": files,
        }
        (directory / "pixal3d-models.json").write_text(json.dumps(manifest), encoding="utf-8")
        return directory

    def test_verify_models_dir_checks_required_files_and_family(self):
        sv_dir = self._populate_models(self.root / "models-sv", "sv")
        self.assertEqual(Path(pixal3d.verify_models_dir(sv_dir, "sv")), sv_dir.resolve())
        with self.assertRaises(ValueError):
            pixal3d.verify_models_dir(sv_dir, "mv")
        (sv_dir / "dinov3.gguf").unlink()
        with self.assertRaises(FileNotFoundError):
            pixal3d.verify_models_dir(sv_dir, "sv")

    def test_prepare_inputs_sv_and_mv(self):
        sv_meta = pixal3d.prepare_inputs(self.asset, mode="sv", view="front", size=256)
        sv_png = self.asset / sv_meta["input_file"]
        self.assertTrue(sv_png.is_file())
        with Image.open(sv_png) as out_im:
            self.assertEqual(out_im.mode, "RGBA")
            self.assertEqual(out_im.size, (256, 256))
            arr = np.asarray(out_im)
            self.assertEqual(int(arr[0, 0, 3]), 0)
            self.assertGreater(int(arr[128, 128, 3]), 200)

        mv_meta = pixal3d.prepare_inputs(self.asset, mode="mv", size=256)
        transforms_path = self.asset / mv_meta["transforms"]
        self.assertTrue(transforms_path.is_file())
        transforms = json.loads(transforms_path.read_text(encoding="utf-8"))
        self.assertEqual(len(transforms["frames"]), 4)
        self.assertEqual(
            [f["file_path"] for f in transforms["frames"]],
            ["view00_front.png", "view01_right.png", "view02_back.png", "view03_left.png"],
        )

    def test_prepare_inputs_sv_crops_front_from_turnaround_set(self):
        """A turnaround reference must not be used whole as the front view.

        `prepare_inputs(view="front")` used to fall back to the first reference before looking at
        sheet sets, so a six-view turnaround sheet was cut out as one single-view input.
        """
        sheet = Image.new("RGB", (192, 64), (240, 240, 240))
        draw = ImageDraw.Draw(sheet)
        draw.rectangle([16, 8, 48, 56], fill=(96, 151, 118))
        draw.rectangle([80, 8, 176, 56], fill=(151, 96, 118))
        sheet.save(self.asset / "ref" / "sheet.png")
        spec = read_spec(self.asset)
        spec["references"] = [{"path": "ref/sheet.png", "source": "original", "view": "turnaround"}]
        (self.asset / "asset.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")
        with self.assertRaises(ValueError):
            pixal3d.prepare_inputs(self.asset, mode="sv", view="front", size=64)

        spec["sets"] = {"sheet": {"image": "ref/sheet.png", "views": {"front": {"box": [0, 0, 64, 64]}}}}
        (self.asset / "asset.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")
        meta = pixal3d.prepare_inputs(self.asset, mode="sv", view="front", size=64)
        self.assertEqual(meta["box"], [0, 0, 64, 64])

    def test_build_cli_command_keeps_quadric_simplify_by_default(self):
        """`--decim` is trellis-cli's legacy cluster-grid size, not a face budget.

        Passing `--decim 50000` by default disabled the Pixal3D quadric simplify to 1M faces and left a
        res-1024 run at ~25M triangles, which also made xatlas charting time out.
        """
        cmd = pixal3d.build_cli_command(self.asset, models_dir=self.root, binary="trellis-cli", threads=1)
        self.assertNotIn("--decim", cmd)
        cmd = pixal3d.build_cli_command(self.asset, models_dir=self.root, binary="trellis-cli", threads=1, decim=64)
        self.assertEqual(cmd[cmd.index("--decim") + 1], "64")
        self.assertTrue(cmd[-1].endswith("pixal3d_raw.glb"))

    def test_run_pixal3d_executes_trellis_cli_and_caches_by_hash(self):
        fake_bin = self.root / "trellis-cli.exe"
        fake_bin.write_bytes(b"fake-trellis-cli")
        sv_dir = self._populate_models(self.root / "models-sv", "sv")
        calls = []

        def fake_runner(cmd, capture_output=True, text=True):
            calls.append(cmd)
            out_glb = Path(cmd[-1])
            verts = [
                [-0.2, 0.0, -0.2],
                [0.2, 0.0, -0.2],
                [0.2, 0.0, 0.2],
                [-0.2, 0.0, 0.2],
                [0.0, 0.5, 0.0],
            ]
            tris = [[0, 2, 1], [0, 3, 2], [0, 1, 4], [1, 2, 4], [2, 3, 4], [3, 0, 4]]
            _make_minimal_glb(out_glb, verts, tris)

            class Proc:
                returncode = 0
                stdout = "ok"
                stderr = ""

            return Proc()

        env = {
            "LOWPOLY_PIXAL3D_BIN": str(fake_bin),
            "LOWPOLY_PIXAL3D_MODELS_SV": str(sv_dir),
            "LOWPOLY_PIXAL3D_THREADS": "6",
        }
        with patch.dict("os.environ", env):
            meta_path, ran = pixal3d.run_pixal3d(self.asset, mode="sv", runner=fake_runner)
            self.assertTrue(ran)
            self.assertTrue(meta_path.is_file())
            self.assertEqual(len(calls), 1)
            self.assertIn("--sv-image", calls[0])
            self.assertIn("--webp", calls[0])
            self.assertIn("off", calls[0])
            # Second run with identical inputs hits cache
            _, ran_again = pixal3d.run_pixal3d(self.asset, mode="sv", runner=fake_runner)
            self.assertFalse(ran_again)
            self.assertEqual(len(calls), 1)

    def test_load_glb_node_palette_and_decal_modes_pass_workshop_contracts(self):
        glb_path = self.asset / "inputs" / "pixal3d_lowpoly.glb"
        glb_path.parent.mkdir(parents=True, exist_ok=True)
        # Closed tetrahedron
        verts = [
            [-0.2, 0.0, -0.2],
            [0.2, 0.0, -0.2],
            [0.0, 0.0, 0.25],
            [0.0, 0.4, 0.0],
        ]
        tris = [[0, 1, 2], [0, 3, 1], [1, 3, 2], [2, 3, 0]]
        uvs = [[0.1, 0.1], [0.9, 0.1], [0.5, 0.9], [0.5, 0.5]]
        _make_minimal_glb(glb_path, verts, tris, uvs=uvs)

        palette_atlas = Atlas({"wood": ("#8f6239", "R"), "iron": ("#4a525d", None)})
        nodes_pal = pixal3d.load_glb_node(glb_path, node_name="Crate", atlas=palette_atlas, mode="palette")
        validated_pal = validate_nodes(nodes_pal, palette_atlas)
        t_stats = topology(triangles(validated_pal)[0])
        self.assertEqual(t_stats["boundary_edges"], 0)
        self.assertEqual(uv_diagnostics(validated_pal, palette_atlas), [])

        tex_png = self.asset / "inputs" / "pixal3d_atlas.png"
        Image.new("RGB", (64, 64), (120, 90, 60)).save(tex_png)
        decal_atlas = pixal3d.make_decal_atlas(tex_png, cell="surface", size=512)
        nodes_dec = pixal3d.load_glb_node(glb_path, node_name="Crate", atlas=decal_atlas, cell="surface", mode="decal")
        validated_dec = validate_nodes(nodes_dec, decal_atlas)
        self.assertEqual(uv_diagnostics(validated_dec, decal_atlas), [])

    def test_cli_pixal3d_prep_and_mcp_script(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            main([str(self.asset), "pixal3d", "prep", "--mode", "sv", "--size", "128"])
        prep = json.loads(out.getvalue())
        self.assertEqual(prep["mode"], "sv")

        script_out = io.StringIO()
        with contextlib.redirect_stdout(script_out):
            main([str(self.asset), "pixal3d", "mcp-script", "--budget", "400", "--height", "0.5", "--node", "Crate"])
        code = script_out.getvalue()
        self.assertIn("LowpolyBudget", code)
        self.assertIn('"budget": 400', code)
        self.assertIn('"node_name": "Crate"', code)

    def test_blender_decimate_and_workshop_build_check_roundtrip(self):
        from lowpoly_workshop.kit.mesh import Mesh
        from lowpoly_workshop.kit.organic import closed_limb
        from lowpoly_workshop.pipeline import find_blender
        from lowpoly_workshop.runner import build
        from lowpoly_workshop.kit.check import run as check_run

        code = pixal3d.blender_mcp_decimate_code(
            self.asset, budget=120, height=0.5, node_name="Crate", ground=True
        )
        compile(code, "decimate_pixal3d", "exec")
        try:
            find_blender()
        except FileNotFoundError:
            self.skipTest("Blender executable not installed in this environment")

        # Build a dense closed organic mesh (~500+ triangles) as inputs/pixal3d_raw.glb
        m = Mesh()
        pts = [[0.0, y, 0.0] for y in np.linspace(0.0, 1.0, 12)]
        radii = [0.25 + 0.08 * np.sin(i * 0.5) for i in range(12)]
        closed_limb(m, pts, radii, n=24, cells="body")
        verts = []
        tris = []
        vmap = {}
        for pts, *_ in m.faces:
            ids = []
            for p in pts:
                k = tuple(np.round(p, 6))
                if k not in vmap:
                    vmap[k] = len(verts)
                    verts.append(k)
                ids.append(vmap[k])
            for c in range(1, len(ids) - 1):
                tris.append([ids[0], ids[c], ids[c + 1]])
        raw_glb = self.asset / "inputs" / "pixal3d_raw.glb"
        raw_glb.parent.mkdir(parents=True, exist_ok=True)
        _make_minimal_glb(raw_glb, verts, tris)

        # Decimate in Blender down to <= 120 triangles, height 0.5m, grounded at y=0
        low_glb = pixal3d.decimate_with_blender(
            self.asset, budget=120, height=0.5, node_name="Crate", ground=True
        )
        self.assertTrue(low_glb.is_file())
        report = json.loads((self.asset / "inputs" / "pixal3d_lowpoly.json").read_text(encoding="utf-8"))
        self.assertGreater(report["raw_triangles"], 200)
        self.assertLessEqual(report["lowpoly_triangles"], 120)
        self.assertAlmostEqual(report["height_m"], 0.5, places=3)

        # Wire gen.py to load inputs/pixal3d_lowpoly.glb and run Workshop build + check
        (self.asset / "gen.py").write_text(
            """from pathlib import Path
import numpy as np
from lowpoly_workshop.kit.atlas import Atlas
from lowpoly_workshop.pixal3d import load_glb_node

HERE = Path(__file__).resolve().parent
ATLAS = Atlas({"wood": ("#8f6239", "R"), "iron": ("#4a525d", "G")})

def params(variant=None, overrides=None):
    return dict(overrides or {})

def build(p):
    nodes = load_glb_node(HERE / "inputs/pixal3d_lowpoly.glb", node_name="Crate", atlas=ATLAS, mode="palette")
    nodes["Top"] = {"parent": "Crate", "pivot": np.array([0.0, 0.5, 0.0]), "faces": []}
    return nodes
""",
            encoding="utf-8",
        )
        spec = read_spec(self.asset)
        spec["relations"] = []
        (self.asset / "asset.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")

        build(self.asset, force=True)
        self.assertTrue(check_run(self.asset))



def _write_trellis_ply(path, tris, colours):
    """Binary PLY in trellis-cli's frame (Z-up, front -Y) from Workshop-frame triangles."""
    pts = np.asarray(tris, float).reshape(-1, 3)
    pts = np.stack([-pts[:, 0], pts[:, 2], pts[:, 1]], axis=1)
    v = np.zeros(len(pts), dtype=[("p", "<f4", 3), ("c", "u1", 3)])
    v["p"], v["c"] = pts, np.repeat(np.asarray(colours, np.uint8), 3, axis=0)
    f = np.zeros(len(tris), dtype=[("n", "u1"), ("i", "<i4", 3)])
    f["n"], f["i"] = 3, np.arange(len(pts)).reshape(-1, 3)
    header = (
        "ply\nformat binary_little_endian 1.0\nelement vertex %d\n"
        "property float x\nproperty float y\nproperty float z\n"
        "property uchar red\nproperty uchar green\nproperty uchar blue\n"
        "element face %d\nproperty list uchar int vertex_indices\nend_header\n" % (len(v), len(f))
    )
    Path(path).write_bytes(header.encode() + v.tobytes() + f.tobytes())


class Pixal3DBakeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.asset = create(Path(self.tmp.name) / "crate", "static-prop")

    def _generated_crate(self, path, scale=1.1, offset=(0.05, -0.04, 0.03)):
        """A dense, red-fronted, blue-elsewhere copy of the crate, deliberately misregistered."""
        from lowpoly_workshop import pixal3d_bake
        from lowpoly_workshop.kit.asset import Asset

        polys = pixal3d_bake.lod_polygons(Asset(self.asset).build())
        tris = np.array([q[[0, k, k + 1]] for q, _ in polys for k in range(1, len(q) - 1)])
        n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
        n /= np.linalg.norm(n, axis=1, keepdims=True)
        pts = pixal3d_bake.surface_samples(polys, n=40000)
        # every sample becomes a 2 mm triangle in its face's plane, facing the same way
        owner = np.argmin(np.abs(np.einsum("tj,sj->st", n, pts) - (n * tris[:, 0]).sum(1)), axis=1)
        nn = n[owner]
        u = np.cross(nn, [0.3, 0.5, 0.7])
        u /= np.linalg.norm(u, axis=1, keepdims=True)
        w = np.cross(nn, u)
        micro = np.stack([pts, pts + 0.002 * u, pts + 0.002 * w], axis=1)
        centre = pts.mean(0)
        micro = centre + (micro - centre) * scale + np.asarray(offset)
        colours = np.where((nn[:, 2] > 0.9)[:, None], [220, 30, 30], [30, 40, 200])
        _write_trellis_ply(path, micro, colours)

    def test_bake_fits_misregistered_source_and_writes_textured_glb(self):
        from lowpoly_workshop.kit.glb import Glb

        ply = self.asset / "inputs" / "pixal3d_raw.ply"
        ply.parent.mkdir(parents=True, exist_ok=True)
        self._generated_crate(ply)
        with contextlib.redirect_stdout(io.StringIO()):
            main([str(self.asset), "pixal3d", "bake", "--size", "256"])
        record = json.loads((self.asset / "out" / "pixal3d_bake" / "bake.json").read_text())
        self.assertGreater(record["fit"]["silhouette_iou"], 0.85)
        self.assertEqual(record["outputs"][0]["triangles"], 12)
        self.assertTrue((self.asset / record["preview"]).is_file())

        g = Glb(self.asset / record["outputs"][0]["glb"])
        tex = np.asarray(g.images()[0].convert("RGB"), float)
        prim = g.js["meshes"][0]["primitives"][0]
        P = g.acc(prim["attributes"]["POSITION"]).reshape(-1, 3, 3)
        UV = g.acc(prim["attributes"]["TEXCOORD_0"]).reshape(-1, 3, 2)
        self.assertEqual(len(P), 12)
        for tri, uv in zip(P, UV):
            normal = np.cross(tri[1] - tri[0], tri[2] - tri[0])
            c = uv.mean(0) * tex.shape[1::-1]
            r, _, b = tex[int(c[1]), int(c[0])]
            if normal[2] / np.linalg.norm(normal) > 0.9:
                self.assertGreater(r, b, "front face should take the red front")
            else:
                self.assertGreater(b, r, "other faces should take the blue sides")

    def test_bake_samples_charts_thinner_than_a_texel(self):
        """A trim or bevel strip narrower than one texel has no texel centre inside its triangles.

        Sampling only texels inside triangles left 6,856 of the rest house LOD0's charts black."""
        from lowpoly_workshop import pixal3d_bake

        wall = np.array([[0, 0, 0], [4, 0, 0], [4, 3, 0], [0, 3, 0]], float)
        trim = np.array([[0, 3, 0.01], [4, 3, 0.01], [4, 3.02, 0.01], [0, 3.02, 0.01]], float)
        polys = [(wall, "body"), (trim, "trim")]
        uvs, normals, density = pixal3d_bake.pack(polys, 64)
        self.assertLess(0.02 * density, 1.0)
        pts, _, pix = pixal3d_bake._texels(polys, uvs, normals, 64, density)
        for (q, _), uv in zip(polys, uvs):
            col, row = (uv.mean(0) * 64).astype(int)
            hit = np.nonzero((pix[:, 0] == row) & (pix[:, 1] == col))[0]
            self.assertEqual(len(hit), 1)
            self.assertLess(np.linalg.norm(pts[hit[0]] - q.mean(0)), 1.5 / density)

    def test_bake_edge_texels_sample_their_own_polygon(self):
        """A texel straddling a thin frame's edge has its centre beyond the frame, on the wall behind.

        Sampling that centre gave frames wall-coloured edge lines; it must be clamped onto the frame."""
        from lowpoly_workshop import pixal3d_bake

        frame = np.array([[0, 0, 0], [0.09, 0, 0], [0.09, 1, 0], [0, 1, 0]], float)
        uvs, normals, density = pixal3d_bake.pack([(frame, "trim")], 16)
        pts, _, _ = pixal3d_bake._texels([(frame, "trim")], uvs, normals, 16, density)
        self.assertGreater(len(pts), 4)
        self.assertTrue(np.all((pts[:, 0] >= -1e-9) & (pts[:, 0] <= 0.09 + 1e-9)))
        self.assertTrue(np.all((pts[:, 1] >= -1e-9) & (pts[:, 1] <= 1 + 1e-9)))

    def test_facade_warp_recovers_a_shifted_bay_layout(self):
        """Generated window edges sit a few pixels off the authored ones; the warp must pull them together."""
        from lowpoly_workshop import pixal3d_bake

        x = np.arange(200, dtype=float)
        authored = ((x // 25) % 2)[:, None] * np.ones((1, 2))
        generated = np.roll(authored, 6, axis=0)
        shift = pixal3d_bake._dtw_shift(authored, generated, 12)
        warped = generated[np.clip(np.round(x + shift).astype(int), 0, 199)]
        before = np.abs(authored - generated)[30:170].mean()
        after = np.abs(authored - warped)[30:170].mean()
        self.assertLess(after, 0.6 * before)
        self.assertLessEqual(np.abs(shift).max(), 12)

    def test_bake_rejects_unknown_variant_and_missing_source(self):
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()) as err:
            main([str(self.asset), "pixal3d", "bake"])
        self.assertIn("pixal3d run", err.getvalue())
        ply = self.asset / "inputs" / "pixal3d_raw.ply"
        ply.parent.mkdir(parents=True, exist_ok=True)
        self._generated_crate(ply)
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()) as err:
            main([str(self.asset), "pixal3d", "bake", "--variant", "9"])
        self.assertIn("No output with variant '9'", err.getvalue())
