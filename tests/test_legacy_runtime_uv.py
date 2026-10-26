import unittest
import numpy as np
from lowpoly_workshop.kit.runtime_uv import face_uvs

class RuntimeUvTests(unittest.TestCase):
    def test_runtime_decal_addresses_whole_cell(self):
        q=[[0,0,0],[2,0,0],[2,3,0],[0,3,0]]
        self.assertEqual(face_uvs(q,[(0,0),(1,0),(1,1),(0,1)],'decal_banner_0'),[(0.,1.),(1.,1.),(1.,0.),(0.,0.)])
    def test_missing_decal_uv_is_an_error(self):
        with self.assertRaises(ValueError):face_uvs([[0,0,0],[1,0,0],[0,1,0]],None,'decal_text_startLine')
    def test_solids_keep_physical_tile_scale(self):
        q=np.array([[1,2,3],[5,2,3],[5,2,9],[1,2,9]],float)
        uv=np.array(face_uvs(q,None,'roofSlate'))
        np.testing.assert_allclose(np.ptp(uv,axis=0),[4,6])
        # Translation moves phase but never rescales a tiled surface.
        shifted=np.array(face_uvs(q+[10,20,30],None,'roofSlate'))
        np.testing.assert_allclose(shifted-uv,[[10,-30]]*4)

if __name__=='__main__':unittest.main()
