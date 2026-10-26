"""Closed economical wildlife forms. See docs/legacy-port-audit.md."""
import math
import numpy as np
from .mesh import loft,tri_count
from .organic import closed_surface
from .animal import cleanup
from .glb import intersect
from . import rig

def vertical(m,rows,n=8,cell='body',paint=None):
 start=len(m.faces)
 rings=[np.array([[rx*math.sin(a),y,z+rz*math.cos(a)] for a in (np.arange(n)+.5)*math.tau/n]) for y,z,rx,rz in rows]
 loft(m,rings,cell,caps=(True,True))
 if paint:
  for i in range(start,len(m.faces)):
   q,c,u,t=m.faces[i];m.faces[i]=(q,paint(q.mean(0)),u,t)
 return m.faces[start:]

def spindle(m,sections,n=6,cell='body',paint=None):
 """Longitudinal shell with point ends; no disconnected head or tube seams."""
 start=len(m.faces);rings=[]
 for z,y,rx,ry in sections[1:-1]:
  rings.append(np.array([[rx*math.sin(a),y+ry*math.cos(a),z] for a in (np.arange(n)+.5)*math.tau/n]))
 loft(m,rings,cell,caps=(False,False))
 for row,ring in [(sections[0],rings[0]),(sections[-1],rings[-1])]:
  z,y,_,_=row;tip=np.array([0,y,z]);inside=np.array([0,np.mean(ring[:,1]),np.mean(ring[:,2])])
  for i in range(n):m.face([tip,ring[i],ring[(i+1)%n]],cell,inside)
 if paint:
  for i in range(start,len(m.faces)):
   q,c,u,t=m.faces[i];m.faces[i]=(q,paint(q.mean(0)),u,t)
 return m.faces[start:]

def leaf(m,outline,thickness,cell='body',paint=None):
 """Closed biconvex shell; two apex fans provide depth with 2*N triangles."""
 start=len(m.faces);q=np.asarray(outline,float);c=q.mean(0)
 for sign in [-1,1]:
  normal=np.cross(q[1]-q[0],q[2]-q[0]);normal=normal/np.linalg.norm(normal)
  apex=c+normal*sign*thickness
  for i in range(len(q)):
   tri=np.array([q[i],q[(i+1)%len(q)],apex]);m.face(tri,paint(tri.mean(0)) if paint else cell,c)
 return m.faces[start:]

def tetra(m,points,cell):
 start=len(m.faces);q=np.asarray(points,float)
 for ids in [(0,1,2),(0,3,1),(0,2,3),(1,3,2)]:m.face(q[list(ids)],cell,q.mean(0))
 return m.faces[start:]

def node(m,parent=None,pivot=(0,0,0),shells=()):
 return {'parent':parent,'pivot':np.asarray(pivot,float),'faces':m.faces,'smooth':True,'shells':list(shells)}

def moving_pose(child,axis,angle):
 """Game radians to rig degrees; wildlife right wings mirror the left Z flap."""
 pose=[0,0,0]
 pose[axis]=math.degrees(-angle if axis==2 and child.endswith('_arm_R') else angle)
 return pose

def checks(asset,report,budget,moving=None):
 nodes=asset.build();total=sum(tri_count(n) for n in nodes.values())
 report(total<=budget,'Runtime triangle budget',str(total))
 report(all(n.get('smooth') for n in nodes.values()),'Smooth organic shading')
 report(all(closed_surface(s) for n in nodes.values() for s in n.get('shells',[])),'Closed continuous anatomy shells before hidden-face cleanup')
 report(all(np.all(np.isfinite(q)) for n in nodes.values() for q,*_ in n['faces']),'Finite geometry')
 if moving:
  body,children,axis,angles,band=moving
  bt,_=rig.posed_triangles({body:nodes[body]},{});gaps=[]
  for child in children:
   for angle in angles:
    pose=moving_pose(child,axis,angle)
    ht,_=rig.posed_triangles({child:nodes[child]},{child:pose})
    pv=nodes[child]['pivot'];root=ht[np.min(np.linalg.norm(ht-pv,axis=2),axis=1)<band]
    if not len(root) or not intersect(bt,root):gaps.append((child,round(float(np.radians(pose[axis])),3)))
  report(not gaps,'Moving roots remain attached across full game motion',str(gaps))
