"""Original high-poly trail-guide tutorial: metres, Y up, front +Z; rigid-node greeting."""
import math
import numpy as np
from lowpoly_workshop.kit.mesh import Mesh, loft, hexa, X, Y, Z, scaled, tri_count
from lowpoly_workshop.kit.organic import closed_limb
from lowpoly_workshop.kit.animal import surface_patch
from lowpoly_workshop.kit.atlas import Atlas

ATLAS = Atlas({'jacket': ('#477D70','R'), 'lining': ('#E8D8AB','G'),
               'trousers': ('#3B4F65',None), 'boots': ('#76513D',None),
               'skin': ('#DDA678',None), 'ink': ('#352F32',None),
               'cheek': ('#CF806B',None), 'pack': ('#B8824D',None), 'sole': ('#403B39',None)})


def params(variant=None, overrides=None):
    p = {'height': 1.72, 'body_width': .46, 'pack_depth': .16}
    p.update(overrides or {})
    if not .8 <= p['height'] <= 2.4 or not .36 <= p['body_width'] <= .60 or not .10 <= p['pack_depth'] <= .24:
        raise ValueError('Use height .8..2.4m, body_width .36...60m, pack_depth .10...24m')
    return p


def node(mesh, parent=None, pivot=(0,0,0), smooth=True):
    return {'faces':mesh.faces, 'parent':parent, 'pivot':np.array(pivot,float), 'smooth':smooth}


def rings(mesh, stations, cell, n=32):
    rows = [np.array([[x+rx*math.sin(t),y,z+rz*math.cos(t)]
                     for t in (np.arange(n)+.5)*math.tau/n]) for x,y,z,rx,rz in stations]
    loft(mesh,rows,cell,caps=(True,True))


def rounded(mesh, centre, radius, cell, n=32):
    x,y,z=centre;rx,ry,rz=radius
    rings(mesh,[(x,y+ry*h,z,rx*w,rz*w) for h,w in
               [(math.sin(t),math.cos(t)) for t in np.linspace(-1.50,1.50,21)]],cell,n)


def box(mesh, centre, half, cell):
    hexa(mesh,np.array(centre,float),[X,Y,Z],np.array(half,float),cell)


