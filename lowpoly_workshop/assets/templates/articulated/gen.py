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
    base=box((0,.18,0),(.5,.18,.3))
    arm=Mesh();tube(arm,np.array([0,.45,0.]),np.array([0,1.2,0.]),.09,n=8,cell='trim',caps=(True,True))
    return {'Base':node(base),'Arm':node(arm,'Base',(0,.45,0)), 'socket_tip':node(Mesh(),'Arm',(0,1.2,0))}
def clips(nodes,p):
    return {'Swing':{'fps':24,'frames':[{'Arm':[0,0,a]} for a in (0,30,60,30,0)]}}
