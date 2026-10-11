"""Generic optional skeletal export; bone names are supplied by the generator."""
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
import bpy,numpy as np
from lowpoly_workshop.kit.asset import Asset
from lowpoly_workshop.kit.skin import validate,bone_segments,vertex_weights
from lowpoly_workshop.kit.blender.build import clear,material,node_object,C4

def main():
    a=Asset(sys.argv[sys.argv.index('--')+1]);nodes=a.build();p=a.params()
    if not hasattr(a.gen,'skin'):raise ValueError('Generator needs a skin(nodes, params) hook')
    spec=a.gen.skin(nodes,p);validate(spec)
    if not spec['bones']:raise ValueError('Skeleton cannot be empty')
    if set(spec.get('bind',{}))|set(spec.get('rigid',{})) != {n for n,nd in nodes.items() if nd['faces']}:
        raise ValueError('Every mesh node must have exactly one bind or rigid rule')
    if set(spec.get('bind',{})) & set(spec.get('rigid',{})):raise ValueError('Bind and rigid rules overlap')
    seen=set()
    for b in spec['bones']:
        if b.get('parent') and b['parent'] not in seen:raise ValueError('Bones must be parent-first without cycles')
        head,tail=np.asarray(b['head'],float),np.asarray(b['tail'],float)
        if head.shape!=(3,) or tail.shape!=(3,) or not np.isfinite([head,tail]).all() or np.linalg.norm(tail-head)<1e-6:raise ValueError('Bone endpoints must be finite and distinct')
        seen.add(b['name'])
    clear();dest=Path(a.out('skinned.glb'));mat=material(a.gen.ATLAS,str(dest.parent),'skinned','skinned_mask.png')
    arm=bpy.data.armatures.new('Skeleton');ob=bpy.data.objects.new('Skeleton',arm);bpy.context.collection.objects.link(ob);bpy.context.view_layer.objects.active=ob;ob.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
    for b in spec['bones']:
        bone=arm.edit_bones.new(b['name']);bone.head=C4[:3,:3]@np.asarray(b['head']);bone.tail=C4[:3,:3]@np.asarray(b['tail'])
        if b.get('parent'):bone.parent=arm.edit_bones[b['parent']]
    bpy.ops.object.mode_set(mode='OBJECT');segments=bone_segments(spec)
    for name,nd in nodes.items():
        obj=node_object(name,nd,mat,a.gen.ATLAS)
        # mesh_object stores points relative to pivot/rest rotation. Restore world coordinates
        # before parenting to the identity armature, preserving every UV corner.
        R=nd.get('rot',np.eye(3));world=np.eye(4);world[:3,:3]=R;world[:3,3]=nd['pivot']
        obj.matrix_world=__import__('lowpoly_workshop.kit.blender.build',fromlist=['to_b']).to_b(world)
        if obj.type!='MESH':continue
        obj.parent=ob;mod=obj.modifiers.new('Skin','ARMATURE');mod.object=ob
        points=np.array([C4[:3,:3].T@(obj.matrix_world@v.co) for v in obj.data.vertices])
        cands=spec.get('bind',{}).get(name,[spec.get('rigid',{}).get(name)])
        weights=vertex_weights(points,cands,segments,spec.get('sigma',.05))
        groups={bn:obj.vertex_groups.new(name=bn) for bn in cands}
        for i,row in enumerate(weights):
            for bn,w in row:groups[bn].add([i],w,'REPLACE')
    bpy.context.scene.unit_settings.system='METRIC'
    bpy.ops.wm.save_as_mainfile(filepath=str(dest.with_suffix('.blend')))
    bpy.ops.export_scene.gltf(filepath=str(dest),export_format='GLB',export_yup=True,export_skins=True,export_animations=False,export_extras=True,export_attributes=True,export_apply=False,export_all_influences=False)
    # Import the result again and verify an actual deformed pose stays finite.
    bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=str(dest))
    arms=[o for o in bpy.context.scene.objects if o.type=='ARMATURE']
    if len(arms)!=1:raise ValueError('Roundtrip skeleton missing')
    bone_names={b.name for b in arms[0].data.bones}
    if bone_names!=seen:raise ValueError('Roundtrip bone names differ')
    for pb in arms[0].pose.bones:
        pb.rotation_mode='XYZ';pb.rotation_euler.x=.4
    bpy.context.view_layer.update();dg=bpy.context.evaluated_depsgraph_get()
    count=0
    for obj in bpy.context.scene.objects:
        if obj.type!='MESH':continue
        evaluated=obj.evaluated_get(dg);mesh=evaluated.to_mesh()
        if not np.isfinite(np.array([v.co for v in mesh.vertices])).all():raise ValueError('Nonfinite posed vertices')
        count+=len(mesh.vertices);evaluated.to_mesh_clear()
    if not count:raise ValueError('Roundtrip mesh missing')
    Path(a.out('skin-check.json')).write_text(json.dumps(dict(ok=True,bones=sorted(seen),posed_vertices=count,note='Finite roundtrip pose; inspect joint silhouettes in target runtime.'),indent=2))
    print('SKIN PASS',len(seen),'bones',count,'posed vertices')
if __name__=='__main__':main()
