"""Regression: removal of duplicate faces must preserve the remaining face's UV cell."""
from pathlib import Path
import sys
import bpy
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from lowpoly_workshop.kit.atlas import Atlas
from lowpoly_workshop.kit.mesh import Mesh
from lowpoly_workshop.kit.blender import build,render

def check(ob,atlas,label):
 mesh=ob.data;uv=mesh.uv_layers.active
 assert len(mesh.polygons)==2,(label,'duplicate face not removed',len(mesh.polygons))
 for poly in mesh.polygons:
  x=sum(mesh.vertices[i].co.x for i in poly.vertices)/len(poly.vertices)
  cell='later' if x>2 else 'first';x0,y0,x1,y1=atlas.layout()[cell]
  for li in poly.loop_indices:
   u,v=uv.data[li].uv
   assert x0<u*1024<x1 and y0<(1-v)*1024<y1,(label,cell,list(uv.data[li].uv))
 print('PASS',label,'UV cells survive duplicate-face removal')

def main():
 m=Mesh();a=[[0,0,0],[1,0,0],[0,1,0]];b=[[3,0,0],[4,0,0],[3,1,0]]
 m.face(a,'first');m.face(a,'first');m.face(b,'later')
 atlas=Atlas({'first':('#ff0000',None),'later':('#00ff00',None)})
 node={'parent':None,'pivot':np.zeros(3),'faces':m.faces}
 ob=build.mesh_object('uv_regression',node,bpy.data.materials.new('test'),atlas)
 check(ob,atlas,'GLB builder')
 render.show_scene({'Test':node},{},atlas)
 ob=next(o for o in bpy.data.objects if o.type=='MESH')
 check(ob,atlas,'review renderer')
if __name__=='__main__':main()
