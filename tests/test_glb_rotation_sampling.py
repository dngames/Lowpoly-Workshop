"""Independent analytic rotations catch wrong quaternion arcs and timing."""
import math
import numpy as np
from lowpoly_workshop.kit.glb import Glb

def rotation(angle):
    a=math.radians(angle)
    return np.array([[math.cos(a),-math.sin(a),0],[math.sin(a),math.cos(a),0],[0,0,1]])

def quaternion(angle):
    a=math.radians(angle)*.5
    return np.array([0,0,math.sin(a),math.cos(a)])

for start,end,flip in [(0,120,False),(170,185,True),(350,370,False),(0,0,True)]:
    g=Glb.__new__(Glb);g.nodes=[{'name':'rotor'}]
    values=[np.array([0.,1.]),np.array([quaternion(start),quaternion(end)*(-1 if flip else 1)])]
    g.acc=lambda index:values[index]
    g.js={'animations':[{'channels':[{'sampler':0,'target':{'node':0,'path':'rotation'}}],
                         'samplers':[{'input':0,'output':1,'interpolation':'LINEAR'}]}]}
    for t in [0,.072,.25,.5,.864,1]:
        actual=g.sample(t,0)[0][0];expected=rotation(start+(end-start)*t)
        assert np.max(abs(actual-expected))<1e-6,(start,end,flip,t,actual,expected)
    print('PASS shortest quaternion arc and angular timing:',start,end,'opposite sign',flip)
