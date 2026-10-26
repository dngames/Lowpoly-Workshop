import unittest
from pathlib import Path
import numpy as np
from lowpoly_workshop.kit.asset import Asset
from lowpoly_workshop.kit.mesh import triangles,tri_count

EXAMPLE=Path(__file__).resolve().parents[1]/'lowpoly_workshop/assets/examples/station-rest-house'

class BuildingExampleTests(unittest.TestCase):
    def test_facades_survive_detail_reduction(self):
        a=Asset(EXAMPLE);bounds=[];counts=[]
        for lod in range(3):
            nodes=a.build(str(lod));counts.append(sum(tri_count(n) for n in nodes.values()))
            features=a.gen.FEATURES[lod]
            windows={name:np.concatenate([q for q,*_ in fs]) for name,fs in features.items()
                     if name in ['entrance','left','right'] or name in [side+str(i) for side in ['front','back'] for i in range(4)]}
            self.assertEqual(len(windows),11)
            bounds.append({name:(pts.min(0)[[1,2] if name in ['left','right'] else [0,1]],pts.max(0)[[1,2] if name in ['left','right'] else [0,1]]) for name,pts in windows.items()})
        self.assertTrue(counts[0]>counts[1]>counts[2])
        for later in bounds[1:]:
            for name in bounds[0]:np.testing.assert_allclose(later[name],bounds[0][name],atol=1e-7)
        far=a.build('3');self.assertLess(sum(tri_count(n) for n in far.values()),counts[-1])
        self.assertEqual(set(a.gen.FEATURES[3]),{'far_roof','far_walls'})

    def test_supports_reach_canopy_and_benches_sit_on_terrace(self):
        a=Asset(EXAMPLE)
        for lod in range(3):
            a.build(str(lod));f=a.gen.FEATURES[lod]
            for name,fs in f.items():
                pts=np.concatenate([q for q,*_ in fs])
                if name.startswith('terrace_post'):
                    z=pts[:,2].mean();roof_top=3.45-.5*(z-4.4)/2.05
                    self.assertAlmostEqual(pts[:,1].min(),0)
                    self.assertGreaterEqual(pts[:,1].max(),roof_top-.16)
                    self.assertLessEqual(pts[:,1].max(),roof_top)
                if name.startswith('bench') and '_leg' in name:
                    self.assertAlmostEqual(pts[:,1].min(),.26)

    def test_scale_origin_and_invalid_level(self):
        a=Asset(EXAMPLE)
        for lod in range(4):
            pts=triangles(a.build(str(lod)))[0].reshape(-1,3)
            self.assertAlmostEqual(pts[:,1].min(),0)
            self.assertGreaterEqual(pts[:,1].max(),8)
            self.assertLess(pts[:,1].max(),8.35)
        with self.assertRaises(ValueError):a.gen.params('4')

    def test_materials_are_painted_and_geometry_adds_relief(self):
        a=Asset(EXAMPLE);col,_=a.gen.ATLAS.paint()
        for cell in ['wood','plaster','roof','stonegrain']:
            x0,y0,x1,y1=a.gen.ATLAS.layout()[cell]
            patch=col[y0:y1,x0:x1].astype(float)
            self.assertGreater(float(patch.std(axis=(0,1)).mean()),2,cell)
        a.build('0');f=a.gen.FEATURES[0]
        for prefix in ['main_tile','hip_tile','gable_tile','canopy_tile','ridge_cap','stone_','upper_post','terrace_brace']:
            self.assertTrue(any(n.startswith(prefix) for n in f),prefix)
        for name,faces in f.items():
            if 'tile' in name:
                # Curved tile strips are closed relief, rather than a single image plane.
                from lowpoly_workshop.kit.organic import closed_surface,surface_orientation
                self.assertTrue(closed_surface(faces),name)
                self.assertTrue(surface_orientation(faces)["ok"],name)
