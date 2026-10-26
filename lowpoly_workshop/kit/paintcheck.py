"""Best-view paint check: does every face's painted cell agree with the sheet where the sheet shows
that face best?

For each sheet set, through the fitted cameras (`cams/<set>/<view>.json`, from `fit`):
- render a face-id buffer per view; a face's best view is the one where it covers the most pixels
  (projected area after occlusion, so a face seen edge-on or hidden loses to one seen square on);
- in its best view, the face's sheet pixels vote for a sheet class (background doesn't vote; ink
  lines vote as the sheet's line class, which is usually the dark one); faces no view sees (undersides, insides) take the majority class of their seen
  neighbours, spreading across shared edges;
- a face disagrees when its painted cell's class (`cell_class`) is not the class the sheet gives it.

A report for review, not a repaint: drawings contradict themselves between views and small
features fall between pixels, so read each flagged face against the sheet. Writes
out/paint/report.json (summary, per node, every flagged face) and out/paint/<set>_<view>.png (the
model through that view's camera, faces whose best view it is and that disagree in magenta).
"""
import os
from collections import Counter, defaultdict

import numpy as np
from PIL import Image

from . import raster as rs
from . import rig
from .atomic import write_json
from .camfit import ViewFit, make_cam

MIN_PIXELS = 6  # a face needs this many visible pixels for a view to judge it
MIN_INNER = 3  # with this many interior pixels, only they vote
AGREE = 0.5  # share of a face's votes its painted class needs to pass
FLAG = np.array((236, 0, 140), float)


def keyed_triangles(nodes, pose):
    """Posed triangles with a stable key each, (node, face, fan index): the same face keeps its key
    in every view, even where a pose hides other nodes."""
    tf = rig.world_transforms(nodes, pose)
    tris, cells, keys = [], [], []
    for name, nd in nodes.items():
        if pose.get("_hide_" + name):
            continue
        R, t = tf[name]
        for fi, (pts, cell, _uv, _thin) in enumerate(nd["faces"]):
            q = pts @ R.T + t
            for i in range(1, len(q) - 1):
                tris.append([q[0], q[i], q[i + 1]])
                cells.append(cell)
                keys.append((name, fi, i - 1))
    return np.array(tris), cells, keys


def face_ids(tris, cam, W, H):
    """Per pixel the index of the nearest triangle, −1 for none."""
    n = len(tris)
    ids = list(range(n))
    _, cm, _ = rs.render(tris, ids, cam, W, H, shade=False, palette={i: (0.0, 0.0, 0.0) for i in ids},
                         classes={i: i + 1 for i in ids})
    return cm - 1


def _neighbours(rest):
    """Faces sharing an edge (vertices welded at 0.1 mm), from their rest positions."""
    vid = {}
    edges = defaultdict(set)
    for key, tri in rest.items():
        ids = [vid.setdefault(tuple(np.round(p, 4)), len(vid)) for p in tri]
        for a, b in ((0, 1), (1, 2), (2, 0)):
            edges[frozenset((ids[a], ids[b]))].add(key)
    out = defaultdict(set)
    for faces in edges.values():
        for f in faces:
            out[f] |= faces - {f}
    return out


