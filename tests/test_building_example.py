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
        self.assertEqual(set(a.gen.FEATURES[3]),{'far_roof','far_walls','front_gable'})

    def test_supports_reach_canopy_and_benches_sit_on_terrace(self):
        a=Asset(EXAMPLE)
        for lod in range(3):
            a.build(str(lod));f=a.gen.FEATURES[lod]
            for name,fs in f.items():
                pts=np.concatenate([q for q,*_ in fs])
                if name.startswith('terrace_post'):
                    z=pts[:,2].mean();roof=np.asarray(f['terrace_roof'][0][0]);slope,offset=np.linalg.lstsq(np.column_stack([roof[:,2],np.ones(len(roof))]),roof[:,1],rcond=None)[0];roof_top=slope*z+offset
                    self.assertAlmostEqual(pts[:,1].min(),.72)
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
            self.assertLess(pts[:,1].max(),9.85)
        with self.assertRaises(ValueError):a.gen.params('4')

    def test_materials_are_painted_and_geometry_adds_relief(self):
        a=Asset(EXAMPLE);col,_=a.gen.ATLAS.paint()
        for cell in ['wood','plaster','roof','stonegrain']:
            x0,y0,x1,y1=a.gen.ATLAS.layout()[cell]
            patch=col[y0:y1,x0:x1].astype(float)
            self.assertGreater(float(patch.std(axis=(0,1)).mean()),2,cell)
        nodes=a.build('0');f=a.gen.FEATURES[0]
        from lowpoly_workshop.quality import topology
        self.assertEqual(topology(triangles(nodes)[0])['duplicates'],0)
        for prefix in ['main_tile','hip_tile','gable_tile','canopy_tile','ridge_cap','stone_','upper_post','terrace_brace']:
            self.assertTrue(any(n.startswith(prefix) for n in f),prefix)
        for name,faces in f.items():
            if 'tile' in name:
                # Curved tile strips are closed relief, rather than a single image plane.
                from lowpoly_workshop.kit.organic import closed_surface,surface_orientation
                self.assertTrue(closed_surface(faces),name)
                self.assertTrue(surface_orientation(faces)["ok"],name)

    def test_reference_depth_and_real_timber_gable_ends(self):
        a=Asset(EXAMPLE)
        for lod in range(4):
            a.build(str(lod));f=a.gen.FEATURES[lod]
            wall=f['ground_floor' if lod<3 else 'far_walls']
            pts=np.concatenate([q for q,*_ in wall])
            self.assertAlmostEqual(float(np.ptp(pts[:,2])),7.0)
            roof=f['main_roof' if lod<3 else 'far_roof']
            ends=[q for q,cell,*_ in roof if cell=='dark']
            self.assertEqual(len(ends),2)
            for end in ends:
                self.assertGreater(float(np.ptp(end[:,1])),1.8)
                self.assertAlmostEqual(float(np.ptp(end[:,0])),0)
            front=f['front_gable'][0][0]
            self.assertLess(front[:,2].max(),3.5)
            self.assertGreater(float(np.ptp(front[:,1])),1.3)

    def test_hip_tiles_stay_on_the_skirt_below_timber_end(self):
        a=Asset(EXAMPLE);a.build('0')
        for name,fs in a.gen.FEATURES[0].items():
            if name.startswith('hip_tile'):
                pts=np.concatenate([q for q,*_ in fs])
                self.assertLessEqual(float(pts[:,1].max()),a.gen.HIP_Y+.14,name)
        apron=[np.concatenate([q for q,*_ in fs]) for name,fs in a.gen.FEATURES[0].items() if name.startswith('gable_apron_tile')]
        self.assertTrue(apron, 'The exposed roof below the gable must retain raised tile rows')
        for pts in apron:self.assertGreaterEqual(float(pts[:,2].min()),a.gen.Z_GABLE-1e-7)
        front_field=[fs for name,fs in a.gen.FEATURES[0].items() if name.startswith('main_tile') and abs(np.concatenate([q for q,*_ in fs])[:,0].mean())<1 and np.concatenate([q for q,*_ in fs])[:,2].mean()>a.gen.Z_GABLE]
        self.assertTrue(front_field, 'Gable exclusion must stop at the actual gable front')
        for z in np.linspace(0,a.gen.Z_EAVE,20):
            expected=a.gen.RIDGE-(a.gen.RIDGE-a.gen.EAVE)*z/a.gen.Z_EAVE
            self.assertAlmostEqual(a.gen.main_height([0,0,z]),expected)
