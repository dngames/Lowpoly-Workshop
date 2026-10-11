import numpy as np
from lowpoly_workshop.kit.mesh import Mesh,hexa,tube,loft,triangles,X,Y,Z
from lowpoly_workshop.kit.atlas import Atlas
ATLAS=Atlas({'body':('#609776','R'),'trim':('#ead8ad','G'),'dark':('#354353',None),'skin':('#d8a879',None)})
def params(variant=None,overrides=None):return dict(overrides or {})
def node(m,parent=None,pivot=(0,0,0),**kw):
    return dict(parent=parent,pivot=np.array(pivot,float),faces=m.faces,**kw)
def box(c,h,cell='body'):
    m=Mesh();hexa(m,np.array(c,float),[X,Y,Z],h,cell);return m

from lowpoly_workshop.surface import wrapped_patch,attachment_frame

def build(p):
    # Closed octagonal head proxy, and a fringe that wraps around its front and temples.
    host=Mesh();tube(host,np.array([0,0,0.]),np.array([0,.7,0.]),.3,n=12,cell='skin',caps=(True,True),up=Z)
    t=triangles({'Host':node(host)})[0]
    angles=np.linspace(-80,80,9)*np.pi/180
    rows=np.array([[[.6*np.sin(a),y,.6*np.cos(a)] for a in angles] for y in (.48,.62)])
    directions=np.array([[[-np.sin(a),0,-np.cos(a)] for a in angles] for y in (.48,.62)])
    hair=Mesh();wrapped_patch(hair,rows,directions,t,'dark',offset=.018,thickness=.012)
    normal=np.array([.65,.35,.68]);frame=attachment_frame(normal)
    ear=Mesh();hexa(ear,np.array([.20,.65,.20]),list(frame.T),(.045,.12,.035),'trim')
    return {'Host':node(host),'Wrap':node(hair,'Host'),'Accessory':node(ear,'Host',(.20,.65,.20),rot=frame)}
