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
    body=box((0,.95,0),(.24,.3,.14));head=box((0,1.4,0),(.17,.18,.16),'skin')
    result={'Body':node(body,None,(0,.8,0)),'Head':node(head,'Body',(0,1.25,0))}
    for side,x in (('L',.32),('R',-.32)):
        upper=Mesh();tube(upper,np.array([x,1.1,0]),np.array([x,.78,0]),.105,n=8,cell='body',caps=(True,True))
        lower=Mesh();tube(lower,np.array([x,.85,0]),np.array([x,.52,0]),.09,n=8,cell='skin',caps=(True,True))
        leg=box((x*.48,.34,0),(.105,.34,.11),'dark');shoe=box((x*.48,.07,.05),(.12,.07,.18),'trim')
        result['Upper'+side]=node(upper,'Body',(x,1.1,0))
        result['Lower'+side]=node(lower,'Upper'+side,(x,.82,0))
        result['Leg'+side]=node(leg,'Body',(x*.48,.65,0))
        result['Shoe'+side]=node(shoe,'Leg'+side,(x*.48,.12,0))
    return result

def skin(nodes,p):
    bones=[dict(name='root',parent=None,head=[0,.8,0],tail=[0,1.2,0]),dict(name='head',parent='root',head=[0,1.25,0],tail=[0,1.55,0])]
    bind={'Body':['root'],'Head':['head']}
    for side,x in (('L',.32),('R',-.32)):
        bones.extend([dict(name='upper'+side,parent='root',head=[x,1.1,0],tail=[x,.82,0]),dict(name='lower'+side,parent='upper'+side,head=[x,.82,0],tail=[x,.52,0]),dict(name='leg'+side,parent='root',head=[x*.48,.65,0],tail=[x*.48,.12,0])])
        bind.update({'Upper'+side:['upper'+side,'lower'+side],'Lower'+side:['upper'+side,'lower'+side],'Leg'+side:['leg'+side],'Shoe'+side:['leg'+side]})
    return dict(bones=bones,bind=bind,rigid={},sigma=.075)
