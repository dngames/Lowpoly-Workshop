"""Regression checks for rigid hidden-face cleanup and zero-triangle band seams."""
import unittest
import numpy as np
from lowpoly_workshop.kit.mesh import Mesh,hexa,tube,X,Y,Z,newell,nrm
from lowpoly_workshop.kit.character_cleanup import finish_character,remove_internal_faces,close_planar_ends
from lowpoly_workshop.quality import topology
from lowpoly_workshop.kit.mesh import triangles
def solid_triangles(node):
    return triangles({'part':dict(node,faces=[f for f in node['faces'] if not f[3]])})[0].reshape(-1,3,3)
def open_edges(tris):return topology(tris)['boundary_edges']


def cube(m,centre,radius):
    hexa(m,np.asarray(centre,float),(X,Y,Z),(radius,radius,radius),'skin')

class CharacterCleanupTests(unittest.TestCase):
    def test_hidden_solid_removed_but_visible_surface_preserved(self):
        m=Mesh();cube(m,(0,0,0),1);outer=list(m.faces);cube(m,(.2,.1,.3),.1)
        node={'faces':m.faces};self.assertEqual(remove_internal_faces(node),12)
        self.assertEqual(len(node['faces']),6)
        for a,b in zip(outer,node['faces']):np.testing.assert_array_equal(a[0],b[0])

    def test_independently_moving_nodes_never_occlude_each_other(self):
        a=Mesh();b=Mesh();cube(a,(0,0,0),1);cube(b,(0,0,0),.1)
        nodes={'Torso':{'faces':a.faces},'HandL':{'faces':b.faces}}
        finish_character(nodes)
        self.assertEqual(len(nodes['HandL']['faces']),6)

    def test_colour_band_rings_close_without_added_triangles(self):
        m=Mesh();tube(m,np.array([0,1,0]),np.array([0,0,0]),.1,.08,n=6,up=Z,cell='shirt',caps=(True,False))
        tube(m,np.array([0,0,0]),np.array([0,-1,0]),.09,.07,n=6,up=Z,cell='skin',caps=(False,True))
        node={'faces':m.faces};before=len(solid_triangles(node))
        self.assertGreater(open_edges(solid_triangles(node)),0)
        self.assertEqual(close_planar_ends(node),0)
        self.assertEqual(open_edges(solid_triangles(node)),0)
        self.assertEqual(len(solid_triangles(node)),before)

    def test_inside_vertices_do_not_justify_crossing_a_concave_surface(self):
        # A U-shaped closed volume assembled from boundary faces of unit voxels.
        occupied={(x,y,0) for x in range(4) for y in range(4) if x in (0,3) or y==0}
        shell=Mesh()
        for x,y,z in occupied:
            m=Mesh();hexa(m,np.array([x-1.5,y-1.5,0]),(X,Y,Z),(.5,.5,1),'skin')
            for face in m.faces:
                direction=np.rint(nrm(newell(face[0]))).astype(int)
                neighbour=tuple(np.array([x,y,z])+direction)
                if neighbour not in occupied:shell.faces.append(face)
        candidate=(np.array([[-1.5,1,0],[1.5,1,0],[-1.5,1.5,0]]),'shirt',None,True)
        shell.faces.append(candidate);node={'faces':shell.faces}
        self.assertEqual(remove_internal_faces(node),0)
        self.assertIs(node['faces'][-1],candidate)

if __name__=='__main__':unittest.main()
