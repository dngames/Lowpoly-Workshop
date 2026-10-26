"""Closed organic limb shells for inexpensive, smoothly shaded characters."""
from collections import Counter
import numpy as np
from .mesh import Z, sweep


def closed_limb(m, points, radii, n=5, cells='skin', up=Z):
    """One shared ring through each elbow/knee, with both attachment ends capped.

    Recess the shoulder/hip root into the torso and overlap the wrist/ankle with
    the hand/shoe. Different segment colours share vertices rather than leaving
    an open sleeve. Five sides add only six triangles for the two end caps.
    Returns the limb shell's faces so a generator can check it independently of props.
    """
    if n < 3 or len(points) < 2:
        raise ValueError('A limb needs at least three sides and two path points')
    colours = [cells]*(len(points)-1) if isinstance(cells,str) else list(cells)
    if len(colours) != len(points)-1:
        raise ValueError('Supply one colour per limb segment')
    start = len(m.faces)
    sweep(m, points, radii, n=n, cell=colours[0], up=up, caps=(True,True), cell_fn=lambda i: colours[i])
    return m.faces[start:]


def closed_surface(faces):
    """Every polygon edge must have exactly two neighbours; ignore colour seams."""
    edges = Counter()
    for pts, *_ in faces:
        keys = [tuple(np.round(p,6)) for p in pts]
        if len(set(keys)) != len(keys):
            return False
        for a,b in zip(keys,keys[1:]+keys[:1]):
            edges[tuple(sorted((a,b)))] += 1
    return bool(edges) and all(count == 2 for count in edges.values())


def surface_orientation(faces):
    """Report closure, directed edge consistency and outward signed volume of one solid.

    Call before hidden-face cleanup, separately for each closed primitive. Deliberate cards
    and assembled overlapping solids need their own checks. Centring the integration keeps
    the result stable for a small object authored far from the world origin.
    """
    faces = list(faces)
    if not faces:
        return {"ok": False, "closed": False, "directed_edge_errors": 0, "signed_volume_m3": 0.0}
    points = np.concatenate([face[0] for face in faces])
    if not np.isfinite(points).all():
        return {"ok": False, "closed": False, "directed_edge_errors": 0, "signed_volume_m3": 0.0}
    origin = points.mean(axis=0)
    directed = Counter()
    volume = 0.0
    for pts, *_ in faces:
        keys = [tuple(np.round(p, 6)) for p in pts]
        for a, b in zip(keys, keys[1:] + keys[:1]):
            directed[tuple(sorted((a, b)))] += 1 if a < b else -1
        local = np.asarray(pts) - origin
        for i in range(1, len(local) - 1):
            volume += float(np.dot(local[0], np.cross(local[i], local[i + 1]))) / 6
    closed = closed_surface(faces)
    errors = sum(count != 0 for count in directed.values())
    scale = float(np.linalg.norm(np.ptp(points, axis=0)))
    epsilon = np.finfo(float).eps * scale ** 3 * 32
    return {"ok": bool(closed and not errors and volume > epsilon), "closed": bool(closed),
            "directed_edge_errors": int(errors), "signed_volume_m3": float(volume)}
