"""Deterministic CPU palette/silhouette proofs for software-only build machines.

Uses the kit's existing camera, rasterizer and generator. Not a substitute for a
production-material capture: label that evidence separately in the handover.
"""
import numpy as np
from PIL import Image
from . import rig,raster
from .camfit import make_cam

def image(a,nodes,pose,camera,width,height):
    triangles,cells=rig.posed_triangles(nodes,pose)
    rgb,classes,_=raster.render(triangles,cells,camera,width,height,palette=a.palette(nodes),
                               classes=a.cell_classes())
    rgba=np.concatenate([rgb.astype(np.uint8),((classes>0)*255).astype(np.uint8)[...,None]],axis=2)
    return Image.fromarray(rgba)

def run(a,args):
    if args[0]=='views':
        for st in args[1:] or a.sets():
            for view in a.views(st):
                entry=a.cam(st,view)
                if not entry:continue
                v=entry['cam'];nodes,pose=a.scene(st,view,v[7:]);x0,y0,x1,y1=a.crop_box(st,view)
                image(a,nodes,pose,make_cam(v,a.target()),x1-x0,y1-y0).save(a.out('render',st,view+'.png'))
                print('RENDERED',st,view,'(kit CPU palette proof)',flush=True)
    else:
        scenes=a.gen.show_scenes(a) if hasattr(a.gen,'show_scenes') else {'rest':(a.build(a.outputs()[0].get('variant')),{},None)}
        views=a.spec.get('show_views',{'side':[-90,4],'front':[0,6],'top':[0,82],'q34':[38,20]})
        for name,(nodes,pose,focus) in scenes.items():
            T,_=rig.posed_triangles(nodes,pose);P=T.reshape(-1,3);lo,hi=P.min(0),P.max(0)
            target=(lo+hi)/2 if focus is None else np.asarray(focus)
            span=float(np.max(hi-lo));dist=span*20+40
            for view,(az,el) in views.items():
                cam=make_cam([az,el,0,dist,500/span,450,350],target)
                image(a,nodes,pose,cam,900,700).save(a.out('render','show',name+'_'+view+'.png'))
                print('SHOT',name,view,'(kit CPU palette proof)',flush=True)
