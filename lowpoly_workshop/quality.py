"""Generic mesh, contact and texture checks. Intent is declared, never inferred from a name."""
from collections import Counter
import numpy as np
from .surface import closest_points,project_rays
from .kit.glb import intersect
from .kit import rig

def topology(triangles, precision=6):
    tri=np.asarray(triangles,float).reshape(-1,3,3)
    edges=Counter();directed=Counter();seen=set();duplicates=0;degenerate=0
    for q in tri:
        keys=[tuple(np.round(v,precision)) for v in q]
        if len(set(keys))<3 or np.linalg.norm(np.cross(q[1]-q[0],q[2]-q[0]))<1e-10:
            degenerate+=1;continue
        face=tuple(sorted(keys))
        duplicates+=face in seen;seen.add(face)
        for a,b in zip(keys,keys[1:]+keys[:1]):
            edges[tuple(sorted((a,b)))]+=1;directed[(a,b)]+=1
    return dict(finite=bool(np.isfinite(tri).all()),triangles=len(tri),
        boundary_edges=sum(v==1 for v in edges.values()),
        nonmanifold_edges=sum(v>2 for v in edges.values()),
        winding_edges=sum(v==2 and (directed[e]!=1 or directed[(e[1],e[0])]!=1) for e,v in edges.items()),
        duplicates=int(duplicates),degenerate=degenerate)

def inside(points,tri):
    tri=np.asarray(tri,float)
    out=[]
    for p in np.asarray(points,float):
        a,b,c=tri[:,0]-p,tri[:,1]-p,tri[:,2]-p
        la,lb,lc=[np.linalg.norm(v,axis=1) for v in (a,b,c)]
        num=np.einsum("ij,ij->i",a,np.cross(b,c))
        den=la*lb*lc+np.einsum("ij,ij->i",a,b)*lc+np.einsum("ij,ij->i",b,c)*la+np.einsum("ij,ij->i",c,a)*lb
        out.append(abs((2*np.arctan2(num,den)).sum())>3*np.pi)
    return np.asarray(out)

def samples(tri,limit=128):
    q=np.concatenate((tri.reshape(-1,3),tri.mean(1)))
    q=np.unique(np.round(q,7),axis=0)
    return q[np.linspace(0,len(q)-1,min(limit,len(q)),dtype=int)] if len(q) else q

def relation_result(relation,geo):
    kind=relation["type"];a,b=relation["a"],relation["b"]
    if a not in geo or b not in geo:
        return False,{"reason":"missing relation node","nodes":[a,b]}
    ta,tb=geo[a],geo[b]
    if not len(ta) or not len(tb):
        return False,{"reason":"relation requires mesh surfaces"}
    if kind in ("fit","support"):
        try:
            # Distances measured from the explicit samples to the host, along declared rays.
            _,_,dist=project_rays(relation["samples"],relation["direction"],tb)
        except ValueError as e:
            return False,{"reason":str(e)}
        low,high=relation.get("min",0.),relation.get("max",.02)
        return bool(np.all((dist>=low-1e-7)&(dist<=high+1e-7))),{"min_distance":float(dist.min()),"max_distance":float(dist.max()),"allowed":[low,high]}
    sa,sb=samples(ta),samples(tb)
    _,da=closest_points(sa,tb);_,db=closest_points(sb,ta)
    crossings=intersect(ta,tb)
    # Containment counts only for closed, consistently wound hosts.
    ina=inside(sa,tb) if all(topology(tb)[k]==0 for k in ("boundary_edges","nonmanifold_edges","winding_edges")) else np.zeros(len(sa),bool)
    inb=inside(sb,ta) if all(topology(ta)[k]==0 for k in ("boundary_edges","nonmanifold_edges","winding_edges")) else np.zeros(len(sb),bool)
    gap=float(min(da.min(),db.min()))
    if kind=="clear":
        okay=not crossings and not ina.any() and not inb.any() and gap+1e-7>=relation.get("min_gap",0.)
        return bool(okay),{"crossings":crossings,"contained_samples":int(ina.sum()+inb.sum()),"min_gap":gap}
    fraction=max(float(np.mean(ina|(da<=relation.get("max_gap",.003)))),float(np.mean(inb|(db<=relation.get("max_gap",.003)))))
    okay=(crossings>0 or fraction>0) and fraction>=relation.get("min_fraction",0.)
    return bool(okay),{"crossings":crossings,"contact_fraction":fraction,"min_gap":gap}

