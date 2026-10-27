"""Original painted materials; the full generated sheet and provenance accompany the source."""
from pathlib import Path
import numpy as np
from lowpoly_workshop.kit.atlas import Atlas,stretch
DATA=np.load(Path(__file__).parent/'inputs/materials.npz')
COLORS={'wood':'#A9744B','dark':'#514136','roof':'#5B6B7E','rooflight':'#708394','clay':'#B96548','stone':'#8E97A0','lightstone':'#BDB3A3','plaster':'#F4E7D0','glass':'#92794E','concrete':'#9C9C89'}

def painter(name):
 def paint(col,kit,rect,atlas):
  x0,y0,x1,y1=rect;h,w=y1-y0,x1-x0
  if name=='glass':
   y,x=np.mgrid[0:h,0:w];v=y/h
   patch=np.array([150,123,77])[None,None,:]*(1-.48*v[:,:,None])
   patch=np.broadcast_to(patch,(h,w,3)).copy();patch+=18*np.exp(-((x/w-.25)**2+(v-.20)**2)/.08)[:,:,None]
  else:
   source='wood' if name=='dark' else 'roof' if name in ['rooflight','clay','tile'] else 'stone' if name in ['lightstone','stonegrain','concrete'] else name
   im=DATA[source]
   if name=='tile':im=im[35:100,10:45]
   # Cap and accent ceramics must sample one tile, not the whole roof-sheet.
   if name in ['rooflight','clay']:im=im[35:90,10:32]
   if name in ['stonegrain','lightstone','concrete']:im=im[30:100,40:130]
   patch=stretch(im,h,w).astype(float)
   if name=='dark':patch*=np.array([.48,.51,.54])
   if name=='rooflight':patch=patch*.85+25
   if name=='clay':patch=patch.mean(2)[:,:,None]*np.array([1.25,.68,.48])
   if name=='lightstone':patch=patch*.84+np.array([51,38,18])
  col[y0:y1,x0:x1]=np.clip(patch,0,255).astype(np.uint8)
 return paint

NAMES=list(COLORS)+['tile','stonegrain']
ATLAS=Atlas({n:(COLORS.get(n,COLORS['roof' if n=='tile' else 'stone']),None,n) for n in NAMES},
 decals={n:((480,480),painter(n)) for n in NAMES},size=2048)
