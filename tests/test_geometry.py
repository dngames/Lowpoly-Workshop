import unittest,tempfile,json
from pathlib import Path
import numpy as np
from lowpoly_workshop.kit.mesh import Mesh,hexa,triangles,X,Y,Z
from lowpoly_workshop.kit.atlas import Atlas
from lowpoly_workshop.quality import topology,relation_result,check_relations,uv_diagnostics
from lowpoly_workshop.surface import project_rays,wrapped_patch,attachment_frame,closest_points
from lowpoly_workshop.spec import validate_nodes
from lowpoly_workshop.kit.skin import vertex_weights

def cube(c=(0,0,0),r=1):
    m=Mesh();hexa(m,np.array(c,float),[X,Y,Z],(r,r,r),'body');return m

def node(m,parent=None,pivot=(0,0,0)):
    return dict(parent=parent,pivot=np.array(pivot,float),faces=m.faces)
def tris(m):return triangles({'x':node(m)})[0]

class GeometryTests(unittest.TestCase):
    def test_closed_cube(self):
        t=topology(tris(cube()));self.assertEqual(sum(t[k] for k in ('boundary_edges','nonmanifold_edges','winding_edges','duplicates','degenerate')),0)
    def test_missing_chin_cap(self):
        m=cube();m.faces.pop();self.assertGreater(topology(tris(m))['boundary_edges'],0)
    def test_duplicate_faces(self):
        m=cube();m.faces.append(m.faces[0]);t=topology(tris(m));self.assertGreater(t['duplicates'],0);self.assertGreater(t['nonmanifold_edges'],0)
    def test_wrong_winding(self):
        m=cube();p,c,u,t=m.faces[0];m.faces[0]=(p[::-1],c,u,t);self.assertGreater(topology(tris(m))['winding_edges'],0)
    def test_degenerate(self):
        self.assertEqual(topology([[[0,0,0],[1,0,0],[2,0,0]]])['degenerate'],1)
    def test_exact_ray_fit(self):
        p,n,d=project_rays([[0,2,0]],[[0,-1,0]],tris(cube()),.02)
        np.testing.assert_allclose(p,[[0,1.02,0]]);np.testing.assert_allclose(n,[[0,1,0]]);self.assertAlmostEqual(d[0],1)
    def test_ray_miss(self):
        with self.assertRaises(ValueError):project_rays([[4,2,0]],[0,-1,0],tris(cube()))
    def test_zero_direction(self):
        with self.assertRaises(ValueError):project_rays([[0,2,0]],[0,0,0],tris(cube()))
    def test_closest_triangle_interior(self):
        p,d=closest_points([[.2,.2,1]],[[[0,0,0],[1,0,0],[0,1,0]]]);np.testing.assert_allclose(p,[[.2,.2,0]]);self.assertAlmostEqual(d[0],1)
    def test_closest_triangle_edge(self):
        p,d=closest_points([[2,0,0]],[[[0,0,0],[1,0,0],[0,1,0]]]);np.testing.assert_allclose(p,[[1,0,0]])
    def test_frame_follows_helmet_normal(self):
        n=np.array([.6,.3,.7]);r=attachment_frame(n);np.testing.assert_allclose(r[:,1],n/np.linalg.norm(n));np.testing.assert_allclose(r.T@r,np.eye(3),atol=1e-9);self.assertAlmostEqual(np.linalg.det(r),1)
    def test_frame_parallel_tangent(self):
        r=attachment_frame([1,0,0],[1,0,0]);np.testing.assert_allclose(r.T@r,np.eye(3))
    def test_zero_frame_rejected(self):
        with self.assertRaises(ValueError):attachment_frame([0,0,0])
    def test_wrapped_fringe_has_thickness_and_closed_perimeter(self):
        # Projection wraps around a bevelled host rather than leaving a flat front board.
        from lowpoly_workshop.kit.mesh import tube
        h=Mesh();tube(h,np.array([0,0,0.]),np.array([0,1,0.]),.3,n=12,cell='body',caps=(True,True),up=Z)
        angles=np.linspace(-75,75,7)*np.pi/180
        rows=np.array([[[.6*np.sin(a),y,.6*np.cos(a)] for a in angles] for y in (.4,.6)])
        dirs=np.array([[[-np.sin(a),0,-np.cos(a)] for a in angles]]*2)
        m=Mesh();outer,inner=wrapped_patch(m,rows,dirs,tris(h),'body')
        self.assertGreater(np.ptp(outer[:,:,2]),.15)
        np.testing.assert_allclose(np.linalg.norm(outer-inner,axis=2),.012)
        t=topology(tris(m));self.assertEqual(t['boundary_edges'],0);self.assertEqual(t['winding_edges'],0)
    def test_gap_rejected(self):
        ok,detail=relation_result(dict(type='connected',a='a',b='b',max_gap=.01),{'a':tris(cube()),'b':tris(cube((2.2,0,0)))})
        self.assertFalse(ok);self.assertAlmostEqual(detail['min_gap'],.2)
    def test_overlap_connected(self):
        self.assertTrue(relation_result(dict(type='connected',a='a',b='b'),{'a':tris(cube()),'b':tris(cube((1.8,.1,.2)))})[0])
    def test_hidden_containment_is_collision(self):
        self.assertFalse(relation_result(dict(type='clear',a='a',b='b'),{'a':tris(cube(r=.1)),'b':tris(cube())})[0])
    def test_clearance_pass(self):
        self.assertTrue(relation_result(dict(type='clear',a='a',b='b',min_gap=.1),{'a':tris(cube()),'b':tris(cube((3,0,0)))})[0])
    def test_shoe_support_offset(self):
        geo={'shoe':tris(cube((0,2,0),.1)),'pedal':tris(cube())};r=dict(type='support',a='shoe',b='pedal',samples=[[0,1.02,0]],direction=[0,-1,0],min=.01,max=.03)
        self.assertTrue(relation_result(r,geo)[0]);r['samples']=[[0,1.2,0]];self.assertFalse(relation_result(r,geo)[0])
    def test_pose_exposes_joint_gap(self):
        nodes={'a':node(cube()),'b':node(cube((1.15,0,0),.2),'a',(0,0,-2))};rows=[]
        check_relations(nodes,[dict(type='connected',a='a',b='b',max_gap=.01)],{'bend':{'b':[90,0,0]}},lambda ok,text,detail:rows.append((ok,text)))
        self.assertTrue(rows[0][0]);self.assertFalse(rows[1][0]);self.assertTrue(any('bend' in text for _,text in rows))
    def test_parent_sort_and_cycle(self):
        atlas=Atlas({'body':('#ffffff',None)})
        nodes={'child':node(cube(),'parent'),'parent':node(cube())}
        self.assertEqual(list(validate_nodes(nodes,atlas)),['parent','child']);nodes['parent']['parent']='child'
        with self.assertRaises(ValueError):validate_nodes(nodes,atlas)
    def test_invalid_uv_rejected(self):
        m=cube();p,c,_,t=m.faces[0];m.faces[0]=(p,c,[(2,2)]*4,t)
        with self.assertRaises(ValueError):validate_nodes({'bad':node(m)},Atlas({'body':('#ffffff',None)}))
    def test_stable_far_bone_weights(self):
        seg={'a':(np.zeros(3),Y),'b':(X,X+Y)}
        w=vertex_weights(np.array([[1000,1000,1000]]),['a','b'],seg,.01)
        self.assertAlmostEqual(sum(v for _,v in w[0]),1);self.assertTrue(all(np.isfinite(v) for _,v in w[0]))
    def test_empty_weights_rejected(self):
        with self.assertRaises(ValueError):vertex_weights(np.zeros((1,3)),[],{},.1)
    def test_rgba_is_data_not_opaque_alpha(self):
        a=Atlas({'skin':('#abcdef','A')},mask_channels='RGBA');col,mask=a.paint();self.assertEqual(mask.shape[-1],4);self.assertIn((0,0,0,255),{tuple(x) for x in np.unique(mask.reshape(-1,4),axis=0)});self.assertTrue((mask[0,0]==0).all())

