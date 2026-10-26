"""Original trail-guide tutorial: metres, Y up, front +Z; rigid-node greeting."""
import math
import numpy as np
from lowpoly_workshop.kit.mesh import Mesh, loft, hexa, X, Y, Z, scaled, tri_count
from lowpoly_workshop.kit.organic import closed_limb
from lowpoly_workshop.kit.animal import surface_patch
from lowpoly_workshop.kit.atlas import Atlas

ATLAS = Atlas({'jacket': ('#477D70','R'), 'lining': ('#E8D8AB','G'),
               'trousers': ('#3B4F65',None), 'boots': ('#76513D',None),
               'skin': ('#DDA678',None), 'ink': ('#352F32',None),
               'cheek': ('#CF806B',None), 'pack': ('#B8824D',None)})


def params(variant=None, overrides=None):
    p = {'height': 1.72, 'body_width': .46, 'pack_depth': .16}
    p.update(overrides or {})
    if not .8 <= p['height'] <= 2.4 or not .36 <= p['body_width'] <= .60 or not .10 <= p['pack_depth'] <= .24:
        raise ValueError('Use height .8..2.4m, body_width .36...60m, pack_depth .10...24m')
    return p


def node(mesh, parent=None, pivot=(0,0,0), smooth=True):
    return {'faces':mesh.faces, 'parent':parent, 'pivot':np.array(pivot,float), 'smooth':smooth}


def rings(mesh, stations, cell, n=12):
    rows = [np.array([[x+rx*math.sin(t),y,z+rz*math.cos(t)]
                     for t in (np.arange(n)+.5)*math.tau/n]) for x,y,z,rx,rz in stations]
    loft(mesh,rows,cell,caps=(True,True))


def rounded(mesh, centre, radius, cell, n=12):
    x,y,z=centre;rx,ry,rz=radius
    rings(mesh,[(x,y+ry*h,z,rx*w,rz*w) for h,w in
               [(-.95,.25),(-.6,.78),(0,1),(.6,.78),(.95,.25)]],cell,n)


def box(mesh, centre, half, cell):
    hexa(mesh,np.array(centre,float),[X,Y,Z],np.array(half,float),cell)


def build(p):
    body=Mesh();w=p['body_width']/2
    rings(body,[(0,.62,0,w*.82,.13),(0,.75,0,w*.96,.15),
                (0,1.06,0,w,.145),(0,1.15,0,w*.76,.12)],'jacket')
    rounded(body,(0,.67,0),(.19,.13,.13),'trousers')
    # The backpack and badge overlap their host; neither floats off the jacket.
    box(body,(0,.93,-.15-p['pack_depth']*.35),(.16,.22,p['pack_depth']/2),'pack')
    box(body,(.10,1.02,.132),(.035,.045,.015),'lining')
    head=Mesh();rounded(head,(0,1.38,0),(.235,.24,.21),'skin',n=14)
    closed_limb(head,[[0,1.095,0],[0,1.28,0]],[.075,.075],n=8,cells='skin')
    rounded(head,(0,1.59,-.015),(.245,.12,.215),'jacket')
    box(head,(0,1.575,.12),(.245,.025,.20),'jacket')
    paint=Mesh()
    def feature(points,cell):
        host=Mesh();host.faces=list(head.faces)+list(paint.faces)
        surface_patch(host,points,cell)
        q,c,u,_=host.faces[-1];paint.faces.append((q,c,u,True))
    for sign in [-1,1]:
        x=sign*.078
        feature([[x-.016,1.39,.3],[x+.016,1.39,.3],[x+.016,1.426,.3],[x-.016,1.426,.3]],'ink')
        feature([[x-.007,1.414,.3],[x+.002,1.414,.3],[x-.007,1.422,.3]],'lining')
        x=sign*.13
        feature([[x-.020,1.345,.3],[x+.020,1.345,.3],[x+.020,1.361,.3],[x-.020,1.361,.3]],'cheek')
    feature([[-.045,1.329,.3],[0,1.312,.3],[0,1.321,.3],[-.04,1.338,.3]],'ink')
    feature([[0,1.312,.3],[.045,1.329,.3],[.04,1.338,.3],[0,1.321,.3]],'ink')
    result={'Body':node(body,smooth=True), 'Head':node(head,'Body',(0,1.12,0)),
            'FacePaint':node(paint,'Head',(0,1.12,0),smooth=False)}
    for side,sign in [('L',1),('R',-1)]:
        shoulder=[sign*(w-.04),1.06,0];elbow=[sign*.30,.84,.02]
        upper=Mesh();closed_limb(upper,[shoulder,[elbow[0],.81,.02]],[.085,.068],n=8,cells='jacket')
        lower=Mesh();closed_limb(lower,[[elbow[0],.865,.02],[sign*.32,.75,.03],[sign*.33,.61,.04]],
                                [.069,.059,.044],n=8,cells=['jacket','skin'])
        rounded(lower,(sign*.33,.58,.04),(.057,.075,.052),'skin',n=8)
        hip=[sign*.105,.68,0];leg=Mesh()
        closed_limb(leg,[hip,[sign*.12,.37,.005],[sign*.12,.10,.02]],[.092,.072,.053],n=8,cells='trousers')
        shoe=Mesh();rings(shoe,[(sign*.12,0,.055,.10,.155),(sign*.12,.09,.055,.10,.155),
                               (sign*.12,.145,.03,.07,.11)],'boots',n=8)
        result['Upper'+side]=node(upper,'Body',shoulder)
        result['Lower'+side]=node(lower,'Upper'+side,elbow)
        result['Leg'+side]=node(leg,'Body',hip)
        result['Shoe'+side]=node(shoe,'Leg'+side,(sign*.12,.10,.02))
    highest=max(float(q[:,1].max()) for nd in result.values() for q,*_ in nd['faces'])
    return scaled(result,p['height']/highest)


def wave(angle=-130):
    return {'UpperR':[0,0,angle], 'LowerR':[0,0,-10], 'Head':[0,-8,0]}


def clips(nodes,p):
    return {'Greeting':{'fps':24,'frames':[wave(-125+5*math.sin(t)) for t in np.linspace(0,math.tau,49)]}}


def extra_checks(asset,report):
    nodes=asset.build();total=sum(tri_count(nd) for nd in nodes.values())
    report(total<=3000,'Tutorial total triangle budget',str(total))
    points=np.concatenate([q for nd in nodes.values() for q,*_ in nd['faces']])
    report(abs(points[:,1].min())<1e-6,'Tutorial soles at ground zero')
    report(abs(points[:,1].max()-asset.params()['height'])<1e-6,'Tutorial height parameter matches geometry')
    # Each closed node has several overlapping solids; whole-node topology is checked on export.
    report(all(np.isfinite(q).all() for nd in nodes.values() for q,*_ in nd['faces']),'Tutorial finite coordinates')
