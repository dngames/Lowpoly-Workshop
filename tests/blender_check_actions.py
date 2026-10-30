"""Regression: layered actions keep linear curves and the correct NLA slot."""
from pathlib import Path
import sys
import bpy
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lowpoly_workshop.kit.blender.build import action_curves,key_clips,to_b,world_matrices

nodes={'Root':{'parent':None,'pivot':np.zeros(3)},
       'Left':{'parent':'Root','pivot':np.array([.4,.7,0])},
       'Right':{'parent':'Root','pivot':np.array([-.4,.7,0])}}
objs={};world=world_matrices(nodes,{},np.zeros(3))
for name,node in nodes.items():
 ob=bpy.data.objects.new(name,None);bpy.context.scene.collection.objects.link(ob)
 if node['parent']:ob.parent=objs[node['parent']]
 ob.matrix_world=to_b(world[name]);objs[name]=ob
 bpy.context.view_layer.update()
key_clips(objs,nodes,{'Wave':{'fps':24,'frames':[
 {'Left':[0,0,30],'Right':[0,0,-30]},
 {'Left':[0,0,-30],'Right':[0,0,30]},
 {'Left':[0,0,30],'Right':[0,0,-30]}]}},np.zeros(3))
for name,ob in objs.items():
 assert ob.animation_data.action is None
 assert {track.name for track in ob.animation_data.nla_tracks}=={'Wave','Stand'}
 for track in ob.animation_data.nla_tracks:
  strip=track.strips[0];action=strip.action;curves=action_curves(action)
  assert curves,(name,track.name,'empty action')
  for curve in curves:
   assert all(p.interpolation=='LINEAR' for p in curve.keyframe_points)
   a,b=curve.keyframe_points[:2];mid=(a.co.x+b.co.x)*.5
   assert abs(curve.evaluate(mid)-(a.co.y+b.co.y)*.5)<1e-6
  if getattr(action,'slots',None):
   assert strip.action_slot is not None
   assert strip.action_slot.identifier==action.slots[0].identifier
 assert abs(ob.rotation_quaternion.w-1)<1e-6,'Stand did not preserve rest rotation'
print('PASS linear curves survive legacy/layered action conversion')
print('PASS NLA strips preserve each object action slot and rest rotation')
