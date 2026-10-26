"""UVs for opt-in named-surface world props (v measured down, as kit atlas UVs)."""
import numpy as np

def face_uvs(points,uv,surface):
    if surface.startswith('decal_'):
        if uv is None:
            raise ValueError('Runtime decal requires explicit local UVs: '+surface)
        return [(float(u),1.0-float(v)) for u,v in uv]
    points=np.asarray(points,float)
    normal=np.cross(points[1]-points[0],points[2]-points[0])
    axis=int(np.argmax(np.abs(normal)))
    axes=(2,1) if axis==0 else ((0,2) if axis==1 else (0,1))
    return [(float(q[axes[0]]),1.0-float(q[axes[1]])) for q in points]