def check_set(asset, set_name):
    views = [v for v in asset.views(set_name) if asset.cam(set_name, v)]
    if not views:
        return None
    cell_cls = asset.cell_classes()
    default = cell_cls.get("_default", 1)
    best = {}  # key -> (pixels, view, votes Counter)
    painted = {}
    rest = {}
    renders = {}
    for view in views:
        vf = ViewFit(asset, set_name, view)
        v = np.array(asset.cam(set_name, view)["cam"], float)
        nodes, pose = asset.scene(set_name, view, v[7:])
        T, C, K = keyed_triangles(nodes, pose)
        H, W = vf.cls.shape
        cam = make_cam(v, vf.target)
        ids = face_ids(T, cam, W, H)
        renders[view] = (T, C, K, cam, ids, vf, nodes)
        flat = ids.ravel()
        sheet = vf.cls.ravel()
        # Interior pixels (all four neighbours on the same face): a face's outline is where the
        # sheet's ink lines run, which would outvote a thin face's paint.
        inner = np.ones_like(ids, bool)
        inner[1:, :] &= ids[1:, :] == ids[:-1, :]
        inner[:-1, :] &= ids[:-1, :] == ids[1:, :]
        inner[:, 1:] &= ids[:, 1:] == ids[:, :-1]
        inner[:, :-1] &= ids[:, :-1] == ids[:, 1:]
        inner = inner.ravel()
        for t in np.unique(flat[flat >= 0]):
            px = flat == t
            key = K[t]
            painted[key] = C[t]
            rest.setdefault(key, T[t])
            n = int(px.sum())
            if n >= MIN_PIXELS and n > best.get(key, (0,))[0]:
                use = px & inner if (px & inner).sum() >= MIN_INNER else px
                votes = Counter(int(c) for c in sheet[use] if c != 0)
                if votes:
                    best[key] = (n, view, votes)
        for t, key in enumerate(K):
            painted.setdefault(key, C[t])
            rest.setdefault(key, T[t])

    # The sheet's class per face: its best view's majority, or its seen neighbours'.
    sheet_cls = {k: b[2].most_common(1)[0][0] for k, b in best.items()}
    share = {k: b[2][cell_cls.get(painted[k], default)] / sum(b[2].values()) for k, b in best.items()}
    inferred = set()
    near = _neighbours(rest)
    frontier = [k for k in painted if k not in sheet_cls]
    while frontier:
        nxt = []
        got = {}
        for k in frontier:
            votes = Counter(sheet_cls[n] for n in near.get(k, ()) if n in sheet_cls)
            if votes:
                got[k] = votes.most_common(1)[0][0]
            else:
                nxt.append(k)
        if not got:
            break
        sheet_cls.update(got)
        inferred |= set(got)
        frontier = nxt

    flagged = []
    for k, cell in painted.items():
        if k not in sheet_cls:
            continue
        mine = cell_cls.get(cell, default)
        if mine == sheet_cls[k]:
            continue
        if k in share and share[k] >= AGREE:
            continue
        flagged.append({
            "node": k[0], "face": k[1], "triangle": k[2], "cell": cell,
            "painted_class": mine, "sheet_class": sheet_cls[k],
            "view": best[k][1] if k in best else None,
            "agreement": round(share.get(k, 0.0), 3), "inferred": k in inferred,
        })

    # One image per view: the model, the faces it judged and found disagreeing in magenta.
    bad = {(f["node"], f["face"], f["triangle"]) for f in flagged}
    os.makedirs(asset.out("paint"), exist_ok=True)
    for view, (T, C, K, cam, ids, vf, nodes) in renders.items():
        pal = asset.palette(nodes)
        img, cm, _ = rs.render(T, C, cam, ids.shape[1], ids.shape[0], palette=pal, classes=asset.cell_classes())
        for t, key in enumerate(K):
            if key in bad and best.get(key, (0, None))[1] == view:
                img[ids == t] = FLAG
        bg = np.median(np.concatenate([vf.img[0], vf.img[-1]]), 0)
        img = np.where((cm > 0)[..., None], img, bg).astype(np.uint8)
        Image.fromarray(np.concatenate([vf.img, img], 1)).save(asset.out("paint", "%s_%s.png" % (set_name, view)))

    per_node = defaultdict(lambda: {"faces": 0, "judged": 0, "inferred": 0, "unseen": 0, "flagged": 0})
    for k in painted:
        row = per_node[k[0]]
        row["faces"] += 1
        row["judged"] += k in best
        row["inferred"] += k in inferred
        row["unseen"] += k not in sheet_cls
    for f in flagged:
        per_node[f["node"]]["flagged"] += 1
    return {"views": views, "faces": len(painted), "judged": len(best), "inferred": len(inferred),
            "unseen": len(painted) - len(sheet_cls), "flagged": len(flagged),
            "flagged_judged": sum(not f["inferred"] for f in flagged),
            "flagged_inferred": sum(f["inferred"] for f in flagged),
            "nodes": dict(per_node), "faces_flagged": flagged}


def run(folder):
    from .asset import Asset
    a = Asset(folder)
    names = a.class_names()
    report = {}
    for set_name in a.sets():
        r = check_set(a, set_name)
        if r is None:
            print("%-14s no fitted cameras: run fit first" % set_name)
            continue
        report[set_name] = r
        print("%-14s %d faces: %d judged in their best view, %d from neighbours, %d unseen; "
              "%d disagree (%d judged, %d from neighbours)"
              % (set_name, r["faces"], r["judged"], r["inferred"], r["unseen"], r["flagged"],
                 r["flagged_judged"], r["flagged_inferred"]))
        for node, row in sorted(r["nodes"].items()):
            if row["flagged"]:
                print("    %-20s %d of %d faces" % (node, row["flagged"], row["faces"]))
        for f in r["faces_flagged"]:
            f["painted_name"] = names.get(f["painted_class"], "c%d" % f["painted_class"])
            f["sheet_name"] = names.get(f["sheet_class"], "c%d" % f["sheet_class"])
    write_json(a.out("paint", "report.json"), report, indent=1)
    return report
