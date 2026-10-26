import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch
import numpy as np
from lowpoly_workshop.kit.coverage import observation, suggestion_gain, framed, plan
from lowpoly_workshop.kit.camfit import make_cam


def panel(z):
    return np.array([[[-1., -1., z], [1., -1., z], [1., 1., z]],
                     [[-1., -1., z], [1., 1., z], [-1., 1., z]]])


class CoverageTests(unittest.TestCase):
    def test_occluded_surface_gets_no_credit(self):
        tris = np.concatenate([panel(0), panel(1)])
        v, target = framed(tris, 0, 0, 64)
        q = observation(tris, make_cam(v, target), 64)
        self.assertTrue(np.all(q[:2] == 0))
        self.assertTrue(np.all(q[2:] > 0))

    def test_backfaces_are_not_trusted_as_paint_sources(self):
        tris = panel(0)[:, ::-1]
        v, target = framed(tris, 0, 0, 64)
        np.testing.assert_array_equal(observation(tris, make_cam(v, target), 64), [0, 0])

    def test_coincident_back_card_does_not_hide_front_card(self):
        tris = np.concatenate([panel(0)[:, ::-1], panel(0)])
        v, target = framed(tris, 0, 0, 64)
        q = observation(tris, make_cam(v, target), 64)
        self.assertTrue(np.all(q[:2] == 0))
        self.assertTrue(np.all(q[2:] > 0))

    def test_edge_on_observation_is_worse(self):
        tris = panel(0)
        front, target = framed(tris, 0, 0, 64)
        angle, _ = framed(tris, 70, 0, 64)
        self.assertGreater(observation(tris, make_cam(front, target), 64).sum(),
                           observation(tris, make_cam(angle, target), 64).sum())

    def test_orthographic_distance_does_not_change_confidence(self):
        from lowpoly_workshop.kit.raster import Camera
        tris = panel(0)
        near = Camera(0, 0, 0, 10, 200, 32, 32, target=[0, 0, 0], ortho=True)
        far = Camera(0, 0, 0, 100, 2000, 32, 32, target=[0, 0, 0], ortho=True)
        np.testing.assert_allclose(observation(tris, near, 64), observation(tris, far, 64))

    def test_coplanar_triangle_edges_are_not_silhouettes(self):
        coarse = panel(0)
        fine = []
        for a, b, c in coarse:
            ab, bc, ca = (a+b)/2, (b+c)/2, (c+a)/2
            fine.extend([[a, ab, ca], [ab, b, bc], [ca, bc, c], [ab, bc, ca]])
        fine = np.array(fine)
        v, target = framed(coarse, 0, 0, 128)
        camera = make_cam(v, target)
        q0 = observation(coarse, camera, 128)
        q1 = observation(fine, camera, 128)
        self.assertLess(abs(q0.mean()-q1.mean())/q0.mean(), .03)

    def test_gain_uses_area_not_triangle_count(self):
        areas = np.array([10., .01, .01, .01])
        known = np.zeros(4)
        self.assertGreater(suggestion_gain(areas, known, np.array([1., 0, 0, 0])),
                           suggestion_gain(areas, known, np.array([0., 1, 1, 1])))

    def test_accepted_observations_need_substantial_improvement(self):
        areas = np.array([1.])
        self.assertEqual(suggestion_gain(areas, np.array([1.]), np.array([2.])), 0)
        self.assertGreater(suggestion_gain(areas, np.array([1.]), np.array([3.])), 0)

    def test_suggestions_do_not_rewrite_observed_evidence(self):
        tris = panel(0)
        observed = np.zeros(2)
        selected, hypothetical = plan(tris, observed, 32, 1, excluded=[(0, 0)])
        self.assertEqual(len(selected), 1)
        self.assertNotEqual(selected[0]['cam'][:2], [0, 0])
        np.testing.assert_array_equal(observed, [0, 0])
        self.assertTrue(np.any(hypothetical > 0))


    def test_review_is_held_out_and_inputs_are_not_modified(self):
        from lowpoly_workshop.kit.coverage import run
        from lowpoly_workshop.kit.mesh import Mesh, hexa, X, Y, Z
        mesh = Mesh()
        hexa(mesh, np.zeros(3), [X, Y, Z], np.ones(3), 'paint')
        nodes = {'body': {'faces': mesh.faces, 'pivot': np.zeros(3),
                          'parent': None, 'rot': np.eye(3)}}
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            camera = root/'cam.json'
            camera.write_text(json.dumps({'cam': [0, 0, 0, 40, 12, 16, 16]}))
            original = camera.read_bytes()

            class Fixture:
                def sets(self): return {'turnaround': {}}
                def views(self, st): return ['front']
                def cam(self, st, view): return json.loads(camera.read_text())
                def scene(self, *args): return nodes, {}
                def crop_box(self, *args): return [0, 0, 32, 32]
                def target(self): return [0, 0, 0]
                def palette(self, nodes): return {'paint': [100, 100, 100]}
                def out(self, *parts):
                    path = root/'out'/Path(*parts)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    return str(path)

            with patch('lowpoly_workshop.kit.coverage.Asset', return_value=Fixture()):
                report = run(folder, size=32, budget=0)['turnaround']
            self.assertFalse(report['review']['used_for_fit_or_paint'])
            self.assertNotEqual(report['review']['cam'][:2], [0, 0])
            self.assertLess(report['observed_area_fraction'], .25)
            self.assertEqual(report['hypothetical_observed_area_fraction'], report['observed_area_fraction'])
            self.assertEqual(camera.read_bytes(), original)
            self.assertTrue((root/'out/coverage/turnaround/review-palette.png').is_file())


if __name__ == '__main__':
    unittest.main()
