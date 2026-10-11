"""Rigid node hierarchies: pose them by rotating nodes about their pivots, solve simple two-bone IK.

A pose is {node: [rx, ry, rz] degrees (XYZ Euler) or a 3x3 matrix}, applied about the node's pivot in
world-aligned axes, relative to its parent's posed frame; "_root_t" translates the roots and "_root_r"
rotates them, "_root_for" limits both to the named roots (a rider's seat offset must not move the bike it
sits on). Nodes keep their faces in world rest coordinates, so a posed node is R x + t.
"""
import math

import numpy as np


def euler(r):
    rx, ry, rz = (math.radians(a) for a in r)
    cx, sx, cy, sy, cz, sz = math.cos(rx), math.sin(rx), math.cos(ry), math.sin(ry), math.cos(rz), math.sin(rz)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return Rz @ Ry @ Rx


def world_transforms(nodes, pose):
    """(R, t) per node so that a rest-pose world point x maps to R x + t."""
    out = {}
    rr = pose.get("_root_r", (0, 0, 0))
    root_R = np.asarray(rr, float) if np.ndim(rr) == 2 else euler(rr)
    root_t = np.asarray(pose.get("_root_t", (0, 0, 0)), float)

    def get(name):
        if name in out:
            return out[name]
        nd = nodes[name]
        pv = nd["pivot"]
        v = pose.get(name, (0, 0, 0))
        R = np.asarray(v, float) if np.ndim(v) == 2 else euler(v)
        lt = pv - R @ pv
        if nd["parent"] and nd["parent"] in nodes:
            PR, Pt = get(nd["parent"])
        elif "_root_for" in pose and name not in pose["_root_for"]:
            PR, Pt = np.eye(3), np.zeros(3)
        else:
            PR, Pt = root_R, root_t
        out[name] = (PR @ R, PR @ lt + Pt)
        return out[name]
    for n in nodes:
        get(n)
    return out


def posed_triangles(nodes, pose, skip=(), uv_fn=None):
    """Posed triangle soup; with uv_fn(pts, cell, uv) also returns per-corner UVs.

    A node carrying its own "atlas" (an Atlas) uses that atlas's face_uvs instead of uv_fn."""
    tf = world_transforms(nodes, pose)
    tris, cells, uvs = [], [], []
    for name, nd in nodes.items():
        if name in skip or pose.get("_hide_" + name):
            continue
        R, t = tf[name]
        for pts, cell, uv, thin in nd["faces"]:
            q = pts @ R.T + t
            fn = nd["atlas"].face_uvs if (uv_fn and nd.get("atlas") is not None) else uv_fn
            fu = fn(pts, cell, uv) if fn else None
            for i in range(1, len(q) - 1):
                tris.append([q[0], q[i], q[i + 1]])
                cells.append(cell)
                if fu:
                    uvs.append([fu[0], fu[i], fu[i + 1]])
    if uv_fn:
        return np.array(tris), cells, np.array(uvs)
    return np.array(tris), cells


def rot_between(a, b):
    a, b = a / np.linalg.norm(a), b / np.linalg.norm(b)
    v = np.cross(a, b)
    c = float(np.dot(a, b))
    if np.linalg.norm(v) < 1e-9:
        return np.eye(3) if c > 0 else -np.eye(3)
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + K + K @ K * (1 / (1 + c))


def frame_rot(b0, h0, b1, h1):
    """Rotation taking bone direction b0 to b1 while the hinge axis h0 goes to h1."""
    def frame(b, h):
        b = b / np.linalg.norm(b)
        h = h - np.dot(h, b) * b
        h = h / np.linalg.norm(h)
        return np.stack([b, h, np.cross(b, h)], 1)
    return frame(b1, h1) @ frame(b0, h0).T


def rx(deg):
    t = math.radians(deg)
    return np.array([[1, 0, 0], [0, math.cos(t), -math.sin(t)], [0, math.sin(t), math.cos(t)]])


def two_bone(A, B, C, T, pole):
    """New mid joint for chain A-B-C reaching T (lengths kept), bent towards pole."""
    l1, l2 = np.linalg.norm(B - A), np.linalg.norm(C - B)
    d = T - A
    L = np.linalg.norm(d)
    L = min(max(L, abs(l1 - l2) + 1e-4), l1 + l2 - 1e-4)
    dn = d / np.linalg.norm(d)
    a = (l1 * l1 - l2 * l2 + L * L) / (2 * L)
    h = math.sqrt(max(l1 * l1 - a * a, 0.0))
    p = pole - np.dot(pole, dn) * dn
    p = p / (np.linalg.norm(p) + 1e-12)
    return A + dn * a + p * h, A + dn * L


def rot(axis, deg):
    """Rotation matrix about an arbitrary axis (degrees)."""
    a = np.asarray(axis, float)
    a = a / np.linalg.norm(a)
    t = math.radians(deg)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(t) * K + (1 - math.cos(t)) * K @ K
