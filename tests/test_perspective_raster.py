"""Compare preview texture/depth against independent camera-ray intersections."""
import numpy as np
from lowpoly_workshop.kit.raster import Camera,render

quad=np.array([[-1.,-1.,-.8],[1.,-1.,.8],[1.,1.,.8],[-1.,1.,-.8]])
order=np.array([[0,1,2],[0,2,3]]);tris=quad[order]
uv=np.array([[0.,1.],[1.,1.],[1.,0.],[0.,0.]])[order]
yy,xx=np.mgrid[:256,:256];texture=np.stack([xx,yy,np.full_like(xx,17)],-1).astype(float)
palette={'tilt':[100,100,100],'flat':[200,50,50]};classes={'tilt':1,'flat':2}
for ortho in [False,True]:
 cam=Camera(0,0,0,6,96,64,64,target=(0,0,0),ortho=ortho)
 rgb,cmap,depth=render(tris,['tilt']*2,cam,128,128,shade=False,palette=palette,classes=classes,uvs=uv,tex=texture)
 errors=[];depth_errors=[]
 for py in [56,60,64,68,72]:
  for px in [54,58,62,68,74,78]:
   # Intersect the pixel-centre ray with the world plane Z=.8X.
   rx=(px+.5-64)/96;ry=(64-py-.5)/96
   distance=6 if ortho else 6/(1+.8*rx)
   x,y=distance*rx,distance*ry
   if abs(x)>.85 or abs(y)>.85:continue
   expected=texture[int((1-y)*.5*256),int((x+1)*.5*256)]
   assert cmap[py,px]==1
   errors.append(float(np.max(abs(rgb[py,px]-expected))))
   depth_errors.append(abs(float(depth[py,px])-(6-.8*x)))
 assert errors and max(errors)<=1.,('atlas slips against analytic plane',ortho,max(errors))
 assert max(depth_errors)<1e-7,('camera depth differs from ray hit',ortho,max(depth_errors))
 flat=np.array([[-1.3,-1.3,0],[1.3,-1.3,0],[1.3,1.3,0],[-1.3,1.3,0]])[order]
 _,visible,_=render(np.concatenate([tris,flat]),['tilt']*2+['flat']*2,cam,128,128,shade=False,palette=palette,classes=classes)
 for px in [60,62,63,65,66,70]:
  assert visible[64,px]==(2 if px<64 else 1),('wrong crossing-plane occlusion',ortho,px,visible[64,px])
 print('PASS',('orthographic' if ortho else 'perspective'),'atlas/depth and crossing-plane occlusion match analytic ray intersections')
