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
W,D,EAVE,RIDGE=14.,7.,6.18,9.20
Z_WALL=D/2;Z_EAVE=Z_WALL+.75;Z_GABLE=3.10
HIP_X,HIP_Z=6.60,2.65
HIP_Y=RIDGE-(RIDGE-EAVE)*HIP_Z/Z_EAVE
GABLE_HALF,GABLE_BASE,GABLE_PEAK=3.00,7.10,9.50

def main_height(q):
 x,z=abs(q[0]),abs(q[2])
 if x<=HIP_X and z<=HIP_Z:return RIDGE-(RIDGE-HIP_Y)*z/HIP_Z
 t=max((x-HIP_X)/(7.75-HIP_X),(z-HIP_Z)/(Z_EAVE-HIP_Z))
 return HIP_Y-(HIP_Y-EAVE)*t

def end_skirt_height(q):
 # The vertical timber gable is a discontinuity: lower hip tiles must not sample
 # the upper roof when a corner overlaps its x boundary.
 t=max(0,(abs(q[0])-HIP_X)/(7.75-HIP_X),(abs(q[2])-HIP_Z)/(Z_EAVE-HIP_Z))
 return HIP_Y-(HIP_Y-EAVE)*t

def gable_height(q):
 return RIDGE+(GABLE_PEAK-RIDGE)*q[2]/Z_GABLE-(GABLE_PEAK-GABLE_BASE)*abs(q[0])/GABLE_HALF

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
  # Irimoya: a lower hipped skirt below real timber gable ends, not a full hip.
  A=np.array([[-w/2,eave-.16,-d/2],[w/2,eave-.16,-d/2],[w/2,eave-.16,d/2],[-w/2,eave-.16,d/2]])
  B=A+[0,.16,0]
  C=np.array([[-HIP_X,HIP_Y,-HIP_Z],[HIP_X,HIP_Y,-HIP_Z],[HIP_X,HIP_Y,HIP_Z],[-HIP_X,HIP_Y,HIP_Z]])
  L=np.array([-HIP_X,ridge,0]);R=np.array([HIP_X,ridge,0]);inside=np.array([0,eave,0])
  def make():
   m.face(A,'roof',inside)
   for i in range(4):
    j=(i+1)%4;m.face([A[i],A[j],B[j],B[i]],'roof',inside)
    m.face([B[i],B[j],C[j],C[i]],'roof',inside)
   m.face([C[0],C[1],R,L],'roof',inside);m.face([C[2],C[3],L,R],'roof',inside)
   m.face([C[3],C[0],L],'dark',inside);m.face([C[1],C[2],R],'dark',inside)
  part(name,make)
 def dormer():
  # A closed, raised cross-gable with a full timber front. The back embeds in the main roof.
  F=np.array([[-GABLE_HALF,GABLE_BASE,Z_GABLE],[GABLE_HALF,GABLE_BASE,Z_GABLE],[0,GABLE_PEAK,Z_GABLE]])
  B=np.array([[-GABLE_HALF,RIDGE-(GABLE_PEAK-GABLE_BASE),0],[GABLE_HALF,RIDGE-(GABLE_PEAK-GABLE_BASE),0],[0,RIDGE,0]])
  inside=np.r_[F,B].mean(0)
  def make():
   m.face(F,'dark',inside);m.face(B,'dark',inside)
   for i in range(3):
    j=(i+1)%3;m.face([F[i],F[j],B[j],B[i]],'dark' if i==0 else 'roof',inside)
  part('front_gable',make)
 def tile(name,centre,across,down,width,length,height_fn,cell='tile',sections=4):
  c=np.asarray(centre,float);a=np.asarray(across,float);v=np.asarray(down,float)
  rows=[]
  for t in [-.5,.5]:
   row=[]
   for u in np.linspace(-.5,.5,sections+1):
    q=c+a*u*width+v*t*length;q[1]=height_fn(q)+.035+.065*(1-(2*u)**2)
    row.append(q)
   rows.append(np.array(row))
  A,B=rows;B=B+[0,.03,0];C=A-[0,.075,0];F=B-[0,.12,0];inside=np.r_[A,B,C,F].mean(0)
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
   if lod<2 and not door:
    for a in [0]:box(name+'_mullion'+str(a),c+u*a+normal*.10,[.034,h/2,.045],'wood',[u,up,normal])
    for yy in [0]:box(name+'_cross'+str(yy),c+up*yy+normal*.105,[w/2,.03,.05],'wood',[u,up,normal])
   if lod==0:box(name+'_sill',c-up*(h/2+.17)+normal*.15,[w/2+.21,.065,.22],'wood',[u,up,normal],.025)
 def bench(name,x):
  if lod==2:box(name+'_proxy',[x,.665,Z_WALL+1.2],[1,.405,.27]);return
  for i in range(3):box(name+'_seat'+str(i),[x,.70,Z_WALL+1.02+i*.18],[1,.065,.078],bevel=.025 if lod==0 else 0)
  for i in range(2):box(name+'_back'+str(i),[x,1.0+i*.19,Z_WALL+.95],[1,.065,.065],bevel=.02 if lod==0 else 0)
  for side in [-1,1]:
   box(name+'_leg'+str(side),[x+side*.72,.48,Z_WALL+1.2],[.075,.22,.23])
   beam(name+'_upright'+str(side),[x+side*.72,.52,Z_WALL+.96],[x+side*.72,1.22,Z_WALL+.96],.055)
 if lod==3:
  roof('far_roof',15.5,2*Z_EAVE,EAVE,RIDGE);box('far_walls',[0,3,0],[7,3,Z_WALL],'plaster');dormer()
 else:
  box('stone_skirting',[0,.48,0],[7,.48,Z_WALL],'stone')
  box('ground_floor',[0,2.03,0],[7,1.07,Z_WALL],'dark')
  box('upper_floor',[0,4.6,0],[7,1.5,Z_WALL],'plaster')
  roof('main_roof',15.5,2*Z_EAVE,EAVE,RIDGE)
  dormer()
  box('terrace',[0,.13,Z_WALL+.75],[7.7,.13,1.1],'dark')
  A=np.array([[-7.7,3.45,Z_WALL-.10],[7.7,3.45,Z_WALL-.10],[7.7,2.95,Z_WALL+1.95],[-7.7,2.95,Z_WALL+1.95]]);B=A-[0,.16,0]
  def canopy():
   centre=np.r_[A,B].mean(0);m.face(A,'roof',centre);m.face(B,'roof',centre)
   for i in range(4):j=(i+1)%4;m.face([A[i],A[j],B[j],B[i]],'roof',centre)
  part('terrace_roof',canopy)
  # Timber sits on visible stone shoes, not directly on the terrace/ground.
  for x in [-7.1,-2.4,2.4,7.1]:
   top=3.01975609756;base=.72
   box('terrace_post'+str(x),[x,(top+base)/2,Z_WALL+1.5],[.12,(top-base)/2,.12],bevel=.035 if lod==0 else 0)
   # The lower block reaches ground and projects beyond the terrace front,
   # so the wooden deck cannot visually hide its foot.
   if lod<2:
    box('post_plinth'+str((x,0)),[x,.19,Z_WALL+1.55],[.34,.19,.40],'stonegrain',bevel=.045 if lod==0 else 0)
    box('post_plinth'+str((x,1)),[x,.565,Z_WALL+1.50],[.30,.175,.30],'lightstone',bevel=.045 if lod==0 else 0)
   else:box('post_plinth'+str(x),[x,.37,Z_WALL+1.55],[.34,.37,.40],'stone')
  # Projecting corner stones wrap both faces and climb above the low stone skirt.
  for sx in [-1,1]:
   for sz in [-1,1]:
    rows=5 if lod==0 else 3 if lod==1 else 1
    for row in range(rows):
     height=1.90/rows;spread=.40 if row%2==0 else .35
     box('corner_stone'+str((sx,sz,row)),[sx*6.86,(row+.5)*height-(.007 if row==0 else 0),sz*(Z_WALL-.14)],[spread,height/2-(.007 if row==0 else .014),spread],'lightstone' if row%2==0 else 'stonegrain',bevel=.055 if lod==0 else 0)
  for i,x in enumerate([-4.6,0,4.6]):bench('bench'+str(i),x)
  for face in ['front','back']:
   for i,x in enumerate([-4.8,-1.65,1.65,4.8]):window(face+str(i),face,x,4.75,1.3,1.35,Z_WALL)
  window('entrance','front',0,1.7,3.3,2.3,Z_WALL,True)
  # Paired wooden doors: recessed lower panels, a substantial centre stile,
  # upper glazing lattice, header and threshold read as joinery in clay too.
  box('door_centre_stile',[0,1.70,Z_WALL+.17],[.065,1.15,.085],bevel=.025 if lod==0 else 0)
  box('door_header',[0,3.01,Z_WALL+.19],[1.94,.13,.19],bevel=.045 if lod==0 else 0)
  box('door_threshold',[0,.43,Z_WALL+.20],[1.90,.12,.35],'lightstone',bevel=.035 if lod==0 else 0)
  for side in [-1,1]:
   x=side*.825
   box('door_upper_glass'+str(side),[x,2.10,Z_WALL+.12],[.70,.64,.045],'glass')
   box('door_lower_panel'+str(side),[x,.98,Z_WALL+.12],[.72,.38,.065],'dark',bevel=.025 if lod==0 else 0)
   if lod<2:
    for sign in [-1,1]:
     box('door_upper_jamb'+str((side,sign)),[x+sign*.73,2.10,Z_WALL+.20],[.04,.68,.055],bevel=.015 if lod==0 else 0)
     box('door_upper_rail'+str((side,sign)),[x,2.10+sign*.67,Z_WALL+.21],[.73,.045,.06],bevel=.015 if lod==0 else 0)
     box('door_panel_edge'+str((side,sign)),[x+sign*.65,.98,Z_WALL+.20],[.045,.34,.045],bevel=.015 if lod==0 else 0)
     box('door_panel_rail'+str((side,sign)),[x,.98+sign*.31,Z_WALL+.21],[.65,.045,.055],bevel=.015 if lod==0 else 0)
    box('door_lock_stile'+str(side),[side*.13,1.70,Z_WALL+.20],[.055,1.10,.065],bevel=.02 if lod==0 else 0)
    box('door_handle'+str(side),[side*.22,1.55,Z_WALL+.31],[.025,.13,.04],'dark',bevel=.01 if lod==0 else 0)
    for j in [-1,0,1]:
     box('door_glazing_bar'+str((side,j)),[x+j*.35,2.10,Z_WALL+.19],[.022,.64,.035])
    for j in [-1,0,1]:
     box('door_glazing_rail'+str((side,j)),[x,2.10+j*.39,Z_WALL+.20],[.70,.022,.04])
  for face in ['left','right']:window(face,face,0,4.75,1.3,1.35,7)
  for face in ['front','back','left','right']:
   n=np.array([0,0,1 if face=='front' else -1]) if face in ['front','back'] else np.array([1 if face=='left' else -1,0,0]);u=np.array([1,0,0]) if face in ['front','back'] else np.array([0,0,1]);span=14 if face in ['front','back'] else D;wall=Z_WALL if face in ['front','back'] else 7;axes=[u,[0,1,0],n]
   for y in [1.0,3.15,6.05]:box('belt'+face+str(y),n*(wall+.04)+[0,y,0],[span/2+.1,.10,.11],axes=axes,bevel=.03 if lod==0 else 0)
   for j,x in enumerate(np.linspace(-span/2+.12,span/2-.12,5 if span==14 else 4)):
    box('upper_post'+face+str(j),n*(wall+.04)+u*x+[0,4.6,0],[.085,1.45,.105],axes=axes,bevel=.025 if lod==0 else 0)
   if lod<2:
    step=1.4 if lod==0 else 2.0;cols=math.ceil(span/step);rows=3 if lod==0 else 2
    for row in range(rows):
     cuts=np.linspace(-span/2,span/2,cols+1)+(step*.25 if row%2 else 0);cuts[0]=-span/2;cuts[-1]=span/2
     for j,(a,b) in enumerate(zip(cuts[:-1],cuts[1:])):
      if b-a<.12:continue
      c=n*(wall+.02)+u*(a+b)/2+[0,(row+.5)*.96/rows-(.007 if row==0 else 0),0]
      box('stone_'+face+str((row,j)),c,[(b-a)/2-.018,.96/rows/2-(.007 if row==0 else .014),.13],'lightstone' if (row+j)%3==0 else 'stonegrain',axes,.045 if lod==0 else 0)
    for j,x in enumerate(np.linspace(-span/2+.15,span/2-.15,round(span/.35))):
     if face=='front' and abs(x)<1.85:continue
     box('board_'+face+str(j),n*(wall+.015)+u*x+[0,2.02,0],[.155,1.0,.025],'dark',axes)
   if face=='back' and lod<2:
    for j,x in enumerate([-4.8,-1.65,1.65,4.8]):window('back_lower'+str(j),face,x,1.95,1.3,1.4,Z_WALL)
  if lod<2:
   # Timber construction reads at street distance, including eaves, gable braces and terrace brackets.
   for side in [-1,1]:
    # The reference has broad flat timber bargeboards under the ceramic verge.
    # Put the face forward and below the cap: a round beam behind the cap was hidden.
    start=np.array([0,GABLE_PEAK-.20,Z_GABLE+.35]);end=np.array([side*(GABLE_HALF+.08),GABLE_BASE-.26,Z_GABLE+.35])
    direction=(end-start)/np.linalg.norm(end-start);perpendicular=np.array([-direction[1],direction[0],0])
    box('gable_barge'+str(side),(start+end)/2,[np.linalg.norm(end-start)/2,.27,.11],'wood',[direction,perpendicular,[0,0,1]],.025 if lod==0 else 0)
    beam('gable_brace'+str(side),[side*.12,GABLE_BASE+.12,Z_GABLE+.12],[side*1.45,GABLE_PEAK-(GABLE_PEAK-GABLE_BASE)*1.45/GABLE_HALF-.10,Z_GABLE+.12],.12)
    # These real side gables are the prominent timber triangles in the reference profile.
    gx=side*(HIP_X+.035)
    beam('side_gable_left'+str(side),[gx,HIP_Y,-HIP_Z],[gx,RIDGE,0],.11,n=6)
    beam('side_gable_right'+str(side),[gx,RIDGE,0],[gx,HIP_Y,HIP_Z],.11,n=6)
    beam('side_gable_sill'+str(side),[gx,HIP_Y,-HIP_Z],[gx,HIP_Y,HIP_Z],.10)
    beam('side_gable_centre'+str(side),[gx,HIP_Y,0],[gx,RIDGE,0],.085)
    for direction in [-1,1]:
     beam('side_gable_brace'+str((side,direction)),[gx,HIP_Y+.12,direction*.10],[gx,RIDGE-(RIDGE-HIP_Y)*.48-.10,direction*HIP_Z*.48],.09)
   beam('gable_centre',[0,GABLE_BASE,Z_GABLE+.07],[0,GABLE_PEAK,Z_GABLE+.07],.14)
   beam('gable_sill',[-GABLE_HALF,GABLE_BASE,Z_GABLE+.07],[GABLE_HALF,GABLE_BASE,Z_GABLE+.07],.15)
   for sign in [-1,1]:
    box('main_fascia'+str(sign),[0,6.13,sign*Z_EAVE],[7.76,.10,.11],bevel=.035 if lod==0 else 0)
    for j,x in enumerate(np.arange(-7.35,7.4,.66)):
     box('rafter'+str((sign,j)),[x,6.07,sign*(Z_EAVE-.21)],[.065,.10,.30],bevel=.02 if lod==0 else 0)
   box('canopy_beam',[0,2.89,Z_WALL+1.65],[7.55,.11,.13],bevel=.03 if lod==0 else 0)
   for x in [-7.1,-2.4,2.4,7.1]:
    for direction in [-1,1]:
     if abs(x+direction*.55)>7.3:continue
     beam('terrace_brace'+str((x,direction)),[x,2.35,Z_WALL+1.5],[x+direction*.55,2.98,Z_WALL+1.5],.065)
   # Closed curved tile strips follow each roof plane; their undersides penetrate the roof substrate.
   if lod==0:
    for sign in [-1,1]:
     for row,z in enumerate(np.arange(.35,Z_EAVE,.68)):
      t=max(0,(z-HIP_Z)/(Z_EAVE-HIP_Z));span=HIP_X+(7.75-HIP_X)*t-.04
      cols=max(1,round(2*span/.58))
      for col,x in enumerate(np.linspace(-span+.29,span-.29,cols)):
       q=[x,0,sign*z]
       if sign==1 and z<=Z_GABLE and abs(x)<GABLE_HALF+.1 and gable_height(q)>main_height(q)-.04:continue
       tile('main_tile'+str((sign,row,col)),q,[1,0,0],[0,0,1],.55,.74,main_height,'clay' if (row*17+col*7)%71==0 else 'tile')
     if sign==1:
      # The cross-gable ends at Z_GABLE. Its height function must not erase
      # the exposed main-roof apron farther toward the street.
      for col,x in enumerate(np.arange(-GABLE_HALF+.22,GABLE_HALF,.55)):
       tile('gable_apron_tile'+str(col),[x,0,Z_GABLE+.16],[1,0,0],[0,0,1],.53,.32,main_height)
     for row,x in enumerate(np.arange(HIP_X+.27,7.7,.53)):
      t=(x-HIP_X)/(7.75-HIP_X);span=HIP_Z+(Z_EAVE-HIP_Z)*t-.08;cols=max(1,round(2*span/.58))
      for col,z in enumerate(np.linspace(-span+.28,span-.28,cols)):
       tile('hip_tile'+str((sign,row,col)),[sign*x,0,z],[0,0,1],[1,0,0],.57,.59,end_skirt_height)
    for sign in [-1,1]:
     for row,x in enumerate(np.arange(.33,GABLE_HALF,.62)):
      for col,z in enumerate(np.arange(.4,Z_GABLE,.58)):
       q=[sign*x,0,z]
       if gable_height(q)<main_height(q)-.04:continue
       tile('gable_tile'+str((sign,row,col)),q,[0,0,1],[1,0,0],.57,.68,gable_height)
    for row,z in enumerate(np.arange(Z_WALL+.15,Z_WALL+1.9,.53)):
     for col,x in enumerate(np.arange(-7.38,7.5,.58)):
      tile('canopy_tile'+str((row,col)),[x,0,z],[1,0,0],[0,0,1],.57,.58,lambda p:3.45-.5*(p[2]-(Z_WALL-.1))/2.05)
   # Chunky separate ceramic verge/hip pieces stand proud of the field tiles.
   def rim(name,a,b,r=.18):
    a=np.array(a,float);b=np.array(b,float);count=max(1,math.ceil(np.linalg.norm(b-a)/(.68 if lod==0 else 1.2)))
    for j in range(count):
     lo=a+(b-a)*j/count;hi=a+(b-a)*min(1,(j+1.04)/count)
     beam(name+str(j),lo,hi,r,'rooflight',6)
   for sign in [-1,1]:
    rim('front_verge_tile'+str(sign),[0,GABLE_PEAK+.12,Z_GABLE+.16],[sign*(GABLE_HALF+.10),GABLE_BASE+.08,Z_GABLE+.16],.25)
    for end in [-1,1]:
     rim('end_verge_tile'+str((sign,end)),[sign*HIP_X,RIDGE+.12,0],[sign*HIP_X,HIP_Y+.12,end*HIP_Z],.22)
     rim('hip_rim_tile'+str((sign,end)),[sign*HIP_X,HIP_Y+.12,end*HIP_Z],[sign*7.75,EAVE+.12,end*Z_EAVE],.22)
   for i,x in enumerate(np.arange(-HIP_X,HIP_X,.48 if lod==0 else .95)):
    beam('ridge_cap'+str(i),[x,RIDGE+.07,0],[min(x+(.52 if lod==0 else 1.0),HIP_X+.1),RIDGE+.07,0],.25,'rooflight',8 if lod==0 else 6)
   for i,z in enumerate(np.arange(.2,Z_GABLE,.52 if lod==0 else 1.0)):
    z1=min(z+(.56 if lod==0 else 1.04),Z_GABLE+.1)
    beam('gable_cap'+str(i),[0,gable_height([0,0,z])+.08,z],[0,gable_height([0,0,z1])+.08,z1],.22,'rooflight',8 if lod==0 else 6)
  chimney_base=main_height([4.5,0,-2.3])-.25;chimney_top=RIDGE+.35
  box('chimney',[4.5,(chimney_base+chimney_top)/2,-2.3],[.40,(chimney_top-chimney_base)/2,.40],'stone',bevel=.035 if lod==0 else 0)
  box('chimney_cap',[4.5,chimney_top+.07,-2.3],[.5,.07,.5],'clay',bevel=.025 if lod==0 else 0)
 # Every textured face gets stable local 0..1 coordinates; vertical timber keeps vertical grain.
 for i,(q,cell,uv,thin) in enumerate(m.faces):
  span=np.ptp(q,axis=0);axes=np.argsort(span)[-2:];a,b=int(axes[0]),int(axes[1])
  if cell in ['wood','dark'] and span[1]>.001:
   b=1 if span[1]>=max(span[0],span[2])*.5 else int(np.argmax(span));a=max((j for j in range(3) if j!=b),key=lambda j:span[j])
  lo=q.min(0)
  def projection(x,y):
   u=np.column_stack([(q[:,x]-lo[x])/max(span[x],1e-9),(q[:,y]-lo[y])/max(span[y],1e-9)])
   area=abs(np.sum(u[:,0]*np.roll(u[:,1],-1)-u[:,1]*np.roll(u[:,0],-1)))
   return u,area
  uv,area=projection(a,b)
  if area<1e-8:
   # A sloping narrow face may span X and Y while those coordinates are
   # collinear. Choose the non-collapsed planar projection instead.
   candidates=[(projection(x,y)[1],x,y) for x,y in [(0,1),(0,2),(1,2)]]
   _,a,b=max(candidates)
   uv,_=projection(a,b)
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
