"""Smooth, closed low-poly forms shared by the authored animal generators."""
import math
import numpy as np
from .mesh import loft,nrm
from .organic import closed_surface
from .character_cleanup import remove_internal_faces
from . import rig,glb

def section_shape(m,sections,n=8,cell='cream',paint=None):
    start=len(m.faces)
    rings=[]
    for z,y,rx,ry in sections:
        rings.append(np.array([[rx*math.sin(a),y+ry*math.cos(a),z] for a in (np.arange(n)+.5)*2*math.pi/n]))
    loft(m,rings,cell,caps=(True,True))
    if paint:
        for i in range(start,len(m.faces)):
            pts,c,uv,thin=m.faces[i];m.faces[i]=(pts,paint(np.mean(pts,axis=0)),uv,thin)
    return m.faces[start:]

def bulb(m,c,r,n=6,cell='cream'):
    start=len(m.faces);c=np.asarray(c);r=np.asarray(r)
    rows=[]
    for h,w in [(-.75,.55),(0,1),(.75,.55)]:
        rows.append(np.array([c+[r[0]*w*math.sin(a),r[1]*h,r[2]*w*math.cos(a)] for a in (np.arange(n)+.5)*2*math.pi/n]))
    loft(m,rows,cell,caps=(True,True));return m.faces[start:]

def ear(m,base,tip,width,cell='cream',inner=None):
    base=np.asarray(base);tip=np.asarray(tip);centre=(base+tip)/2
    axis=nrm(tip-base);cross=nrm(np.cross(axis,[0,1,0]))*width
    ring=[base,centre+cross,tip,centre-cross]
    for sign in (-1,1):
        apex=centre+np.array([0,sign*.018,0])
        for i in range(4):m.face([ring[i],ring[(i+1)%4],apex],inner if inner and sign>0 else cell,centre)

def surface_patch(m,points,cell):
    # Use the tangent plane of the foremost polygon at the feature centre. Projecting
    # each corner independently can bury the patch interior beneath a convex coarse head.
    centre=np.mean(points,axis=0);x,y=centre[:2];highest=None;plane=None
    for face,*_ in m.faces:
        for i in range(1,len(face)-1):
            tri=face[[0,i,i+1]];a,b,c=tri
            den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
            if abs(den)<1e-10:continue
            u=((b[1]-c[1])*(x-c[0])+(c[0]-b[0])*(y-c[1]))/den
            v=((c[1]-a[1])*(x-c[0])+(a[0]-c[0])*(y-c[1]))/den;w=1-u-v
            if min(u,v,w)<-1e-6:continue
            z=u*a[2]+v*b[2]+w*c[2]
            if highest is None or z>highest:highest=z;plane=np.cross(b-a,c-a)
    result=[]
    for point in points:
        px,py,pz=point
        if plane is not None and abs(plane[2])>1e-8:pz=highest-(plane[0]*(px-x)+plane[1]*(py-y))/plane[2]+.001
        result.append([px,py,pz])
    m.face(result,cell,np.mean(result,axis=0)-[0,0,.03])

def painted_eye(m,centre,size=.025):
    x,y,z=centre;side=1 if x>=0 else -1;right=np.array([.78,0,-side*.62]);up=np.array([0,1,0]);c=np.array(centre)
    surface_patch(m,[c+right*size*math.cos(a)+up*size*math.sin(a) for a in np.arange(6)*math.pi/3],'eye')
    s=size*.56
    surface_patch(m,[c-right*s-up*s,c+right*s-up*s,c+right*s+up*s,c-right*s+up*s],'ink')
    surface_patch(m,[c-right*s*.4+up*s*.6,c+up*s*.6,c-right*s*.4+up*s*.15],'eye')


def cleanup(nodes):
    for name,node in nodes.items():
        # Independent animated head never occludes a body/limb, and vice versa.
        node['cleanup']={'removed':remove_internal_faces(node)}
    return nodes

def animal_checks(asset,report,body,head,pivot,budget,angles):
    nodes=asset.build();report(all(nd.get('smooth') for nd in nodes.values()),'All organic nodes smooth shaded')
    from .mesh import tri_count
    report(sum(tri_count(v) for v in nodes.values())<=budget,'Animal triangle budget',str(sum(tri_count(v) for v in nodes.values())))
    report(nodes[head]['parent']==body and np.allclose(nodes[head]['pivot'],pivot),'Exact game head parent and pivot')
    bt,_=rig.posed_triangles({body:nodes[body]},{});gaps=[];ground=[]
    for a in angles:
        ht,_=rig.posed_triangles({head:nodes[head]},{head:[math.degrees(a),0,0]})
        root=ht[np.min(np.linalg.norm(ht-np.asarray(pivot),axis=2),axis=1)<.19]
        if not len(root) or not glb.intersect(bt,root):gaps.append(round(float(a),3))
        if ht[:,:,1].min()<-.005:ground.append(round(float(a),3))
    report(not gaps,'Animated head stays attached through the full game range',str(gaps))
    report(not ground,'Head stays above ground through the full game range',str(ground))