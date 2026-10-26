import tempfile
import unittest
from pathlib import Path
import numpy as np
from lowpoly_workshop.kit.mesh import Mesh, hexa, X, Y, Z
from lowpoly_workshop.kit.organic import surface_orientation
from lowpoly_workshop.kit.wildlife import leaf, spindle, moving_pose
from lowpoly_workshop.kit.atomic import replacing, write_json

class LegacyHelpers(unittest.TestCase):
    def test_closed_can_still_be_inward(self):
        m=Mesh();hexa(m,np.zeros(3),[X,Y,Z],np.ones(3),'body')
        self.assertTrue(surface_orientation(m.faces)['ok'])
        reversed_faces=[(q[::-1],c,u,t) for q,c,u,t in m.faces]
        wrong=surface_orientation(reversed_faces)
        self.assertTrue(wrong['closed']);self.assertFalse(wrong['ok'])
        self.assertLess(wrong['signed_volume_m3'],0)

    def test_upright_fin_has_real_thickness(self):
        m=Mesh();faces=leaf(m,[[0,0,0],[0,1,0],[0,.5,1]],.05,'body')
        self.assertTrue(surface_orientation(faces)['ok'])
        self.assertAlmostEqual(np.ptp(np.concatenate([f[0] for f in faces])[:,0]),.1)

    def test_point_ended_body_is_closed(self):
        m=Mesh();faces=spindle(m,[[-1,0,0,0],[-.5,0,.2,.3],[.5,0,.2,.3],[1,0,0,0]])
        self.assertTrue(surface_orientation(faces)['ok'])

    def test_wing_motion_converts_and_mirrors_only_signed_z(self):
        np.testing.assert_allclose(moving_pose('wing_arm_L',2,.5),[0,0,np.degrees(.5)])
        np.testing.assert_allclose(moving_pose('wing_arm_R',2,.5),[0,0,-np.degrees(.5)])
        np.testing.assert_allclose(moving_pose('wing_arm_R',0,.5),[np.degrees(.5),0,0])

    def test_interrupted_output_keeps_previous_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'asset.glb';path.write_bytes(b'previous')
            with self.assertRaises(RuntimeError):
                with replacing(str(path)) as staging:
                    Path(staging).write_bytes(b'incomplete');raise RuntimeError('interrupted')
            self.assertEqual(path.read_bytes(),b'previous')
            self.assertEqual(list(Path(tmp).iterdir()),[path])

    def test_successful_atomic_json_replaces_previous(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'report.json';path.write_text('previous')
            write_json(str(path),{'ok':True})
            self.assertIn('true',path.read_text())
