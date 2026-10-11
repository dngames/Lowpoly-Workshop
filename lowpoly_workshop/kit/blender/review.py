"""Review the ACTUAL exported GLBs, including underside and configurable close-ups."""
import sys,os,json,re,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
import bpy,numpy as np
from lowpoly_workshop.kit.asset import Asset
from lowpoly_workshop.kit.blender.build import clear,world_matrices,to_b
from lowpoly_workshop.kit.blender.render import setup,aim
from lowpoly_workshop.kit.mesh import triangles
from lowpoly_workshop.quality import topology,uv_diagnostics
VIEWS={'front':(0,5),'back':(180,5),'side':(-90,5),'quarter':(38,20),'top':(0,85),'below':(25,-65)}
def slug(s):return re.sub(r'[^a-zA-Z0-9_-]','_',str(s))
def points(objects):
    return np.array([o.matrix_world@v.co for o in objects if o.type=='MESH' for v in o.data.vertices])
def main():
    a=Asset(sys.argv[sys.argv.index('--')+1]);cfg=a.spec.get('review',{});shots=[]
    from lowpoly_workshop.features import regions as feature_regions, enabled
    from lowpoly_workshop.runner import fingerprint
    from lowpoly_workshop.approval import export_hashes
    source_key=fingerprint(a.dir);exports=export_hashes(a.dir)
    whole_views=list(cfg.get('views',list(VIEWS)))
    whole_modes=list(cfg.get('modes',['textured','plain','checker']))
    if enabled(a.spec):
        whole_views=list(dict.fromkeys(whole_views+['front','side','quarter','below','back']))
        whole_modes=list(dict.fromkeys(whole_modes+['plain','textured']))
    for output in a.outputs():
        clear();src=a.path(output['file']);bpy.ops.import_scene.gltf(filepath=src)
        objs={o.name:o for o in bpy.context.scene.objects}
        for imported in objs.values():imported.animation_data_clear()
        meshes=[o for o in objs.values() if o.type=='MESH']
        base={o.name:list(o.data.materials) for o in meshes}
        nodes=a.build(output.get('variant'),output.get('scale',1.));origin=nodes[output['origin']]['pivot'] if output.get('origin') else np.zeros(3)
        sc=bpy.context.scene;cam,sun=setup(sc);sc.render.use_freestyle=False
        sc.eevee.taa_render_samples=int(os.environ.get('LOWPOLY_RENDER_SAMPLES','16'))
        size=int(cfg.get('size',512));sc.render.resolution_x=size;sc.render.resolution_y=size;sc.render.resolution_percentage=100
        plain=bpy.data.materials.new('Review clay');plain.diffuse_color=(.55,.65,.7,1)
        wire=bpy.data.materials.new('Review edges');wire.diffuse_color=(.04,.06,.08,1)
        checker=bpy.data.materials.new('UV checker');checker.use_nodes=True;nt=checker.node_tree
        tex=nt.nodes.new('ShaderNodeTexChecker');tex.inputs['Scale'].default_value=16
        uv=nt.nodes.new('ShaderNodeTexCoord');nt.links.new(uv.outputs['UV'],tex.inputs['Vector']);nt.links.new(tex.outputs['Color'],nt.nodes['Principled BSDF'].inputs['Base Color'])
        regions=[dict(name='whole',nodes=list(objs),views=whole_views,modes=whole_modes)] + list(cfg.get('regions',[])) + feature_regions(a.spec,output['file'])
        # Suspect source regions get an exported-mesh close-up automatically.
        suspect=set(i.get('node') for i in uv_diagnostics(nodes,a.gen.ATLAS) if i.get('node'))
        for name,nd in nodes.items():
            if not nd['faces']:continue
            t=topology(triangles({name:nd})[0])
            if t['degenerate'] or t['duplicates'] or t['nonmanifold_edges']:suspect.add(name)
        regions.extend(dict(name='diagnostic-'+n,nodes=[n],views=['quarter','below']) for n in sorted(suspect))
        for pose_name,pose in {'rest':{},**a.spec.get('poses',{})}.items():
            W=world_matrices(nodes,pose,origin)
            for name in nodes:
                if name in objs:
                    objs[name].matrix_world=to_b(W[name])
                    bpy.context.view_layer.update()
            bpy.context.view_layer.update()
            for region in regions:
                if region.get('poses') and pose_name not in region['poses']:continue
                if region.get('feature_id') and any(n not in objs for n in region['nodes']):
                    raise ValueError('Feature nodes missing from exported GLB: '+region['name'])
                chosen=[objs[n] for n in region.get('nodes',[]) if n in objs]
                if region.get('bounds'):
                    bounds=np.array(region['bounds'],float);lo,hi=bounds
                    target=(lo+hi)/2;span=float(max(hi-lo))
                else:
                    p=points(chosen)
                    if not len(p):
                        if region.get('feature_id'):raise ValueError('Feature needs at least one exported mesh for framing: '+region['name'])
                        continue
                    # Convert Blender (+Z up) bounds back to glTF (+Y up).
                    q=p@np.array([[1,0,0],[0,0,1],[0,-1,0]]).T
                    lo,hi=q.min(0),q.max(0);target=(lo+hi)/2;span=float(max(hi-lo))
                if span<=0:continue
                for o in meshes:o.hide_render=bool(region.get('isolate',False) and o not in chosen)
                for mode in region.get('modes',cfg.get('modes',['textured','plain','checker'])):
                    if mode not in ('textured','plain','checker','wireframe'):raise ValueError('Unknown review mode '+mode)
                    mods=[]
                    for o in meshes:
                        o.data.materials.clear()
                        for m in (base[o.name] if mode=='textured' else [checker if mode=='checker' else wire if mode=='wireframe' else plain]):o.data.materials.append(m)
                        if mode=='wireframe':
                            mod=o.modifiers.new('Review wireframe','WIREFRAME');mod.thickness=span*.0015;mods.append((o,mod))
                    for view in region.get('views',cfg.get('views',list(VIEWS))):
                        az,el=VIEWS[view];aim(cam,sun,target,az,el,0,span*6+2)
                        cam.data.type='ORTHO';cam.data.ortho_scale=span*float(region.get('margin',1.3));cam.data.clip_start=.001;cam.data.clip_end=span*20+20
                        name='-'.join(map(slug,(Path(src).stem,pose_name,region['name'],mode,view)))+'.png'
                        dest=a.out('review',name);sc.render.filepath=dest;bpy.ops.render.render(write_still=True)
                        pose_vertices=points(meshes)
                        pose_hash=hashlib.sha256(np.round(pose_vertices,6).tobytes()).hexdigest()
                        shots.append(dict(feature_id=region.get('feature_id'),nodes=region.get('nodes',[]),image_sha256=hashlib.sha256(Path(dest).read_bytes()).hexdigest(),pose_geometry_sha256=pose_hash,file=Path(dest).relative_to(Path(a.dir)).as_posix(),output=output['file'],pose=pose_name,region=region['name'],mode=mode,view=view,source='exported-model-render',sha256=hashlib.sha256(Path(src).read_bytes()).hexdigest()))
                    for o,m in mods:o.modifiers.remove(m)
    if fingerprint(a.dir)!=source_key or export_hashes(a.dir)!=exports:
        raise ValueError('Source or exports changed during rendering; rerun review')
    Path(a.out('review','index.json')).write_text(json.dumps(dict(status='visual-review-pending',source=source_key,exports=exports,shots=shots),indent=2))
    print('REVIEW',len(shots),'exported-model images')
if __name__=='__main__':main()
