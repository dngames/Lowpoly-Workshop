"""Textured Station Rest House remodel. Metres, +Y up, +Z street; see provenance.json."""
from pathlib import Path
import sys,json,math
import numpy as np
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from lowpoly_workshop.kit.mesh import Mesh,hexa,tube,loft,tri_count
from lowpoly_workshop.kit.organic import closed_surface,surface_orientation
from station_materials import ATLAS,COLORS
CFG=json.loads((HERE/'inputs/construction.json').read_text());SHELLS={};FEATURES={}
W,D,EAVE,RIDGE=14.,9.,6.18,8.

def params(variant=None,overrides=None):
 p={'lod':int(variant or 0)};p.update(overrides or {})
 if isinstance(p['lod'],bool) or p['lod'] not in range(4):raise ValueError('lod must be an integer 0..3')
 return p

def build(p):
 lod=p['lod'];m=Mesh();solids=[];features={}
 def part(name,fn):
  start=len(m.faces);fn();f=list(m.faces[start:]);solids.append((name,f));features[name]=f
 def box(name,c,h,cell='wood',axes=None,bevel=0):
  c=np.asarray(c,float);h=np.asarray(h,float);axes=np.eye(3) if axes is None else np.asarray(axes,float)
  def make():
   if bevel<=0:hexa(m,c,axes,h,cell);return
   b=min(bevel,float(h.min())*.4)
   def ring(y,w,d,cut):
    return np.array([c+x*axes[0]+y*axes[1]+z*axes[2] for x,z in
      [(-w+cut,-d),(w-cut,-d),(w,-d+cut),(w,d-cut),(w-cut,d),(-w+cut,d),(-w,d-cut),(-w,-d+cut)]])
   loft(m,[ring(-h[1],h[0]-b,h[2]-b,b*.4),ring(-h[1]+b,h[0],h[2],b),
           ring(h[1]-b,h[0],h[2],b),ring(h[1],h[0]-b,h[2]-b,b*.4)],cell)
  part(name,make)
 def beam(name,a,b,r,cell='wood',n=4):
  a,b=np.array(a,float),np.array(b,float)
  part(name,lambda:tube(m,a,b,r,n=n,cell=cell,caps=(True,True),up=np.array([0,0,1]) if abs((b-a)[2])<abs((b-a)[0]) else np.array([1,0,0]),phase=.125))
 def roof(name,w,d,eave,ridge,hip=True,z=0):
  A=np.array([[-w/2,eave-.16,-d/2+z],[w/2,eave-.16,-d/2+z],[w/2,eave-.16,d/2+z],[-w/2,eave-.16,d/2+z]])
  B=A+[0,.16,0];r=max(.001,w/2-(d/2 if hip else 0));L=np.array([-r,ridge,z]);R=np.array([r,ridge,z]);inside=np.array([0,eave,z])
  def make():
   m.face(A,'roof',inside)
   for i in range(4):j=(i+1)%4;m.face([A[i],A[j],B[j],B[i]],'roof',inside)
   for i,j,T,U in [(0,1,R,L),(2,3,L,R)]:m.face([B[i],B[j],T,U],'roof',inside)
   m.face([B[3],B[0],L],'roof',inside);m.face([B[1],B[2],R],'roof',inside)
  part(name,make)
 def tile(name,centre,across,down,width,length,height_fn,cell='tile',sections=4):
  c=np.asarray(centre,float);a=np.asarray(across,float);v=np.asarray(down,float)
  rows=[]
  for t in [-.5,.5]:
   row=[]
   for u in np.linspace(-.5,.5,sections+1):
    q=c+a*u*width+v*t*length;q[1]=height_fn(q)+.035+.065*(1-(2*u)**2)
    row.append(q)
   rows.append(np.array(row))
  A,B=rows;C=A-[0,.075,0];F=B-[0,.075,0];inside=np.r_[A,B,C,F].mean(0)
  def make():
   # A curved band's centroid can lie outside its thin volume. Orient against
   # local outward directions, never a single guessed interior point.
   def face(q,outward):
    m.face(q,cell,np.asarray(q).mean(0)-np.asarray(outward)*.01)
   for i in range(sections):
    j=i+1;face([A[i],A[j],B[j],B[i]],[0,1,0]);face([C[i],F[i],F[j],C[j]],[0,-1,0])
   face([A[0],B[0],F[0],C[0]],-a);face([A[-1],C[-1],F[-1],B[-1]],a)
   face([*A,*C[::-1]],-v);face([*B,*F[::-1]],v)
  part(name,make)
 def window(name,face,s,y,w,h,wall,door=False):
  normal=np.array([0,0,1 if face=='front' else -1]) if face in ['front','back'] else np.array([1 if face=='left' else -1,0,0]);u=np.array([1,0,0]) if face in ['front','back'] else np.array([0,0,1]);up=np.array([0,1,0]);c=u*s+up*y+normal*wall
  box(name,c+normal*.055,[w/2,h/2,.035],'glass',[u,up,normal])
  if lod<3:
   for sign in [-1,1]:
    box(name+'_jamb'+str(sign),c+u*sign*(w/2+.07)+normal*.12,[.085,h/2+.16,.12],'wood',[u,up,normal],.025 if lod==0 else 0)
    box(name+'_lintel'+str(sign),c+up*sign*(h/2+.08)+normal*.14,[w/2+.18,.09,.14],'wood',[u,up,normal],.03 if lod==0 else 0)
   if lod<2:
    for a in ([-w/4,0,w/4] if door else [0]):box(name+'_mullion'+str(a),c+u*a+normal*.10,[.034,h/2,.045],'wood',[u,up,normal])
    for yy in ([-h/6,h/6] if door else [0]):box(name+'_cross'+str(yy),c+up*yy+normal*.105,[w/2,.03,.05],'wood',[u,up,normal])
   if lod==0:box(name+'_sill',c-up*(h/2+.17)+normal*.15,[w/2+.21,.065,.22],'wood',[u,up,normal],.025)
 def bench(name,x):
  if lod==2:box(name+'_proxy',[x,.665,5.7],[1,.405,.27]);return
  for i in range(3):box(name+'_seat'+str(i),[x,.70,5.52+i*.18],[1,.065,.078],bevel=.025 if lod==0 else 0)
  for i in range(2):box(name+'_back'+str(i),[x,1.0+i*.19,5.45],[1,.065,.065],bevel=.02 if lod==0 else 0)
  for side in [-1,1]:
   box(name+'_leg'+str(side),[x+side*.72,.48,5.7],[.075,.22,.23])
   beam(name+'_upright'+str(side),[x+side*.72,.52,5.46],[x+side*.72,1.22,5.46],.055)
 if lod==3:
  roof('far_roof',15.5,10.5,EAVE,RIDGE);box('far_walls',[0,3,0],[7,3,4.5],'plaster')
 else:
  box('stone_skirting',[0,.48,0],[7,.48,4.5],'stone')
  box('ground_floor',[0,2.03,0],[7,1.07,4.5],'dark')
  box('upper_floor',[0,4.6,0],[7,1.5,4.5],'plaster')
  roof('main_roof',15.5,10.5,EAVE,RIDGE)
  G=np.array([[-2.8,6.17,5.27],[2.8,6.17,5.27],[0,7.90,5.27]]);inside=np.array([0,6.6,4.8])
  def gable():
   B=G-[0,0,5.27];m.face(G,'dark',inside);m.face(B,'dark',inside)
   for i in range(3):j=(i+1)%3;m.face([G[i],G[j],B[j],B[i]],'roof' if i else 'dark',inside)
  part('front_gable',gable)
  box('terrace',[0,.13,5.25],[7.7,.13,1.1],'dark')
  A=np.array([[-7.7,3.45,4.4],[7.7,3.45,4.4],[7.7,2.95,6.45],[-7.7,2.95,6.45]]);B=A-[0,.16,0]
  def canopy():
   centre=np.r_[A,B].mean(0);m.face(A,'roof',centre);m.face(B,'roof',centre)
   for i in range(4):j=(i+1)%4;m.face([A[i],A[j],B[j],B[i]],'roof',centre)
  part('terrace_roof',canopy)
  for x in [-7.1,-2.4,2.4,7.1]:box('terrace_post'+str(x),[x,3.01975609756/2,6.0],[.12,3.01975609756/2,.12],bevel=.035 if lod==0 else 0)
  for i,x in enumerate([-4.6,0,4.6]):bench('bench'+str(i),x)
  for face in ['front','back']:
   for i,x in enumerate([-4.8,-1.65,1.65,4.8]):window(face+str(i),face,x,4.75,1.3,1.35,4.5)
  window('entrance','front',0,1.7,3.3,2.3,4.5,True)
  for face in ['left','right']:window(face,face,0,4.75,1.3,1.35,7)
  for face in ['front','back','left','right']:
   n=np.array([0,0,1 if face=='front' else -1]) if face in ['front','back'] else np.array([1 if face=='left' else -1,0,0]);u=np.array([1,0,0]) if face in ['front','back'] else np.array([0,0,1]);span=14 if face in ['front','back'] else 9;wall=4.5 if face in ['front','back'] else 7;axes=[u,[0,1,0],n]
   for y in [1.0,3.15,6.05]:box('belt'+face+str(y),n*(wall+.04)+[0,y,0],[span/2+.1,.10,.11],axes=axes,bevel=.03 if lod==0 else 0)
   for j,x in enumerate(np.linspace(-span/2+.12,span/2-.12,5 if span==14 else 4)):
    box('upper_post'+face+str(j),n*(wall+.04)+u*x+[0,4.6,0],[.085,1.45,.105],axes=axes,bevel=.025 if lod==0 else 0)
   if lod<2:
    step=1.4 if lod==0 else 2.0;cols=math.ceil(span/step);rows=3 if lod==0 else 2
    for row in range(rows):
     cuts=np.linspace(-span/2,span/2,cols+1)+(step*.25 if row%2 else 0);cuts[0]=-span/2;cuts[-1]=span/2
     for j,(a,b) in enumerate(zip(cuts[:-1],cuts[1:])):
      if b-a<.12:continue
      c=n*(wall+.02)+u*(a+b)/2+[0,(row+.5)*.96/rows,0]
      box('stone_'+face+str((row,j)),c,[(b-a)/2-.018,.96/rows/2-.014,.13],'lightstone' if (row+j)%3==0 else 'stonegrain',axes,.045 if lod==0 else 0)
    for j,x in enumerate(np.linspace(-span/2+.15,span/2-.15,round(span/.35))):
     if face=='front' and abs(x)<1.85:continue
     box('board_'+face+str(j),n*(wall+.015)+u*x+[0,2.02,0],[.155,1.0,.025],'dark',axes)
   if face=='back' and lod<2:
    for j,x in enumerate([-4.8,-1.65,1.65,4.8]):window('back_lower'+str(j),face,x,1.95,1.3,1.4,4.5)
  if lod<2:
   # Timber construction reads at street distance, including eaves, gable braces and terrace brackets.
   for side in [-1,1]:
    beam('gable_barge'+str(side),[0,7.90,5.34],[side*2.9,6.11,5.34],.13,n=6)
    beam('gable_brace'+str(side),[0,6.23,5.32],[side*1.9,6.74,5.32],.075)
   beam('gable_centre',[0,6.18,5.33],[0,7.9,5.33],.10)
   for sign in [-1,1]:
    box('main_fascia'+str(sign),[0,6.13,sign*5.25],[7.76,.10,.11],bevel=.035 if lod==0 else 0)
    for j,x in enumerate(np.arange(-7.35,7.4,.66)):
     box('rafter'+str((sign,j)),[x,6.07,sign*5.04],[.065,.10,.30],bevel=.02 if lod==0 else 0)
   box('canopy_beam',[0,2.89,6.15],[7.55,.11,.13],bevel=.03 if lod==0 else 0)
   for x in [-7.1,-2.4,2.4,7.1]:
    for direction in [-1,1]:
     if abs(x+direction*.55)>7.3:continue
     beam('terrace_brace'+str((x,direction)),[x,2.35,6.0],[x+direction*.55,2.98,6.0],.065)
   # Closed curved tile strips follow each roof plane; their undersides penetrate the roof substrate.
   if lod==0:
    for sign in [-1,1]:
     for row,z in enumerate(np.arange(.44,5.2,.86)):
      span=2.5+z-.05;cols=max(1,round(2*span/.58))
      for col,x in enumerate(np.linspace(-span+.29,span-.29,cols)):
       q=[x,0,sign*z]
       if sign==1 and abs(x)<2.9 and 7.9-1.73*abs(x)/2.8>8-1.82*z/5.25-.04:continue
       tile('main_tile'+str((sign,row,col)),q,[1,0,0],[0,0,1],.57,.93,lambda p:8-1.82*abs(p[2])/5.25,'clay' if (row*17+col*7)%71==0 else 'tile')
     for row,x in enumerate(np.arange(2.95,7.65,.86)):
      span=x-2.5-.06;cols=max(1,round(2*span/.58))
      for col,z in enumerate(np.linspace(-span+.28,span-.28,cols)):
       tile('hip_tile'+str((sign,row,col)),[sign*x,0,z],[0,0,1],[1,0,0],.57,.93,lambda p:8-1.82*(abs(p[0])-2.5)/5.25)
    for sign in [-1,1]:
     for row,x in enumerate(np.arange(.38,2.8,.70)):
      for col,z in enumerate(np.arange(.5,5.3,.60)):
       if 7.9-1.73*x/2.8<8-1.82*z/5.25-.04:continue
       tile('gable_tile'+str((sign,row,col)),[sign*x,0,z],[0,0,1],[1,0,0],.59,.76,lambda p:7.9-1.73*abs(p[0])/2.8)
    for row,z in enumerate(np.arange(4.65,6.4,.53)):
     for col,x in enumerate(np.arange(-7.38,7.5,.58)):
      tile('canopy_tile'+str((row,col)),[x,0,z],[1,0,0],[0,0,1],.57,.58,lambda p:3.45-.5*(p[2]-4.4)/2.05)
   for i,x in enumerate(np.arange(-2.5,2.5,.48 if lod==0 else .95)):
    beam('ridge_cap'+str(i),[x,8.07,0],[min(x+(.52 if lod==0 else 1.0),2.6),8.07,0],.16,'rooflight',8 if lod==0 else 6)
   for i,z in enumerate(np.arange(.55,5.2,.52 if lod==0 else 1.0)):
    beam('gable_cap'+str(i),[0,7.98,z],[0,7.98,min(z+(.56 if lod==0 else 1.04),5.45)],.14,'rooflight',8 if lod==0 else 6)
  box('chimney',[4.5,6.9,-2.3],[.40,1.0,.40],'stone',bevel=.035 if lod==0 else 0)
  box('chimney_cap',[4.5,7.94,-2.3],[.5,.06,.5],'clay',bevel=.025 if lod==0 else 0)
 # Every textured face gets stable local 0..1 coordinates; vertical timber keeps vertical grain.
 for i,(q,cell,uv,thin) in enumerate(m.faces):
  span=np.ptp(q,axis=0);axes=np.argsort(span)[-2:];a,b=int(axes[0]),int(axes[1])
  if cell in ['wood','dark'] and span[1]>.001:
   b=1 if span[1]>=max(span[0],span[2])*.5 else int(np.argmax(span));a=max((j for j in range(3) if j!=b),key=lambda j:span[j])
  lo=q.min(0);uv=np.column_stack([(q[:,a]-lo[a])/max(span[a],1e-9),(q[:,b]-lo[b])/max(span[b],1e-9)])
  m.faces[i]=(q,cell,uv,thin)
 root=CFG['model']+('_far' if lod==3 else '_LOD'+str(lod));SHELLS[lod]=solids;FEATURES[lod]=features
 return {root:{'parent':None,'pivot':np.zeros(3),'faces':m.faces,'smooth':False}}

def extra_checks(asset,report):
 for lod,budget in enumerate(CFG['budgets']):
  ns=asset.build(str(lod));count=sum(tri_count(n) for n in ns.values())
  report(count<=budget,f'LOD{lod} triangle budget',str(count))
  report(all(closed_surface(f) and surface_orientation(f)['ok'] for _,f in SHELLS[lod]),f'LOD{lod} closed outward structural primitives')
  if lod<3:
   f=FEATURES[lod];report(sum(n.startswith('terrace_post') for n in f)==4,f'LOD{lod} four supported canopy posts')
   report(all(n in f for n in ['main_roof','front_gable','terrace_roof','entrance','chimney']),f'LOD{lod} architectural identity')
