import numpy as np
from lowpoly_workshop.kit.mesh import Mesh,hexa,tube,loft,triangles,X,Y,Z
from lowpoly_workshop.kit.atlas import Atlas
ATLAS=Atlas({'body':('#609776','R'),'trim':('#ead8ad','G'),'dark':('#354353',None),'skin':('#d8a879',None)})
def params(variant=None,overrides=None):return dict(overrides or {})
def node(m,parent=None,pivot=(0,0,0),**kw):
    return dict(parent=parent,pivot=np.array(pivot,float),faces=m.faces,**kw)
def box(c,h,cell='body'):
    m=Mesh();hexa(m,np.array(c,float),[X,Y,Z],h,cell);return m

def build(p):
    # One watertight solid wall/floor shell, with an intentionally open mouth.
    m=Mesh()
    def ring(w,y):return np.array([[-w,y,-w],[w,y,-w],[w,y,w],[-w,y,w]])
    bottom,outer,inner,floor=ring(.45,0),ring(.45,.8),ring(.38,.8),ring(.38,.08)
    # Outer winding is corrected against a point inside the shell volume.
    for i in range(4):
        j=(i+1)%4
        m.face([bottom[i],bottom[j],outer[j],outer[i]],'body',(0,.4,0))
        # Cavity faces point inward, toward empty space.
        pts=np.array([floor[i],floor[j],inner[j],inner[i]])
        centre=pts.mean(0);inside=centre+np.array([centre[0],0,centre[2]])*.1
        m.face(pts,'trim',inside)
        m.face([outer[i],outer[j],inner[j],inner[i]],'trim',(0,.7,0))
    m.face(bottom,'body',(0,.1,0));m.face(floor,'trim',(0,0,0))
    return {'Container':node(m)}
