import unittest
import numpy as np
from lowpoly_workshop.kit.mesh import triangulate_profile
from lowpoly_workshop.kit.raster import background_mask, classify

class LegacyProfileTests(unittest.TestCase):
    def test_concave_cap_preserves_area_and_avoids_void(self):
        for p in [np.array([[0,0],[2,0],[2,1],[1,1],[1,2],[0,2]],float)]:
            for polygon in [p,p[::-1]]:
                tris=polygon[np.asarray(triangulate_profile(polygon))]
                a,b=tris[:,1]-tris[:,0],tris[:,2]-tris[:,0]
                self.assertAlmostEqual(np.abs(a[:,0]*b[:,1]-a[:,1]*b[:,0]).sum()/2,3)
                centres=tris.mean(1)
                self.assertFalse(np.any((centres[:,0]>1)&(centres[:,1]>1)))
    def test_zero_area_profile_fails(self):
        with self.assertRaises(ValueError):triangulate_profile([[0,0],[1,0],[2,0]])
    def test_gradient_mask_keeps_cream_object(self):
        y,x=np.mgrid[-1:1:80j,-1:1:80j]
        grey=200+20*x+20*y+10*x*x
        image=np.stack([grey]*3,-1).astype(np.uint8)
        image[30:50,30:50]=[244,226,195]
        mask=background_mask(image,24,'gradient')
        self.assertTrue(mask[5,5]);self.assertFalse(mask[40,40])
        classes=classify(image,{1:['#f4e2c3']},bg_mode='gradient')
        self.assertEqual(classes[5,5],0);self.assertEqual(classes[40,40],1)
    def test_gradient_rejects_undersized_crop(self):
        with self.assertRaises(ValueError):background_mask(np.zeros((8,8,3)),mode='gradient')