def build(p):
    body=Mesh();w=p['body_width']/2
    rings(body,[(0,.62,0,w*.82,.13),(0,.75,0,w*.96,.15),
                (0,1.06,0,w,.145),(0,1.15,0,w*.76,.12)],'jacket')
    rounded(body,(0,.67,0),(.19,.13,.13),'trousers')
    # The backpack and badge overlap their host; neither floats off the jacket.
    rounded(body,(0,.93,-.15-p['pack_depth']*.35),(.175,.24,p['pack_depth']/2),'pack')
    rounded(body,(0,.86,-.15-p['pack_depth']*.85),(.13,.12,.035),'pack')
    for sign in [-1,1]:
        closed_limb(body,[[sign*.145,.78,.09],[sign*.15,1.04,.09],
                          [sign*.135,1.14,.015],[sign*.13,1.10,-.17]],
                    [.018,.022,.022,.018],n=16,cells='pack')
    closed_limb(body,[[0,.74,.15],[0,1.045,.15]],[.009,.009],n=12,cells='lining')
    for y in [.80,.87,.94]:rounded(body,(.10,y,.135),(.04,.025,.025),'jacket',n=16)
    box(body,(.10,1.02,.132),(.035,.045,.015),'lining')
    head=Mesh();rounded(head,(0,1.38,0),(.235,.24,.21),'skin',n=48)
    rounded(head,(0,1.365,.195),(.038,.045,.045),'skin',n=24)
    for sign in [-1,1]:
        rounded(head,(sign*.222,1.38,0),(.04,.065,.04),'skin',n=24)
        rounded(head,(sign*.242,1.38,.012),(.019,.038,.025),'cheek',n=16)
    closed_limb(head,[[0,1.095,0],[0,1.28,0]],[.075,.075],n=24,cells='skin')
    rounded(head,(0,1.59,-.015),(.245,.12,.215),'jacket')
    rounded(head,(0,1.575,.12),(.245,.025,.20),'jacket')
    paint=Mesh()
    def feature(points,cell):
        host=Mesh();host.faces=list(head.faces)+list(paint.faces)
        surface_patch(host,points,cell)
        q,c,u,_=host.faces[-1];paint.faces.append((q,c,u,True))
    for sign in [-1,1]:
        x=sign*.078
        feature([[x-.016,1.39,.3],[x+.016,1.39,.3],[x+.016,1.426,.3],[x-.016,1.426,.3]],'ink')
        feature([[x-.007,1.414,.3],[x+.002,1.414,.3],[x-.007,1.422,.3]],'lining')
        feature([[x-.023,1.447,.3],[x+.023,1.447,.3],[x+.020,1.458,.3],[x-.023,1.458,.3]],'ink')
        x=sign*.13
        feature([[x-.020,1.345,.3],[x+.020,1.345,.3],[x+.020,1.361,.3],[x-.020,1.361,.3]],'cheek')
    feature([[-.045,1.329,.3],[0,1.312,.3],[0,1.321,.3],[-.04,1.338,.3]],'ink')
    feature([[0,1.312,.3],[.045,1.329,.3],[.04,1.338,.3],[0,1.321,.3]],'ink')
    result={'Body':node(body,smooth=True), 'Head':node(head,'Body',(0,1.12,0)),
            'FacePaint':node(paint,'Head',(0,1.12,0),smooth=False)}
    for side,sign in [('L',1),('R',-1)]:
        shoulder=[sign*(w-.04),1.06,0];elbow=[sign*.30,.84,.02]
        upper=Mesh();closed_limb(upper,[shoulder,[elbow[0],.81,.02]],[.085,.068],n=24,cells='jacket')
        lower=Mesh();closed_limb(lower,[[elbow[0],.865,.02],[sign*.32,.75,.03],[sign*.33,.61,.04]],
                                [.069,.059,.044],n=24,cells=['jacket','skin'])
        rounded(lower,(sign*.33,.58,.04),(.057,.075,.052),'skin',n=24)
        rounded(lower,(sign*.289,.60,.066),(.030,.042,.029),'skin',n=20)
        closed_limb(lower,[[elbow[0],.86,.02],[sign*.305,.823,.022]], [.071,.068],n=24,cells='lining')
        hip=[sign*.105,.68,0];leg=Mesh()
        closed_limb(leg,[hip,[sign*.12,.37,.005],[sign*.12,.10,.02]],[.092,.072,.053],n=24,cells='trousers')
        shoe=Mesh();rings(shoe,[(sign*.12,.025,.055,.10,.155),(sign*.12,.09,.055,.10,.155),
                               (sign*.12,.145,.03,.07,.11)],'boots',n=24)
        rings(shoe,[(sign*.12,0,.055,.101,.156),(sign*.12,.035,.055,.102,.157),
                     (sign*.12,.045,.055,.099,.154)],'sole',n=32)
        for y,z in [(.095,.15),(.108,.12),(.12,.09)]:
            closed_limb(shoe,[[sign*.12-.045,y,z],[sign*.12+.045,y,z]],[.005,.005],n=8,cells='lining')
        result['Upper'+side]=node(upper,'Body',shoulder)
        result['Lower'+side]=node(lower,'Upper'+side,elbow)
        result['Leg'+side]=node(leg,'Body',hip)
        result['Shoe'+side]=node(shoe,'Leg'+side,(sign*.12,.10,.02))
    highest=max(float(q[:,1].max()) for nd in result.values() for q,*_ in nd['faces'])
    return scaled(result,p['height']/highest)


def wave(angle=-115):
    return {'UpperR':[0,0,angle], 'LowerR':[0,0,-10], 'Head':[0,-8,0]}


def clips(nodes,p):
    return {'Greeting':{'fps':24,'frames':[wave(-110+5*math.sin(t)) for t in np.linspace(0,math.tau,49)]}}


def extra_checks(asset,report):
    nodes=asset.build();total=sum(tri_count(nd) for nd in nodes.values())
    report(total<=40000,'Tutorial total triangle budget',str(total))
    points=np.concatenate([q for nd in nodes.values() for q,*_ in nd['faces']])
    report(abs(points[:,1].min())<1e-6,'Tutorial soles at ground zero')
    report(abs(points[:,1].max()-asset.params()['height'])<1e-6,'Tutorial height parameter matches geometry')
    # Each closed node has several overlapping solids; whole-node topology is checked on export.
    report(all(np.isfinite(q).all() for nd in nodes.values() for q,*_ in nd['faces']),'Tutorial finite coordinates')
