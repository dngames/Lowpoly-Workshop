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
