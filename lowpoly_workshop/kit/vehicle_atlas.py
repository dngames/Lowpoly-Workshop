"""Shared vehicle atlas helpers: binary alpha mask and linear fallback colours.

The atlas remains opaque to glTF: alpha is a paint mask consumed by the game's future
vehicle material, not transparency. The matching fallback colour is carried in COLOR_0.
"""
import numpy as np


def pack_vehicle_atlas(colour, mask):
    colour=np.asarray(colour,dtype=np.uint8); mask=np.asarray(mask,dtype=np.uint8)
    if colour.shape != (2048,2048,3) or mask.shape != colour.shape:
        raise ValueError('vehicle atlas and RGB mask must both be 2048 x 2048')
    if np.any(mask[:,:,1:]) or not np.isin(mask[:,:,0],[0,255]).all():
        raise ValueError('vehicle paint mask must use binary R only')
    return np.dstack((colour,mask[:,:,0]))


def fallback_linear(atlas_rgb, triangle_uv, cell, paint_cells, paint_linear):
    """Return exact paint linear RGB for paint cells; otherwise average covered texels.

    UVs use the workshop's 0..1 convention with v measured down from the image top.
    Texel centres are tested against the triangle. Sub-texel triangles use their centroid.
    """
    if cell in paint_cells:
        paint=np.asarray(paint_linear,dtype=float)
        if paint.shape!=(3,) or not np.isfinite(paint).all() or np.any(paint<0) or np.any(paint>1):
            raise ValueError('paint_linear must contain three linear RGB values in 0..1')
        return paint
    rgb=np.asarray(atlas_rgb)
    uv=np.asarray(triangle_uv,dtype=float)
    if rgb.ndim!=3 or rgb.shape[2]!=3 or uv.shape!=(3,2) or not np.isfinite(uv).all():
        raise ValueError('fallback colour needs an RGB atlas and finite triangle UVs')
    uv=np.clip(uv,0,1); h,w=rgb.shape[:2]
    x0=max(0,int(np.floor(uv[:,0].min()*w)));x1=min(w,int(np.ceil(uv[:,0].max()*w)))
    y0=max(0,int(np.floor(uv[:,1].min()*h)));y1=min(h,int(np.ceil(uv[:,1].max()*h)))
    yy,xx=np.mgrid[y0:y1,x0:x1];px=(xx+.5)/w;py=(yy+.5)/h
    cross=[]
    for a,b in zip(uv,np.roll(uv,-1,axis=0)):
        cross.append((b[0]-a[0])*(py-a[1])-(b[1]-a[1])*(px-a[0]))
    inside=(np.logical_and.reduce([c>=-1e-12 for c in cross]) |
            np.logical_and.reduce([c<=1e-12 for c in cross]))
    if inside.any():
        sampled=rgb[yy[inside],xx[inside]]
    else:
        centre=uv.mean(axis=0)
        sampled=rgb[[min(int(centre[1]*h),h-1)],[min(int(centre[0]*w),w-1)]]
    srgb=sampled.astype(float)/255
    linear=np.where(srgb<=.04045,srgb/12.92,((srgb+.055)/1.055)**2.4)
    return linear.mean(axis=0)
