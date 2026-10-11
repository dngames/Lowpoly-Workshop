"""Surface-aware fitting for fringes, wearable roots and normal-aligned attachments."""
import numpy as np
from .kit.mesh import Mesh, nrm, loft

def project_rays(points, directions, triangles, offset=0.0):
    """Nearest positive ray hit; return fitted points, outward normals and distances.
    Directions point FROM the supplied points TOWARD the host shell. Missing hits fail.
    Triangle winding must be outward. Offset follows the host normal, not world up.
    """
    tri = np.asarray(triangles, float).reshape(-1, 3, 3)
    if not len(tri):
        raise ValueError("Empty projection host")
    pts = np.asarray(points, float).reshape(-1, 3)
    dirs = np.broadcast_to(np.asarray(directions, float), pts.shape).copy()
    lengths = np.linalg.norm(dirs, axis=1)
    if not np.isfinite(pts).all() or not np.isfinite(dirs).all() or np.any(lengths < 1e-12):
        raise ValueError("Projection needs finite points and nonzero directions")
    dirs /= lengths[:, None]
    a, e1, e2 = tri[:, 0], tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]
    result, normals, distances = [], [], []
    for point, direction in zip(pts, dirs):
        h = np.cross(direction, e2)
        det = np.einsum("ij,ij->i", e1, h)
        inv = np.divide(1., det, out=np.zeros_like(det), where=np.abs(det) > 1e-12)
        s = point - a
        u = np.einsum("ij,ij->i", s, h) * inv
        q = np.cross(s, e1)
        v = q @ direction * inv
        t = np.einsum("ij,ij->i", e2, q) * inv
        valid = (np.abs(det) > 1e-12) & (u >= -1e-8) & (v >= -1e-8) & (u + v <= 1 + 1e-8) & (t >= -1e-8)
        if not valid.any():
            raise ValueError(f"Surface ray misses host at {point.tolist()}")
        i = int(np.argmin(np.where(valid, t, np.inf)))
        normal = nrm(np.cross(e1[i], e2[i]))
        result.append(point + direction * t[i] + normal * offset)
        normals.append(normal)
        distances.append(float(t[i]))
    return np.asarray(result), np.asarray(normals), np.asarray(distances)

def wrapped_patch(m, rows, directions, host_triangles, cell, offset=.008, thickness=.012):
    """Closed fitted strip/patch. Rows share vertices; underside follows the same host.
    Suitable for a fringe, cuff or panel. Projection samples must surround the host;
    the strip does not invent missing coverage. All outer and inner perimeter edges close.
    """
    grid = np.asarray(rows, float)
    if grid.ndim != 3 or grid.shape[2] != 3 or min(grid.shape[:2]) < 2:
        raise ValueError("wrapped_patch needs at least a 2x2 sample grid")
    if thickness <= 0:
        raise ValueError("thickness must be positive")
    dirs = np.broadcast_to(np.asarray(directions, float), grid.shape)
    outer, normals, _ = project_rays(grid.reshape(-1, 3), dirs.reshape(-1, 3), host_triangles, offset)
    outer = outer.reshape(grid.shape)
    inner = (outer.reshape(-1, 3) - normals * thickness).reshape(grid.shape)
    for i in range(len(grid) - 1):
        for j in range(grid.shape[1] - 1):
            ix = [(i,j),(i,j+1),(i+1,j+1),(i+1,j)]
            top = np.asarray([outer[k] for k in ix])
            bottom = np.asarray([inner[k] for k in ix])
            m.face(top, cell, bottom.mean(0))
            m.face(bottom, cell, top.mean(0))
    boundary = ([(0,j) for j in range(grid.shape[1])] +
                [(i,grid.shape[1]-1) for i in range(1,len(grid))] +
                [(len(grid)-1,j) for j in range(grid.shape[1]-2,-1,-1)] +
                [(i,0) for i in range(len(grid)-2,0,-1)])
    centre = (outer.mean((0,1)) + inner.mean((0,1))) / 2
    for a,b in zip(boundary,boundary[1:]+boundary[:1]):
        m.face([outer[a],inner[a],inner[b],outer[b]],cell,centre)
    return outer, inner

def attachment_frame(normal, tangent=(1,0,0)):
    """Right-handed frame with local +Y along the actual host surface normal."""
    normal = np.asarray(normal, float)
    if normal.shape != (3,) or not np.isfinite(normal).all() or np.linalg.norm(normal) < 1e-12:
        raise ValueError("Attachment needs a finite nonzero normal")
    y = nrm(normal)
    x = np.asarray(tangent, float) - y * np.dot(tangent,y)
    if np.linalg.norm(x) < 1e-8:
        seed = np.eye(3)[np.argmin(np.abs(y))]
        x = seed - y * np.dot(seed,y)
    x = nrm(x)
    return np.column_stack((x,y,np.cross(x,y)))

def closest_points(points, triangles):
    """Closest points on triangle interiors or edges, with distances (no spatial approximation)."""
    tri = np.asarray(triangles, float).reshape(-1,3,3)
    if not len(tri):
        raise ValueError("Empty surface")
    a,b,c = tri[:,0],tri[:,1],tri[:,2]
    ab,ac=b-a,c-a
    d00=np.einsum("ij,ij->i",ab,ab);d01=np.einsum("ij,ij->i",ab,ac);d11=np.einsum("ij,ij->i",ac,ac)
    denom=d00*d11-d01*d01
    output=[];distance=[]
    for p in np.asarray(points,float).reshape(-1,3):
        ap=p-a;d20=np.einsum("ij,ij->i",ap,ab);d21=np.einsum("ij,ij->i",ap,ac)
        v=np.divide(d11*d20-d01*d21,denom,out=np.zeros_like(denom),where=np.abs(denom)>1e-18)
        w=np.divide(d00*d21-d01*d20,denom,out=np.zeros_like(denom),where=np.abs(denom)>1e-18)
        face=a+v[:,None]*ab+w[:,None]*ac
        ds=np.linalg.norm(face-p,axis=1)
        ds[(v<0)|(w<0)|(v+w>1)|(np.abs(denom)<1e-18)]=np.inf
        candidates=[face];distances=[ds]
        for u,z in ((a,b),(b,c),(c,a)):
            edge=z-u;length=np.einsum("ij,ij->i",edge,edge)
            t=np.clip(np.divide(np.einsum("ij,ij->i",p-u,edge),length,out=np.zeros_like(length),where=length>1e-18),0,1)
            q=u+t[:,None]*edge
            candidates.append(q);distances.append(np.linalg.norm(q-p,axis=1))
        ds=np.stack(distances)
        i,j=np.unravel_index(ds.argmin(),ds.shape)
        output.append(candidates[i][j]);distance.append(ds[i,j])
    return np.asarray(output),np.asarray(distance)
