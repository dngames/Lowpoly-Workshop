"""Prepare cached closed organic LODs through an asset's raw_sources() hook.

Run with the kit Blender launcher: -P shell_lods.py -- asset-directory.
The generator uses the saved triangles on host Python as well as in Blender.
"""
import sys
from pathlib import Path
import hashlib
import json
import bpy
import bmesh
import numpy as np
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from lowpoly_workshop.kit.asset import Asset
from lowpoly_workshop.kit.atomic import write_json

def mesh(faces):
    verts=[];indices={};polys=[]
    for pts,*_ in faces:
        ids=[]
        for p in pts:
            key=tuple(np.round(p,7))
            if key not in indices:
                indices[key]=len(verts);verts.append(tuple(p))
            ids.append(indices[key])
        polys.append(ids)
    me=bpy.data.meshes.new('organic_source');me.from_pydata(verts,[],polys)
    ob=bpy.data.objects.new('organic_source',me);bpy.context.scene.collection.objects.link(ob)
    return ob

def evaluated(ob):
    ev=ob.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh()
    try:
        bm=bmesh.new();bm.from_mesh(me)
    finally:ev.to_mesh_clear()
    return bm

def remove(ob):
    me=ob.data;bpy.data.objects.remove(ob,do_unlink=True);bpy.data.meshes.remove(me)

def bake(faces,target,voxel=True,voxels=64):
    ob=mesh(faces)
    if voxel:
        modifier=ob.modifiers.new('Watertight union','REMESH');modifier.mode='VOXEL'
        pts=np.concatenate([f[0] for f in faces]);modifier.voxel_size=float(np.ptp(pts,axis=0).max()/voxels)
        modifier.adaptivity=0;modifier.use_smooth_shade=False
    bm=evaluated(ob);remove(ob)
    bmesh.ops.triangulate(bm,faces=list(bm.faces));bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    me=bpy.data.meshes.new('closed_dense');bm.to_mesh(me);bm.free()
    ob=bpy.data.objects.new('closed_dense',me);bpy.context.scene.collection.objects.link(ob)
    modifier=ob.modifiers.new('Outline preserving collapse','DECIMATE')
    modifier.decimate_type='COLLAPSE';modifier.ratio=min(1,(target-2)/len(me.polygons));modifier.use_collapse_triangulate=True
    bm=evaluated(ob);remove(ob)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    assert all(e.is_manifold for e in bm.edges),'Open/non-manifold shell'
    assert len(bm.faces)<=target,(len(bm.faces),target)
    pts=np.concatenate([q for q,*_ in faces]);lo=pts.min(0);hi=pts.max(0)
    bv=np.asarray([v.co[:] for v in bm.verts]);blo=bv.min(0);bhi=bv.max(0)
    if np.any(bhi-blo<=1e-12):raise ValueError('Collapsed shell cannot preserve source bounds')
    for v in bm.verts:v.co=tuple(lo+(np.asarray(v.co)-blo)/(bhi-blo)*(hi-lo))
    # Transfer broad source palette by nearest actual source triangle.
    src=mesh(faces);sb=bmesh.new();sb.from_mesh(src.data);sb.faces.ensure_lookup_table()
    tree=BVHTree.FromBMesh(sb)
    result=[]
    for face in bm.faces:
        _,_,idx,_=tree.find_nearest(face.calc_center_median())
        result.append((np.asarray([v.co[:] for v in face.verts]),faces[idx][1],None,False))
    sb.free();remove(src);bm.free()
    return result

def main():
    a=Asset(sys.argv[sys.argv.index('--')+1]);rows={}
    if a.spec['kind'] != 'static-prop':
        raise ValueError('Shell LODs are only for explicitly declared static organic props')
    if hasattr(a.gen,'skin'):
        raise ValueError('Shell LODs cannot merge skinned geometry')
    if hasattr(a.gen,'clips') and a.gen.clips(a.build(),a.params()):
        raise ValueError('Shell LODs cannot merge animated parts')
    for spec in a.gen.raw_sources():
        if spec.get('static_organic') is not True:
            raise ValueError('raw_sources must explicitly declare static_organic: true')
        faces=spec['faces'];targets=spec['targets'];key=spec['key']
        if not targets or any(not isinstance(t,int) or t<12 for t in targets):
            raise ValueError('Shell targets must be integers of at least 12 triangles')
        if not faces or any(f[3] for f in faces):
            raise ValueError('Shell source must contain solids, not thin cards')
        near=bake(faces,targets[0],voxels=spec.get('voxels',64))
        levels=[near]+[bake(near,t,voxels=spec.get('voxels',64)) for t in targets[1:]]
        rows[key]=[[[q.tolist(),c] for q,c,_,_ in lev] for lev in levels]
        print('SHELL',key,[len(lev) for lev in levels],flush=True)
    hashes={name:hashlib.sha256(Path(a.path(name)).read_bytes()).hexdigest() for name in a.spec['geometry_sources']}
    Path(a.path('inputs')).mkdir(exist_ok=True)
    write_json(a.path('inputs/shells.json'),{'source_sha256':hashes,'levels':rows,'blender':bpy.app.version_string})

if __name__=='__main__':main()
