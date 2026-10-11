"""Regression checks for connected, capped organic limb shells (no Blender needed)."""
import sys
import unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
from lowpoly_workshop.kit.mesh import Mesh,tri_count
from lowpoly_workshop.kit.organic import closed_limb,closed_surface


class ClosedLimbTests(unittest.TestCase):
    def test_bent_limb_with_sleeve_is_closed_at_every_joint_and_end(self):
        m=Mesh()
        faces=closed_limb(m,[[.16,.86,0],[.26,.78,.03],[.28,.69,.06],[.28,.60,.18]], [.08,.077,.066,.05], cells=['shirt','skin','skin'])
        self.assertTrue(closed_surface(faces))
        self.assertEqual(tri_count({'faces':faces}),36)
        self.assertEqual({f[1] for f in faces},{'shirt','skin'})
        # Removing either attachment cap must fail the same check used by assets.
        self.assertFalse(closed_surface(faces[:-1]))
        self.assertFalse(closed_surface(faces[:-2]+faces[-1:]))
        # A rigid animation transform preserves closure at every pose.
        for theta in np.linspace(-.5,.5,9):
            c,s=np.cos(theta),np.sin(theta)
            r=np.array([[1,0,0],[0,c,-s],[0,s,c]])
            self.assertTrue(closed_surface([(p@r.T,k,u,t) for p,k,u,t in faces]))

    def test_invalid_segment_colours_are_rejected(self):
        with self.assertRaises(ValueError):
            closed_limb(Mesh(),[[0,0,0],[0,1,0]], [.1,.1], cells=['skin','shirt'])


if __name__=='__main__':
    unittest.main()
