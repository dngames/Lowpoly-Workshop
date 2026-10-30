import unittest
import numpy as np
from lowpoly_workshop.kit.vehicle_atlas import fallback_linear,pack_vehicle_atlas

class VehicleAtlasTest(unittest.TestCase):
    def test_mask_is_opaque_data_not_opacity(self):
        c=np.full((2048,2048,3),216,np.uint8);m=np.zeros_like(c);m[10:20,10:20,0]=255
        out=pack_vehicle_atlas(c,m)
        self.assertEqual(out.shape,(2048,2048,4))
        self.assertEqual(out[12,12].tolist(),[216,216,216,255])
        self.assertEqual(out[0,0].tolist(),[216,216,216,0])
        m[0,0,0]=127
        with self.assertRaises(ValueError):pack_vehicle_atlas(c,m)
    def test_fallback_uses_exact_paint_and_unmasked_linear_texels(self):
        c=np.full((4,4,3),128,np.uint8);uv=[[0,0],[1,0],[0,1]]
        np.testing.assert_allclose(fallback_linear(c,uv,'paint',{'paint'},[.05,.51,.53]),[.05,.51,.53])
        expected=((128/255+.055)/1.055)**2.4
        np.testing.assert_allclose(fallback_linear(c,uv,'fixed',{'paint'},[.05,.51,.53]),[expected]*3)
    def test_fallback_averages_covered_texels_in_linear_space(self):
        c=np.zeros((2,2,3),np.uint8);c[0,1]=255
        # Three texel centres lie on or inside this triangle: black, white, black.
        value=fallback_linear(c,[[0,0],[1,0],[0,1]],'glass',set(),[0,0,0])
        np.testing.assert_allclose(value,[1/3]*3)

if __name__=='__main__':unittest.main()