class UVTests(unittest.TestCase):
    def atlas(self):return Atlas({'face':('#ffffff',None,'decal')},decals={'decal':((128,128),lambda *a:None)})
    def test_face_decal_on_chin_rejected(self):
        m=Mesh();m.face([[0,0,0],[1,0,0],[1,0,1],[0,0,1]],'face',uv=[(0,0),(1,0),(1,1),(0,1)])
        nd=node(m);nd['decal_regions']={'face':dict(normal=[0,0,1],min_dot=.3)}
        self.assertTrue(any(i['type']=='decal_wrong_surface' for i in uv_diagnostics({'chin':nd},self.atlas())))
    def test_collapsed_decal(self):
        m=Mesh();m.face([[0,0,0],[1,0,0],[0,1,0]],'face',uv=[(0,0)]*3)
        self.assertEqual(uv_diagnostics({'face':node(m)},self.atlas())[0]['type'],'collapsed_decal_uv')
    def test_stretched_decal(self):
        m=Mesh();m.face([[0,0,0],[20,0,0],[0,1,0]],'face',uv=[(0,0),(1,0),(0,1)])
        nd=node(m);nd['decal_regions']={'face':dict(max_anisotropy=4)}
        self.assertTrue(any(i['type']=='stretched_decal_uv' for i in uv_diagnostics({'face':nd},self.atlas())))
    def test_valid_decal(self):
        m=Mesh();m.face([[0,0,0],[1,0,0],[0,1,0]],'face',uv=[(0,0),(1,0),(0,1)])
        nd=node(m);nd['decal_regions']={'face':dict(normal=[0,0,1],max_anisotropy=4)}
        self.assertEqual(uv_diagnostics({'face':nd},self.atlas()),[])
