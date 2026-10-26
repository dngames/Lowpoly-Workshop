import hashlib,json,tempfile,unittest
from pathlib import Path
import numpy as np
from PIL import Image
from lowpoly_workshop.templates import create
from lowpoly_workshop.cli import main
from lowpoly_workshop.kit.asset import Asset
from lowpoly_workshop.kit.mesh import triangles
from lowpoly_workshop.kit.camfit import make_cam
from lowpoly_workshop.kit.raster import render

class DiagnosticCliTests(unittest.TestCase):
    def test_public_commands_preserve_source_and_fitted_camera(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=create(Path(tmp)/'diagnostic');a=Asset(folder);nodes=a.build();t,c,_=triangles(nodes)
            cam=[0,0,0,40,70,64,64]
            rgb,mask,_=render(t,c,make_cam(cam,a.target()),128,128,palette=a.palette(nodes),classes={'_default':1})
            Image.fromarray(np.where((mask>0)[...,None],rgb,240).astype(np.uint8)).save(folder/'ref/calibration.png')
            s=a.spec;s['sets']={'calibration':{'image':'ref/calibration.png','views':{'front':{'box':[0,0,128,128]}}}}
            s['palettes']={'default':{'1':['#609776']}};s['cell_class']={'body':1}
            (folder/'asset.json').write_text(json.dumps(s));camera=folder/'cams/calibration/front.json';camera.parent.mkdir(parents=True);camera.write_text(json.dumps({'cam':cam}))
            paths=[folder/'asset.json',folder/'gen.py',folder/'ref/calibration.png',camera]
            before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
            main([str(folder),'coverage','calibration','--size','64','--budget','2'])
            main([str(folder),'paint'])
            report=json.loads((folder/'out/coverage/report.json').read_text())['calibration']
            self.assertFalse(report['review']['used_for_fit_or_paint'])
            self.assertGreater(report['observed_area_fraction'],0)
            self.assertTrue(report['suggestions'])
            self.assertTrue((folder/'out/paint/report.json').exists())
            self.assertEqual(before,{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
