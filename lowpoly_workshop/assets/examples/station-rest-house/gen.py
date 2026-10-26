"""Tiny Tour Station Rest House, adapted for standalone Workshop; see provenance.json."""
from pathlib import Path
import json,math
import numpy as np
HERE=Path(__file__).resolve().parent
from lowpoly_workshop.kit.mesh import Mesh,hexa,tube,tri_count
from lowpoly_workshop.kit.atlas import Atlas
from lowpoly_workshop.kit.organic import closed_surface
from lowpoly_workshop.kit.character_cleanup import remove_internal_faces
CFG=json.loads((HERE/'inputs/construction.json').read_text());SHELLS={};FEATURES={}
COLORS={'wood':'#A9744B','dark':'#4A3F3A','roof':'#5B6B7E','rooflight':'#6B7A88','clay':'#C3664D','stone':'#8E97A0','lightstone':'#BDB3A3','plaster':'#F4E7D0','glass':'#625B51','concrete':'#C9C4BA','booth':'#E6E2DA','blue':'#586C8E','plum':'#8E4F8F','teal':'#2BA59B','straw':'#C9A35E'}
ATLAS=Atlas({k:(v,None) for k,v in COLORS.items()})
def params(variant=None,overrides=None):
 p={'lod':int(variant or 0)};p.update(overrides or {})
 if isinstance(p['lod'],bool) or p['lod'] not in range(4):raise ValueError('lod must be an integer 0..3')
 return p

