import base64
import contextlib
import io
import json
import os
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image, ImageDraw

from lowpoly_workshop import rodin
from lowpoly_workshop.cli import main
from lowpoly_workshop.spec import read_spec
from lowpoly_workshop.templates import create
from test_pixal3d import _make_minimal_glb


class FakeFal:
    """Scripted stand-in for urllib.request.urlopen; records every request."""

    def __init__(self, glb_bytes, statuses=("IN_QUEUE", "IN_PROGRESS", "COMPLETED"), status_url=None,
                 result_error=False):
        self.glb = glb_bytes
        self.statuses = list(statuses)
        self.status_url = status_url or "https://queue.fal.run/fal-ai/hyper3d/requests/req-1/status"
        self.result_error = result_error
        self.uploaded = {}
        self.calls = []

    def __call__(self, req, timeout=None):
        url, method = req.full_url, req.get_method()
        if method == "PUT":
            self.calls.append({"url": url, "method": method, "body": None, "auth": req.get_header("Authorization")})
            self.uploaded[url] = req.data
            return io.BytesIO(b"")
        body = json.loads(req.data) if req.data else None
        self.calls.append({"url": url, "method": method, "body": body, "auth": req.get_header("Authorization")})
        if method == "POST" and url.startswith(rodin.UPLOAD_URL):
            n = len(self.uploaded) + len([c for c in self.calls if c["url"] == rodin.UPLOAD_URL]) - 1
            return self._json({"upload_url": f"https://upload.example/signed/{n}?sig=x",
                               "file_url": f"https://v3b.fal.media/files/b/in/{n}-{body['file_name']}"})
        if method == "POST":
            return self._json({"request_id": "req-1", "status_url": self.status_url,
                               "response_url": "https://queue.fal.run/fal-ai/hyper3d/requests/req-1",
                               "cancel_url": "https://queue.fal.run/fal-ai/hyper3d/requests/req-1/cancel"})
        if url.endswith("/status"):
            return self._json({"status": self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]})
        if url.startswith("https://queue.fal.run/"):
            if self.result_error:
                raise urllib.error.HTTPError(url, 422, "Unprocessable", {}, io.BytesIO(b'{"detail": "bad image"}'))
            return self._json({"model_mesh": {"url": "https://v3.fal.media/files/x/model.glb",
                                              "content_type": "model/gltf-binary", "file_name": "model.glb"},
                               "seed": 1234, "textures": []})
        if url == "https://v3.fal.media/files/x/model.glb":
            return io.BytesIO(self.glb)
        raise AssertionError("unexpected request " + url)

    @staticmethod
    def _json(obj):
        return io.BytesIO(json.dumps(obj).encode("utf-8"))

    def posts(self):
        """Paid submissions only (uploads excluded)."""
        return [c for c in self.calls if c["method"] == "POST" and c["url"].startswith(rodin.QUEUE_URL)]


class RodinTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.asset = create(Path(self.tmp.name) / "crate", "static-prop")
        im = Image.new("RGB", (128, 128), (240, 240, 240))
        ImageDraw.Draw(im).rectangle([32, 24, 96, 104], fill=(96, 151, 118))
        for view in ("front", "right", "back", "left"):
            im.save(self.asset / "ref" / f"{view}.png")
        spec = read_spec(self.asset)
        spec["references"] = [{"path": f"ref/{v}.png", "source": "original", "view": v}
                              for v in ("front", "right", "back", "left")]
        (self.asset / "asset.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")
        glb = Path(self.tmp.name) / "generated.glb"
        _make_minimal_glb(glb, [[0, 0, 0], [1, 0, 0], [0, 1, 0]], [[0, 1, 2]])
        self.glb_bytes = glb.read_bytes()
        env = patch.dict(os.environ, {"FAL_KEY": "test-key"})
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("LOWPOLY_RODIN_ENDPOINT", None)

    def _run(self, fake, **kw):
        kw.setdefault("sleep", lambda s: None)
        kw.setdefault("log", lambda *a, **k: None)
        return rodin.run_rodin(self.asset, request=fake, **kw)

    def test_dry_run_records_hashes_not_images_and_needs_no_key(self):
        with patch.dict(os.environ, {}, clear=True):
            out = rodin.run_rodin(self.asset, dry_run=True, seed=7)
        self.assertEqual(out["endpoint"], "https://queue.fal.run/fal-ai/hyper3d/rodin")
        images = out["payload"]["input_image_urls"]
        self.assertEqual(len(images), 1)
        sv = self.asset / "inputs" / "pixal3d" / "sv_input.png"
        self.assertEqual(images[0], "sha256:" + rodin.file_sha256(sv))
        self.assertEqual(out["payload"]["seed"], 7)
        self.assertEqual(out["payload"]["geometry_file_format"], "glb")
        self.assertNotIn("condition_mode", out["payload"])
        self.assertNotIn("quality", out["payload"])

    def test_multi_view_and_endpoint_specific_image_field(self):
        out = rodin.run_rodin(self.asset, mode="mv", dry_run=True)
        self.assertEqual(len(out["payload"]["input_image_urls"]), 4)
        self.assertEqual(out["payload"]["condition_mode"], "concat")
        out = rodin.run_rodin(self.asset, mode="mv", endpoint="fal-ai/hyper3d/rodin/v2.5", dry_run=True,
                              params=rodin.parse_params(["tier=Gen-2.5-High", "use_original_alpha=true"]))
        self.assertEqual(len(out["payload"]["image_urls"]), 4)
        self.assertNotIn("condition_mode", out["payload"], "v2.5 has no condition_mode input")
        self.assertEqual(out["payload"]["tier"], "Gen-2.5-High")
        self.assertIs(out["payload"]["use_original_alpha"], True)
        with self.assertRaises(ValueError):
            rodin.run_rodin(self.asset, endpoint="someone/other-model", dry_run=True)
        out = rodin.run_rodin(self.asset, endpoint="someone/other-model", field="images", dry_run=True)
        self.assertIn("images", out["payload"])
        with self.assertRaises(ValueError):
            rodin.parse_params(["novalue"])
        with self.assertRaises(ValueError):
            rodin.endpoint_name("fal-ai/../x")

    def test_run_submits_polls_downloads_and_caches(self):
        fake = FakeFal(self.glb_bytes)
        meta_path, generated = self._run(fake, seed=7, quality="medium", material="PBR")
        self.assertTrue(generated)
        post = fake.posts()[0]
        self.assertEqual(post["url"], "https://queue.fal.run/fal-ai/hyper3d/rodin")
        self.assertEqual(post["auth"], "Key test-key")
        sv = self.asset / "inputs" / "pixal3d" / "sv_input.png"
        self.assertEqual(post["body"]["input_image_urls"], ["https://v3b.fal.media/files/b/in/0-sv_input.png"])
        init = [c for c in fake.calls if c["url"] == rodin.UPLOAD_URL]
        self.assertEqual(init[0]["auth"], "Key test-key")
        self.assertEqual(init[0]["body"], {"file_name": "sv_input.png", "content_type": "image/png"})
        put = [c for c in fake.calls if c["method"] == "PUT"]
        self.assertIsNone(put[0]["auth"], "the key must not go to the signed upload URL")
        self.assertEqual(list(fake.uploaded.values()), [sv.read_bytes()])
        self.assertEqual((post["body"]["seed"], post["body"]["quality"], post["body"]["material"]), (7, "medium", "PBR"))
        download = [c for c in fake.calls if "fal.media" in c["url"]]
        self.assertEqual(len(download), 1)
        self.assertIsNone(download[0]["auth"], "the key must not go to the media CDN")
        raw = self.asset / rodin.RAW_GLB
        self.assertEqual(raw.read_bytes(), self.glb_bytes)
        meta = json.loads(Path(meta_path).read_text())
        self.assertEqual(meta["request_id"], "req-1")
        self.assertEqual(meta["result"]["seed"], 1234)
        self.assertEqual(meta["raw_glb_sha256"], rodin.file_sha256(raw))
        self.assertEqual(meta["payload"]["input_image_urls"], ["sha256:" + rodin.file_sha256(sv)])
        self.assertEqual(meta["image_transport"], "fal-cdn")
        self.assertNotIn("test-key", Path(meta_path).read_text())
        self.assertFalse((self.asset / rodin.PENDING).exists())

        again = FakeFal(self.glb_bytes)
        _, generated = self._run(again, seed=7, quality="medium", material="PBR")
        self.assertFalse(generated)
        self.assertEqual(again.calls, [], "a cached result makes no request")
        changed = FakeFal(self.glb_bytes)
        self._run(changed, seed=8, quality="medium", material="PBR")
        self.assertEqual(len(changed.posts()), 1, "other parameters are a new generation")

    def test_inline_sends_data_uris_and_shares_the_cache_key(self):
        fake = FakeFal(self.glb_bytes)
        self._run(fake, inline=True, seed=5)
        uri = fake.posts()[0]["body"]["input_image_urls"][0]
        sv = self.asset / "inputs" / "pixal3d" / "sv_input.png"
        self.assertTrue(uri.startswith("data:image/png;base64,"))
        self.assertEqual(base64.b64decode(uri.split(",", 1)[1]), sv.read_bytes())
        self.assertFalse([c for c in fake.calls if c["url"] == rodin.UPLOAD_URL])
        again = FakeFal(self.glb_bytes)
        self.assertFalse(self._run(again, seed=5)[1], "transport does not change what is generated")

    def test_timeout_keeps_request_and_next_run_resumes_without_paying_again(self):
        clock = iter(range(0, 10_000, 10))
        slow = FakeFal(self.glb_bytes, statuses=("IN_QUEUE",))
        with self.assertRaises(TimeoutError):
            self._run(slow, timeout=25, clock=lambda: next(clock))
        pending = json.loads((self.asset / rodin.PENDING).read_text())
        self.assertEqual(pending["request_id"], "req-1")
        self.assertFalse((self.asset / rodin.RAW_GLB).exists())

        resumed = FakeFal(self.glb_bytes, statuses=("COMPLETED",))
        _, generated = self._run(resumed)
        self.assertTrue(generated)
        self.assertEqual(resumed.posts(), [], "resuming must not submit a second paid job")
        self.assertFalse((self.asset / rodin.PENDING).exists())

    def test_pending_request_with_other_inputs_blocks_until_forced(self):
        slow = FakeFal(self.glb_bytes, statuses=("IN_QUEUE",))
        clock = iter(range(0, 10_000, 10))
        with self.assertRaises(TimeoutError):
            self._run(slow, seed=1, timeout=5, clock=lambda: next(clock))
        with self.assertRaises(ValueError):
            self._run(FakeFal(self.glb_bytes), seed=2)
        forced = FakeFal(self.glb_bytes)
        self._run(forced, seed=2, force=True)
        self.assertEqual(len(forced.posts()), 1)

    def test_failures_and_key_safety(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                self._run(FakeFal(self.glb_bytes))
        evil = FakeFal(self.glb_bytes, status_url="https://example.com/status")
        with self.assertRaises(ValueError):
            self._run(evil)
        self.assertFalse([c for c in evil.calls if "example.com" in c["url"]], "no request, so no key, to other hosts")
        (self.asset / rodin.PENDING).unlink()
        odd = FakeFal(self.glb_bytes, statuses=("FAILED",))
        with self.assertRaises(RuntimeError):
            self._run(odd)
        (self.asset / rodin.PENDING).unlink()
        failed = FakeFal(self.glb_bytes, statuses=("COMPLETED",), result_error=True)
        with self.assertRaisesRegex(RuntimeError, "422"):
            self._run(failed)
        self.assertFalse((self.asset / rodin.PENDING).exists(), "a failed request is not resumed")
        with self.assertRaises(ValueError):
            rodin.run_rodin(self.asset, image_urls=["http://insecure.example/a.png"], dry_run=True)

    def test_cli_dry_run_and_status(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            main([str(self.asset), "rodin", "run", "--dry-run", "--seed", "3", "--param", "TAPose=false"])
        out = json.loads(buf.getvalue())
        self.assertEqual(out["payload"]["seed"], 3)
        self.assertIs(out["payload"]["TAPose"], False)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            main([str(self.asset), "rodin", "status"])
        state = json.loads(buf.getvalue())
        self.assertEqual(state["key"], "set (FAL_KEY)")
        self.assertIsNone(state["generated"])


class GeneratedSourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.asset = create(Path(self.tmp.name) / "crate", "static-prop")

    def test_bake_source_front_keeps_or_turns_the_generated_mesh(self):
        from lowpoly_workshop import pixal3d_bake
        quad = np.array([[0.2, 0.0, 0.5], [0.6, 0.0, 0.5], [0.6, 0.4, 0.5], [0.2, 0.4, 0.5]])
        uvs = [np.array([[0, 0], [1, 0], [1, 1], [0, 1]], float)]
        png = io.BytesIO()
        Image.new("RGB", (8, 8), (200, 10, 10)).save(png, format="PNG")
        path = Path(self.tmp.name) / "facing.glb"
        pixal3d_bake.write_textured_glb(path, [(quad, None)], uvs, png.getvalue(), name="g")
        turned = pixal3d_bake.load_source(path)[0]
        kept = pixal3d_bake.load_source(path, "+z")[0]
        self.assertGreater(kept[:, 2].min(), 0.4)
        self.assertLess(turned[:, 2].max(), -0.4)
        np.testing.assert_allclose(turned[:, 0], -kept[:, 0])
        with self.assertRaises(ValueError):
            pixal3d_bake.load_source(path, "+x")

    def test_base_colour_image_skips_the_normal_map(self):
        from lowpoly_workshop.pixal3d_bake import base_colour_image
        rodin_like = {"materials": [{"normalTexture": {"index": 0},
                                     "pbrMetallicRoughness": {"baseColorTexture": {"index": 1},
                                                              "metallicRoughnessTexture": {"index": 2}}}],
                      "textures": [{"source": 0}, {"source": 1}, {"source": 2}]}
        self.assertEqual(base_colour_image(rodin_like, {"material": 0}), 1)
        remapped = dict(rodin_like, textures=[{"source": 2}, {"source": 0}, {"source": 1}])
        self.assertEqual(base_colour_image(remapped, {"material": 0}), 0)
        self.assertEqual(base_colour_image({}, {}), 0, "no material information keeps the first image")
        self.assertEqual(base_colour_image(rodin_like, {}), 0)

    def test_decimate_script_reads_another_generated_glb(self):
        from lowpoly_workshop import pixal3d
        other = self.asset / "inputs" / "rodin_raw.glb"
        code = pixal3d.blender_mcp_decimate_code(self.asset, budget=500, height=1.0, source=other)
        self.assertIn(json.dumps(str(other.resolve()))[1:-1], code)
        default = pixal3d.blender_mcp_decimate_code(self.asset, budget=500, height=1.0)
        self.assertIn("pixal3d_raw.glb", default)


if __name__ == "__main__":
    unittest.main()