def check_relations(nodes,relations,poses,report):
    from .kit.mesh import triangles
    for pose_name,pose in {"rest":{},**poses}.items():
        tf=rig.world_transforms(nodes,pose)
        geo={}
        for name,nd in nodes.items():
            tris,_,_=triangles({name:nd});tris=tris.reshape(-1,3,3);r,t=tf[name]
            geo[name]=tris@r.T+t
        for rel in relations:
            if rel.get("poses") and pose_name not in rel["poses"]:
                continue
            moved=dict(rel)
            if "samples" in rel:
                # Samples are authored on node a in rest world coordinates.
                r,t=tf[rel["a"]]
                moved["samples"]=(np.asarray(rel["samples"])@r.T+t).tolist()
                moved["direction"]=(r@np.asarray(rel["direction"])).tolist()
            okay,detail=relation_result(moved,geo)
            report(okay,f"{rel['type']}: {rel['a']} / {rel['b']} at {pose_name}",str(detail))

def uv_diagnostics(nodes,atlas):
    issues=[]
    layout=atlas.layout()
    rects=list(layout.items())
    for i,(a,ra) in enumerate(rects):
        for b,rb in rects[i+1:]:
            if min(ra[2],rb[2])>max(ra[0],rb[0]) and min(ra[3],rb[3])>max(ra[1],rb[1]):
                issues.append({"type":"atlas_overlap","cells":[a,b]})
    for name,nd in nodes.items():
        for pts,cell,uv,thin in nd["faces"]:
            if uv is None or not atlas.cells[cell][2]:
                continue
            pts=np.asarray(pts);uv=np.asarray(uv)
            for k in range(1,len(pts)-1):
                ix=[0,k,k+1]
                area=np.linalg.norm(np.cross(pts[ix[1]]-pts[ix[0]],pts[ix[2]]-pts[ix[0]]))
                uvarea=abs(np.linalg.det(np.stack([uv[ix[1]]-uv[ix[0]],uv[ix[2]]-uv[ix[0]]])))
                if area>1e-10 and uvarea<1e-8:
                    issues.append({"type":"collapsed_decal_uv","node":name,"cell":cell})
                rules=nd.get("decal_regions",{}).get(cell,{})
                if area>1e-10 and uvarea>1e-8 and rules.get("max_anisotropy"):
                    e1=pts[ix[1]]-pts[ix[0]];e2=pts[ix[2]]-pts[ix[0]]
                    u=e1/np.linalg.norm(e1);v=e2-u*np.dot(e2,u);v/=np.linalg.norm(v)
                    geometry=np.array([[np.dot(e1,u),np.dot(e2,u)],[np.dot(e1,v),np.dot(e2,v)]])
                    coords=(uv[ix[1:]]-uv[ix[0]]).T
                    singular=np.linalg.svd(coords@np.linalg.inv(geometry),compute_uv=False)
                    ratio=float(singular.max()/singular.min())
                    if ratio>rules["max_anisotropy"]:issues.append({"type":"stretched_decal_uv","node":name,"cell":cell,"anisotropy":ratio})
                normal=np.cross(pts[ix[1]]-pts[ix[0]],pts[ix[2]]-pts[ix[0]])
                rules=nd.get("decal_regions",{}).get(cell)
                if rules and "normal" in rules and np.dot(normal/max(np.linalg.norm(normal),1e-12),rules["normal"])<rules.get("min_dot",.3):
                    issues.append({"type":"decal_wrong_surface","node":name,"cell":cell})
    return issues