def build(p):
 lod=p['lod'];m=Mesh();nodes={};solids=[];features={};kind=CFG['kind'];root=CFG['model']+('_far' if lod==3 else '_LOD'+str(lod))
 def solid(name,fn):
  start=len(m.faces);fn();fs=m.faces[start:];solids.append((name,list(fs)));features[name]=list(fs)
 def box(name,c,half,cell,cells=None):solid(name,lambda:hexa(m,c,np.eye(3),half,cell,cells=cells or {}))
 def beam(name,a,b,width,cell='wood'):
  a,b=np.array(a,float),np.array(b,float);solid(name,lambda:tube(m,a,b,width,n=4,cell=cell,caps=(True,True),up=np.array([0,0,1]) if abs((b-a)[2])<abs((b-a)[0]) else np.array([1,0,0]),phase=.125))
 def roof(name,w,d,eave,ridge,hip=True,z=0,cell='roof'):
  A=np.array([[-w/2,eave-.12,-d/2+z],[w/2,eave-.12,-d/2+z],[w/2,eave-.12,d/2+z],[-w/2,eave-.12,d/2+z]]);B=A+[0,.12,0];r=max(0,w/2-(d/2 if hip else 0));L=np.array([-r,ridge,z]);R=np.array([r,ridge,z]);inside=np.array([0,eave,z])
  def add():
   m.face(A,cell,inside)
   for i in range(4):j=(i+1)%4;m.face([A[i],A[j],B[j],B[i]],cell,inside)
   for i,j,T,U in [(0,1,R,L),(2,3,L,R)]:m.face([B[i],B[j],T] if r<1e-6 else [B[i],B[j],T,U],cell,inside)
   m.face([B[3],B[0],L],cell,inside);m.face([B[1],B[2],R],cell,inside)
  solid(name,add)
  if lod==0:
   beam(name+'_ridge',[-r-.15,ridge,z],[r+.15,ridge,z],.12,'rooflight' if cell=='roof' else 'dark')
 def window(name,face,s,y,w,h,wall,door=False):
  # Closed, shallow facade blocks keep every aperture in the same position at all levels.
  normal=np.array([0,0,1 if face=='front' else -1]) if face in ['front','back'] else np.array([1 if face=='left' else -1,0,0]);u=np.array([1,0,0]) if face in ['front','back'] else np.array([0,0,1]);c=u*s+np.array([0,y,0])+normal*(wall+.035)
  if lod<2:
   solid(name+'_frame',lambda:hexa(m,c,np.array([u,[0,1,0],normal]),[w/2+.09,h/2+.09,.065],'wood'))
  if lod<2:solid(name,lambda:hexa(m,c+normal*.075,np.array([u,[0,1,0],normal]),[w/2,h/2,.025],'glass'))
  else:
   cc=c+normal*.075;v=np.array([0,h/2,0]);uu=u*w/2;m.face([cc-uu-v,cc+uu-v,cc+uu+v,cc-uu+v],'glass',cc-normal);features[name]=[m.faces[-1]]
  if lod==0:
   for k in ([0] if not door else [-w/4,0,w/4]):solid(name+'_bar'+str(k),lambda k=k:hexa(m,c+normal*.11+u*k,np.array([u,[0,1,0],normal]),[.035,h/2+.025,.035],'wood'))
 def bench(name,x,y,z,width=2):
  box(name+'_seat',[x,y+.43,z],[width/2,.065,.26],'wood')
  box(name+'_back',[x,y+.83,z-.22],[width/2,.16,.065],'wood')
  for a in [-width*.36,width*.36]:box(name+'_leg'+str(a),[x+a,y+.24,z],[.075,.24,.23],'wood')
 if lod==3:roof('far_roof',15.5,10.5,6.15,8,True);box('far_walls',[0,3.0,0],[7,3,4.5],'plaster')
 else:
  box('stone_skirting',[0,.48,0],[7,.48,4.5],'stone');box('ground_floor',[0,2.03,0],[7,1.07,4.5],'dark');box('upper_floor',[0,4.6,0],[7,1.5,4.5],'plaster')
  roof('main_roof',15.5,10.5,6.18,8,True)
  # Front gable into the hipped roof: a sealed small gable at the same ridge height.
  # Its rear sits within the roof rather than creating an open join.
  G=np.array([[-2.8,6.17,5.27],[2.8,6.17,5.27],[0,7.90,5.27]]);inside=np.array([0,6.6,4.8])
  def front_gable():
   B=G-[0,0,5.27];m.face(G,'dark',inside);m.face(B,'dark',inside)
   for i in range(3):j=(i+1)%3;m.face([G[i],G[j],B[j],B[i]],'roof',inside)
  solid('front_gable',front_gable)
  box('terrace',[0,.13,5.25],[7.7,.13,1.1],'wood')
  # Closed sloping canopy and four anchored supports.
  A=np.array([[-7.7,3.45,4.4],[7.7,3.45,4.4],[7.7,2.95,6.45],[-7.7,2.95,6.45]]);B=A-[0,.16,0]
  def canopy():
   centre=np.mean(np.r_[A,B],axis=0);m.face(A,'roof',centre);m.face(B,'roof',centre)
   for i in range(4):j=(i+1)%4;m.face([A[i],A[j],B[j],B[i]],'roof',centre)
  solid('terrace_roof',canopy)
  for x in [-7.1,-2.4,2.4,7.1]:box('terrace_post'+str(x),[x,3.01975609756/2,6.0],[.12,3.01975609756/2,.12],'wood')
  for x in [-4.6,0,4.6]:
   if lod<2:bench('bench'+str(x),x,.26,5.7)
   else:box('bench_proxy'+str(x),[x,.73,5.7],[1,.40,.27],'wood')
  for face in ['front','back']:
   for i,x in enumerate([-4.8,-1.65,1.65,4.8]):window(face+str(i),face,x,4.75,1.30,1.35,4.5)
  window('entrance','front',0,1.7,3.3,2.3,4.5,True)
  for face in ['left','right']:window(face,face,0,4.75,1.3,1.35,7)
  box('chimney',[4.5,6.9,-2.3],[.40,1.0,.40],'stone');box('chimney_cap',[4.5,7.94,-2.3],[.5,.06,.5],'clay')
 # Parent inserted first; named text boards follow it with their original pivots.
 main={'parent':None,'pivot':np.zeros(3),'faces':m.faces,'smooth':False};main['hidden_triangles_removed']=remove_internal_faces(main)
 nodes={root:main,**nodes};SHELLS[lod]=solids;FEATURES[lod]=features
 return nodes

def extra_checks(asset,report):
 for lod,budget in enumerate(CFG['budgets']):
  ns=asset.build(str(lod));total=sum(tri_count(nd) for nd in ns.values())
  report(total<=budget,f'LOD{lod} source triangle budget',str(total))
  report(all(closed_surface(f) for _,f in SHELLS[lod]),f'LOD{lod} structural primitives closed before hidden-face removal')
  if lod<3:
   features=FEATURES[lod]
   report(sum(k.startswith('terrace_post') for k in features)==4,f'LOD{lod} four canopy supports')
   report(sum(k.startswith('bench') and k.endswith('_seat') for k in features)==3 if lod<2 else sum(k.startswith('bench_proxy') for k in features)==3,f'LOD{lod} three terrace benches')
   report(all(name in features for name in ['main_roof','front_gable','terrace_roof','entrance','chimney']),f'LOD{lod} architectural landmarks retained')

