import unittest,tempfile,json,contextlib,io
from pathlib import Path
import numpy as np
from PIL import Image
from lowpoly_workshop.templates import create
from lowpoly_workshop.kit.asset import Asset
from lowpoly_workshop.kit.mesh import triangles
from lowpoly_workshop.kit.camfit import make_cam,fit_view
from lowpoly_workshop.kit.raster import render
from lowpoly_workshop.kit import colourmatch

class ColourMatchTests(unittest.TestCase):
    def project(self,tmp,recolour=None):
        folder=create(Path(tmp)/'colour');a=Asset(folder);nodes=a.build();t,c,_=triangles(nodes)
        camera=[20,15,0,40,100,64,64]
        rgb,classes,_=render(t,c,make_cam(camera,a.target()),128,128,shade=True,palette=a.palette(nodes),classes={'_default':1})
        rgb=np.where((classes>0)[...,None],rgb,255)
        if recolour:rgb=np.where((classes>0)[...,None],rgb*np.array(recolour)/np.array([0x60,0x97,0x76]),255)
        Image.fromarray(np.clip(rgb,0,255).astype(np.uint8)).save(folder/'ref/lit.png')
        spec=a.spec;spec['sets']={'lit':{'label':'Synthetic shaded render, not original art','image':'ref/lit.png','views':{'quarter':{'box':[0,0,128,128],'init':camera}}}}
        spec['palettes']={'default':{'1':['#609776']}};spec['sheet_denoise']=False
        (folder/'asset.json').write_text(json.dumps(spec));a=Asset(folder)
        fit_view(a,'lit','quarter',optimize=False)
        with contextlib.redirect_stdout(io.StringIO()):return folder,colourmatch.run(folder)

    def test_matching_reference_passes_and_unused_cells_are_unseen(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder,report=self.project(tmp)
            self.assertEqual(report['cells']['body']['status'],'ok')
            self.assertLess(report['cells']['body']['d_ab'],3)
            self.assertEqual(report['cells']['trim']['status'],'unseen')
            self.assertTrue((folder/'out/colour/lit_quarter_trust.png').exists())
            self.assertTrue((folder/'out/colour/swatches.png').exists())
            trust=np.asarray(Image.open(folder/'out/colour/lit_quarter_trust.png'))
            self.assertEqual(trust[0,0],0);self.assertGreater((trust>0).sum(),200)

    def test_recoloured_reference_is_flagged_with_a_suggestion(self):
        with tempfile.TemporaryDirectory() as tmp:
            _,report=self.project(tmp,recolour=(0x3f,0x6f,0xb0))
            body=report['cells']['body']
            self.assertEqual(body['status'],'review');self.assertGreater(body['d_ab'],12)
            suggest=colourmatch.srgb_to_lab(np.array([int(body['suggest'][i:i+2],16) for i in (1,3,5)]))
            target=colourmatch.srgb_to_lab(np.array([0x3f,0x6f,0xb0]))
            hue=lambda lab:np.degrees(np.arctan2(lab[2],lab[1]))
            self.assertLess(abs(hue(suggest)-hue(target)),4)

    def test_lab_roundtrip(self):
        for h in ('#609776','#ead8ad','#000000','#ffffff','#d8a879'):
            rgb=np.array([int(h[i:i+2],16) for i in (1,3,5)])
            self.assertEqual(colourmatch.lab_to_hex(colourmatch.srgb_to_lab(rgb)),h)
