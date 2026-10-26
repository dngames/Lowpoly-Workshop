import unittest
from pathlib import Path
import numpy as np
from lowpoly_workshop.kit.asset import Asset
from lowpoly_workshop.kit.mesh import triangles, tri_count
from lowpoly_workshop.kit import rig
from lowpoly_workshop.quality import topology, relation_result

EXAMPLE=Path(__file__).resolve().parents[1]/'lowpoly_workshop/assets/examples/trail-guide'

class CharacterExampleTests(unittest.TestCase):
    example=EXAMPLE
    budget=3000
    def test_closed_nodes_and_triangle_budget(self):
        a=Asset(self.example);nodes=a.build()
        self.assertLessEqual(sum(tri_count(n) for n in nodes.values()),self.budget)
        for name in a.spec['outputs'][0]['contract']['closed']:
            stats=topology(triangles({name:nodes[name]})[0])
            self.assertFalse(any(stats[k] for k in ['boundary_edges','nonmanifold_edges','winding_edges','duplicates','degenerate']),name)
    def test_height_and_ground_are_editable_contracts(self):
        a=Asset(self.example)
        for height in [1.4,1.72,2.0]:
            nodes=a.gen.build(a.gen.params(overrides={'height':height}))
            pts=triangles(nodes)[0].reshape(-1,3)
            self.assertAlmostEqual(pts[:,1].min(),0)
            self.assertAlmostEqual(pts[:,1].max(),height)
    def test_wave_keeps_joints_attached_and_hand_clear(self):
        a=Asset(self.example);nodes=a.build();clip=a.gen.clips(nodes,a.params())['Greeting']
        self.assertEqual(len(clip['frames']),49)
        np.testing.assert_allclose(clip['frames'][0]['UpperR'],clip['frames'][-1]['UpperR'],atol=1e-12)
        for pose in clip['frames'][::4]:
            tf=rig.world_transforms(nodes,pose);geo={}
            for name,nd in nodes.items():
                t=triangles({name:nd})[0];r,offset=tf[name];geo[name]=t@r.T+offset
            for host,child in [('Body','UpperR'),('UpperR','LowerR')]:
                self.assertTrue(relation_result(dict(type='connected',a=host,b=child,max_gap=.008),geo)[0],(host,child,pose))
            self.assertTrue(relation_result(dict(type='clear',a='LowerR',b='Head',min_gap=.015),geo)[0],pose)
            for paint,head in zip(tf['FacePaint'],tf['Head']):np.testing.assert_allclose(paint,head,atol=1e-12)
    def test_invalid_dimensions_fail(self):
        a=Asset(self.example)
        with self.assertRaises(ValueError):a.gen.params(overrides={'height':-1})


class HighCharacterExampleTests(CharacterExampleTests):
    example=EXAMPLE.parent/"trail-guide-high"
    budget=40000

    def test_detail_is_geometry_and_higher_density(self):
        a=Asset(self.example);n=a.build()
        self.assertGreater(sum(tri_count(x) for x in n.values()),20000)
        # Features and accessories add geometry, rather than just subdividing a low shell.
        low=Asset(EXAMPLE).build()
        for name in ["Body","Head","LowerR","ShoeL"]:
            self.assertGreater(tri_count(n[name]),tri_count(low[name]),name)
