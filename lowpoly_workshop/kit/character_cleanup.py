"""Conservative cleanup of rigid character parts, without changing bone weights or UVs.

Close planar open ends on leg shells. Remove a face only when it lies strictly inside
another closed solid in the SAME rigid node. The latter stays hidden in every pose.
Never use a helmet to occlude a head, or a torso to occlude an independently moving arm.
"""
from collections import Counter, defaultdict
import numpy as np
from .glb import intersect


def key(v):
    return tuple(np.round(v, 6))


def triangles(faces):
    out = []
    for pts, _, _, thin in faces:
        if thin:
            continue
        for k in range(1, len(pts)-1):
            q = np.asarray([pts[0], pts[k], pts[k+1]])
            if np.linalg.norm(np.cross(q[1]-q[0], q[2]-q[0])) > 1e-10:
                out.append(q)
    return np.asarray(out)


def close_planar_ends(node):
    edges = defaultdict(list)
    points = {}
    for face in node['faces']:
        if face[3]:
            continue
        for q in triangles([face]):
            for a,b in zip(q, np.roll(q, -1, axis=0)):
                ka,kb=key(a),key(b);points[ka]=a;points[kb]=b
                edges[tuple(sorted((ka,kb)))].append((ka,kb,face[1]))
    boundary={e:values[0] for e,values in edges.items() if len(values)==1}
    adjacent=defaultdict(list)
    for a,b in boundary:
        adjacent[a].append(b);adjacent[b].append(a)
    if any(len(v)!=2 for v in adjacent.values()):
        raise ValueError('Open joint boundary is not a simple ring')
    loops=[]
    while boundary:
        edge=next(iter(boundary));a,b,cell=boundary[edge];loop=[a];previous=a;current=b
        while current!=a:
            loop.append(current)
            following=next(v for v in adjacent[current] if v!=previous)
            previous,current=current,following
        for x,y in zip(loop,loop[1:]+loop[:1]):
            boundary.pop(tuple(sorted((x,y))),None)
        loops.append((loop,cell))
    # Adjacent colour bands of a rigid limb must share exactly the same ring.
    # Match equal-count rings at the same station and average their tiny radius/
    # basis discrepancies. This closes the seam with zero added triangles.
    replacement={};used=set()
    for i,(aa,_) in enumerate(loops):
        if i in used:continue
        pa=np.asarray([points[k] for k in aa]);centre=pa.mean(0)
        for j,(bb,_) in enumerate(loops):
            if j<=i or j in used or len(aa)!=len(bb):continue
            pb=np.asarray([points[k] for k in bb])
            if np.linalg.norm(centre-pb.mean(0))>1e-5:continue
            distance=np.linalg.norm(pa[:,None]-pb[None,:],axis=-1);indices=distance.argmin(1)
            if len(set(indices))!=len(aa) or distance[np.arange(len(aa)),indices].max()>.04:continue
            for k,l in enumerate(indices):
                q=(pa[k]+pb[l])*.5;replacement[aa[k]]=q;replacement[bb[l]]=q
            used.update((i,j));break
    if replacement:
        node['faces']=[(np.asarray([replacement.get(key(v),v) for v in pts]),cell,uv,thin)
                       for pts,cell,uv,thin in node['faces']]
    added=0
    for i,(loop,cell) in enumerate(loops):
        if i in used:continue
        pts=np.asarray([points[v] for v in loop][::-1])
        _,singular,_=np.linalg.svd(pts-pts.mean(0),full_matrices=False)
        if singular[-1]>1e-5:
            raise ValueError('Cannot cap a nonplanar joint boundary')
        node['faces'].append((pts,cell,None,False));added+=len(pts)-2
    node['joined_band_rings']=len(used)//2
    return added


def components(faces):
    # Connect solid faces sharing geometric vertices, including triangulated cap fans.
    neighbours=defaultdict(list)
    solid=[]
    for i,face in enumerate(faces):
        if face[3] or not len(triangles([face])):
            continue
        solid.append(i)
        for p in face[0]:neighbours[key(p)].append(i)
    remaining=set(solid);out=[]
    while remaining:
        stack=[remaining.pop()];group=[]
        while stack:
            i=stack.pop();group.append(i)
            for p in faces[i][0]:
                for j in neighbours[key(p)]:
                    if j in remaining:remaining.remove(j);stack.append(j)
        tri=triangles([faces[i] for i in group]);edges=Counter()
        for q in tri:
            keys=[key(v) for v in q]
            for a,b in zip(keys,keys[1:]+keys[:1]):edges[tuple(sorted((a,b)))]+=1
        if edges and all(n==2 for n in edges.values()):
            out.append((set(group),tri,tri.min((0,1)),tri.max((0,1))))
    return out


def strictly_inside(points, tri):
    # Signed solid angle: an oriented closed surface encloses 4*pi steradians.
    # Requiring >3*pi rejects boundary points and inconsistent/open occluders.
    v=tri[None,:,:,:]-np.asarray(points)[:,None,None,:]
    a,b,c=v[:,:,0],v[:,:,1],v[:,:,2]
    na,nb,nc=np.linalg.norm(a,axis=-1),np.linalg.norm(b,axis=-1),np.linalg.norm(c,axis=-1)
    numerator=np.einsum('...i,...i->...',a,np.cross(b,c))
    denominator=na*nb*nc+np.einsum('...i,...i->...',a,b)*nc+np.einsum('...i,...i->...',b,c)*na+np.einsum('...i,...i->...',c,a)*nb
    angles=2*np.arctan2(numerator,denominator)
    return np.all(np.abs(angles.sum(1))>3*np.pi)


def remove_internal_faces(node):
    faces=node['faces'];volumes=components(faces);remove=set()
    for i,face in enumerate(faces):
        pts=face[0]
        for group,tri,low,high in volumes:
            if i in group or np.any(pts.min(0)<=low+1e-5) or np.any(pts.max(0)>=high-1e-5):
                continue
            if not strictly_inside(pts,tri):continue
            # Inside vertices alone are insufficient for a concave volume: reject any
            # candidate whose edges/interior cross its actual enclosing triangles.
            candidate=triangles([(pts,face[1],face[2],False)])
            if len(candidate) and not intersect(candidate,tri,eps=1e-7):
                remove.add(i);break
    saved=sum(len(faces[i][0])-2 for i in remove)
    node['faces']=[face for i,face in enumerate(faces) if i not in remove]
    return saved


def finish_character(nodes):
    for name,node in nodes.items():
        added=close_planar_ends(node) if name.startswith(('Thigh','Shin')) else 0
        # Preserve all caps in independently moving joint pieces. Other solids may
        # lose fully buried faces only within their own rigid bone/transform.
        saved=0 if name.startswith(('UpperArm','Forearm','Thigh','Shin')) else remove_internal_faces(node)
        node['cleanup']={'added':added,'removed':saved}
    return nodes
