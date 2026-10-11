import unittest,tempfile,json
from pathlib import Path
import numpy as np
from PIL import Image
from lowpoly_workshop.templates import create
from lowpoly_workshop.kit.asset import Asset
from lowpoly_workshop.kit.mesh import triangles
from lowpoly_workshop.kit.camfit import make_cam,fit_view
from lowpoly_workshop.kit.raster import render
from lowpoly_workshop.kit.compose import run as compose

class FittingTests(unittest.TestCase):
    def test_synthetic_reference_fit_and_compare(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=create(Path(tmp)/'fit');a=Asset(folder);nodes=a.build();t,c,_=triangles(nodes)
            camera=[0,0,0,40,100,64,64]
            rgb,classes,_=render(t,c,make_cam(camera,a.target()),128,128,shade=False,palette=a.palette(nodes),classes={'_default':1,'body':1})
            image=folder/'ref/calibration.png';Image.fromarray(rgb.astype(np.uint8)).save(image)
            spec=a.spec;spec['sets']={'calibration':{'label':'Synthetic rendered calibration, not original art','image':'ref/calibration.png','views':{'front':{'box':[0,0,128,128],'init':camera}}}}
            spec['palettes']={'default':{'1':['#609776']}};spec['cell_class']={'body':1};spec['sheet_denoise']=False
            (folder/'asset.json').write_text(json.dumps(spec));a=Asset(folder)
            solved,scores=fit_view(a,'calibration','front',optimize=False)
            self.assertGreater(scores['fg'],.95);self.assertTrue((folder/'cams/calibration/front.json').exists());self.assertTrue((folder/'out/fit/calibration_front.png').exists())
            rgba=np.concatenate((rgb.astype(np.uint8),((classes>0)*255).astype(np.uint8)[:,:,None]),axis=2)
            dest=folder/'out/render/calibration/front.png';dest.parent.mkdir(parents=True);Image.fromarray(rgba).save(dest)
            comparison=compose(folder);self.assertAlmostEqual(comparison['calibration']['front']['iou'],1,places=3);self.assertTrue((folder/'out/compare/calibration_front.jpg').exists())
