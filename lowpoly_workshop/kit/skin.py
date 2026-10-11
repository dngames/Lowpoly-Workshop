"""Skin weights for a rigid-part character: each vertex follows the bones near it, blended across joints.

A generator's skin(nodes, p) hook returns
    {"bones": [{"name", "parent", "head", "tail"}, ...],   # rest pose, glTF world metres, parents first
     "bind": {node: [bone, ...]},                           # bones a node's vertices may follow
     "rigid": {node: bone},                                 # nodes that follow exactly one bone (a helmet)
     "sigma": 0.05}                                         # blend width in metres
Weights fall off with the distance from a vertex to each bone's segment: a vertex on a forearm follows
the forearm, and one near the elbow follows both bones in proportion. That bend is what closes the
elbow and knee gaps that rigid parts leave at a joint.
"""
import numpy as np

MAX_INFLUENCES = 4


def segment_distance(points, a, b):
    """Distance from each point (n, 3) to the segment a-b."""
    ab = np.asarray(b, float) - np.asarray(a, float)
    t = np.clip(((points - a) @ ab) / max(float(ab @ ab), 1e-12), 0.0, 1.0)
    return np.linalg.norm(points - (a + t[:, None] * ab), axis=1)


def bone_segments(spec):
    """{name: (head, tail)} for every bone in the spec, as float arrays."""
    return {b["name"]: (np.asarray(b["head"], float), np.asarray(b["tail"], float)) for b in spec["bones"]}


def vertex_weights(points, candidates, segments, sigma):
    """Per point: up to MAX_INFLUENCES (bone, weight) pairs that sum to 1.

    points: (n, 3) float array; candidates: bone names; segments: bone_segments(spec).
    """
    if not candidates or sigma <= 0 or not np.isfinite(sigma):
        raise ValueError("Weights need candidate bones and a positive finite sigma")
    if len(candidates) == 1:
        return [[(candidates[0], 1.0)] for _ in range(len(points))]
    d = np.stack([segment_distance(points, *segments[c]) for c in candidates], axis=1)
    logw = -((d / sigma) ** 2)
    w = np.exp(logw - logw.max(axis=1, keepdims=True))
    w /= w.sum(axis=1, keepdims=True)
    out = []
    for row in w:
        order = np.argsort(-row)[:MAX_INFLUENCES]
        kept = row[order]
        kept = kept / kept.sum()
        out.append([(candidates[i], float(k)) for i, k in zip(order, kept) if k > 0])
    return out


def validate(spec):
    """Raise on a spec the exporter cannot write: unknown parents, candidates or rigid bones."""
    names = [b["name"] for b in spec["bones"]]
    if len(set(names)) != len(names):
        raise ValueError("duplicate bone names in skin spec")
    known = set(names)
    for b in spec["bones"]:
        if b.get("parent") is not None and b["parent"] not in known:
            raise ValueError("bone %s has unknown parent %s" % (b["name"], b["parent"]))
    for node, cands in spec["bind"].items():
        for c in cands:
            if c not in known:
                raise ValueError("node %s binds to unknown bone %s" % (node, c))
    for node, bone in spec.get("rigid", {}).items():
        if bone not in known:
            raise ValueError("node %s is rigid to unknown bone %s" % (node, bone))
