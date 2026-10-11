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
    m=box((0,.5,0),(.4,.5,.3))
    return {'Crate':node(m),'socket_top':node(Mesh(),'Crate',(0,1,0))}
