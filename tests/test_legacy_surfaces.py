"""Regression checks for the coplanar-overlap check and the piece shots (no Blender needed)."""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lowpoly_workshop.kit import pieces as P
from lowpoly_workshop.kit import surfaces as S


def quad(y, x0=0.0, x1=1.0, z0=0.0, z1=1.0, up=True):
    """Two triangles of a horizontal quad at height y, facing up (or down)."""
    a, b, c, d = [x0, y, z0], [x1, y, z0], [x1, y, z1], [x0, y, z1]
    t = [[a, d, c], [a, c, b]] if up else [[a, c, d], [a, b, c]]
    return np.array(t, float)


def uv(u):
    return np.full((2, 3, 2), u, float)


def box(lo, hi):
    """A closed box: twelve outward triangles."""
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    v = np.array([[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],
                  [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]], float)
    f = [(0, 3, 2), (0, 2, 1), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4),
         (3, 7, 6), (3, 6, 2), (0, 4, 7), (0, 7, 3), (1, 2, 6), (1, 6, 5)]
    return v[np.array(f)]


class OverlapTests(unittest.TestCase):
    def test_a_patch_half_a_millimetre_over_a_face_fights_unless_it_looks_the_same(self):
        tris = np.concatenate([quad(1.0), quad(1.0005, .2, .6, .2, .6)])
        names = ["body"] * 2 + ["patch"] * 2
        found = S.overlaps(tris, names, np.concatenate([uv(.1), uv(.7)]), eps=S.eps_for(60))
        self.assertEqual(len(found["zfight"]), 1)
        a, b, area, gap, _ = found["zfight"][0]
        self.assertEqual({a, b}, {"body", "patch"})
        self.assertAlmostEqual(area, 0.16, places=6)
        self.assertAlmostEqual(gap, 0.0005, places=6)
        same = S.overlaps(tris, names, np.concatenate([uv(.1), uv(.1)]), eps=S.eps_for(60))
        self.assertEqual((len(same["zfight"]), len(same["hidden"])), (0, 1))

    def test_with_an_atlas_the_texel_decides_not_the_coordinate(self):
        # Two places in one flat palette cell look the same; another cell does not.
        atlas = np.zeros((4, 4, 3), np.uint8)
        atlas[:, :2] = (200, 30, 30)
        atlas[:, 2:] = (30, 30, 200)
        tris = np.concatenate([quad(1.0), quad(1.0, .2, .6, .2, .6)])
        same = S.overlaps(tris, ["arm"] * 2 + ["ring"] * 2, np.concatenate([uv(.1), uv(.4)]), tex=atlas)
        self.assertEqual((len(same["zfight"]), len(same["hidden"])), (0, 1))
        other = S.overlaps(tris, ["arm"] * 2 + ["ring"] * 2, np.concatenate([uv(.1), uv(.9)]), tex=atlas)
        self.assertEqual(len(other["zfight"]), 1)

    def test_a_patch_lifted_past_the_depth_resolution_is_fine(self):
        tris = np.concatenate([quad(1.0), quad(1.002, .2, .6, .2, .6)])
        self.assertEqual(S.overlaps(tris, ["a"] * 4, np.concatenate([uv(.1), uv(.7)]), eps=S.eps_for(60))["zfight"], [])
        # Seen from 100 m the same 2 mm lift is too little.
        self.assertEqual(len(S.overlaps(tris, ["a"] * 4, np.concatenate([uv(.1), uv(.7)]), eps=S.eps_for(100))["zfight"]), 1)

    def test_neighbouring_faces_of_one_plane_and_crossing_faces_do_not_count(self):
        tris = np.concatenate([quad(0.5, 0, 1), quad(0.5, 1, 2)])
        tilted = quad(0.5, 0, 1) @ np.array([[1, 0, 0], [0, .9, -.43], [0, .43, .9]])
        for t in (tris, np.concatenate([quad(0.5), tilted])):
            found = S.overlaps(t, ["a"] * len(t), None, eps=0.001)
            self.assertEqual(sum(len(v) for v in found.values()), 0)

    def test_glued_boxes_are_back_to_back_but_a_two_sided_card_is_meant(self):
        tris = np.concatenate([box([0, 0, 0], [1, 1, 1]), box([0.2, 1, 0.2], [0.8, 1.5, 0.8])])
        found = S.overlaps(tris, ["lower"] * 12 + ["upper"] * 12, None, eps=0.001)
        self.assertEqual(len(found["back_to_back"]), 1)
        self.assertAlmostEqual(found["back_to_back"][0][2], 0.36, places=6)
        card = np.concatenate([quad(1.0), quad(1.0, up=False)])
        self.assertEqual(S.overlaps(card, ["card"] * 4, None)["back_to_back"], [])

    def test_bottoms_on_the_ground_are_never_seen(self):
        tris = np.concatenate([box([0, 0, 0], [1, 1, 1]), box([0.1, 0, 0.1], [0.5, 0.3, 0.5])])
        uvs = np.concatenate([np.zeros((12, 3, 2)), np.full((12, 3, 2), .5)])
        found = S.overlaps(tris, ["a"] * 12 + ["b"] * 12, uvs, eps=0.001)
        self.assertEqual(found["zfight"], [])
        lifted = tris + np.array([0, 2, 0])
        self.assertEqual(len(S.overlaps(lifted, ["a"] * 12 + ["b"] * 12, uvs, eps=0.001)["zfight"]), 1)

    def test_a_fight_too_small_to_see_where_it_starts_is_faint(self):
        # A 1 cm2 nose patch 0.8 mm up flickers beyond 58 m, where it is a tenth of a pixel.
        tris = np.concatenate([quad(0.2, 0, .2, 0, .2), quad(0.2008, .05, .06, .05, .06)])
        found = S.overlaps(tris, ["head"] * 2 + ["nose"] * 2, np.concatenate([uv(.1), uv(.7)]), eps=S.eps_for(60))
        self.assertEqual((len(found["zfight"]), len(found["faint"])), (0, 1))
        self.assertTrue(S.visible_fight(1e-4, 0.0))

    def test_depth_resolution_rule(self):
        self.assertAlmostEqual(S.eps_for(60) * 1000, 0.857, places=3)
        self.assertAlmostEqual(S.eps_for(150) * 1000, 5.357, places=3)


class PieceShotTests(unittest.TestCase):
    def test_pieces_follow_shared_corners_within_a_node(self):
        tris = np.concatenate([box([0, 0, 0], [1, 1, 1]), box([2, 0, 0], [3, 1, 1]), quad(0.2, 5, 6)])
        names = ["a"] * 24 + ["b"] * 2
        ids = P.piece_ids(tris, names)
        self.assertEqual(len(set(ids)), 3)
        self.assertEqual(len(set(ids[:12])), 1)

    def test_shot_draws_four_views_with_distinct_piece_colours(self):
        tris = np.concatenate([box([0, 0, 0], [1, 1, 1]), box([0.2, 1, 0.2], [0.8, 1.2, 0.8])])
        img = P.shot(tris, ["a"] * 24, marks=[[0.5, 1.0, 0.5]])
        self.assertEqual(img.size, (P.SIZE * 4, P.SIZE))
        front = np.asarray(img)[:, :P.SIZE].reshape(-1, 3)
        colours = {tuple(c) for c in front if tuple(c) != (255, 255, 255)}
        self.assertGreater(len(colours), 2)


if __name__ == "__main__":
    unittest.main()
