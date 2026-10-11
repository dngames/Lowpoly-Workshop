"""Contract checks on the exported GLBs, driven by the "contract" block of each output in asset.json.

Every output gets: node names and parents, pivots against the generator (and against an explicit
table when the contract has one), rest rotations, unit scale, triangle budget, one material with an
embedded square atlas, a kit mask with only black/R/G/B, the kitMask extra, no cameras/lights/skins.
Optional per-output checks:
    "ground": [nodes]            lowest vertex of each at y = 0
    "sweep": {...}               move joints through their ranges; listed node pairs must never intersect
    "attach": {...}              this file attached to a node of another output clears listed nodes
    "budget": 3000               triangle budget
A gen.py may add its own checks with extra_checks(asset, report) (e.g. a rider's clip on a bike).
"""
import itertools
from pathlib import Path
import os
import random

import numpy as np
from PIL import Image

from . import glb as G
from .asset import Asset

TOL = 0.005


class Report:
    def __init__(self):
        self.results = []
        self.rows = []

    def __call__(self, ok, what, detail=""):
        self.results.append(bool(ok))
        self.rows.append({"ok": bool(ok), "text": what, "detail": detail})
        print("%s  %s%s" % ("PASS" if ok else "FAIL", what, ("  -- " + detail) if detail else ""), flush=True)

    @property
    def ok(self):
        return all(self.results)


def node_tris(g, loc=None):
    geo, W = g.posed(loc if loc is not None else g.sample())
    return geo, W


def check_output(a, out, report):
    path = a.path(out["file"])
    tag = os.path.basename(path)
    from lowpoly_workshop.spec import load_profile
    c = {**load_profile(a.spec.get("profile", "portable")), **out.get("contract", {})}
    tolerance = c.get("pivot_tolerance", TOL)
    if not os.path.exists(path):
        report(False, "%s exists" % tag)
        return
    g = G.Glb(path)
    print("== %s (%.1f KB)" % (out["file"], os.path.getsize(path) / 1024))
    nodes = a.build(out.get("variant"), out.get("scale", 1.0))
    want = [n for n in nodes if n in out.get("nodes", list(nodes)) and n not in out.get("exclude", [])]
    mesh_nodes = [n.get("name") for n in g.nodes if "mesh" in n]
    want_meshes = [n for n in want if nodes[n]["faces"]]
    par = {n.get("name"): (g.names[g.parent[i]] if i in g.parent else None)
           for i, n in enumerate(g.nodes)}
    exp_par = {n: (nodes[n]["parent"] if nodes[n]["parent"] in want else None) for n in want}
    extra = [k for k in ("cameras", "lights", "skins") if g.js.get(k)]
    report(sorted(g.names) == sorted(want) and sorted(mesh_nodes) == sorted(want_meshes)
           and all(par.get(n) == exp_par[n] for n in want) and not extra,
           "%s: %d named nodes with the generator's parents and mesh/empty types, nothing else" % (tag, len(want)),
           "file %s, meshes %s, extra %s" % (sorted(g.names), sorted(mesh_nodes), extra))
    # pivots and rest rotations (world), relative to an optional origin node of another output
    rest = g.sample()
    geo, W = g.posed(rest)
    origin = np.zeros(3)
    if out.get("origin"):
        origin = nodes[out["origin"]]["pivot"]
    worst, bad = 0.0, []
    table = c.get("pivots", {})
    for n in want:
        R, T = W[g.names.index(n)]
        exp = np.asarray(table.get(n, nodes[n]["pivot"] - origin), float)
        worst = max(worst, np.abs(T - exp).max(), np.abs(T - (nodes[n]["pivot"] - origin)).max())
        if np.abs(R - nodes[n]["rot"]).max() > 1e-4:
            bad.append(n)
        sc = g.nodes[g.names.index(n)].get("scale", [1, 1, 1])
        if np.abs(np.array(sc) - 1).max() > 1e-6:
            bad.append(n + "(scale)")
    raked = [n for n in want if np.abs(nodes[n]["rot"] - np.eye(3)).max() > 1e-6]
    report(worst <= tolerance and not bad, "%s: pivots within configured tolerance, rest rotations %s, scale 1" % (
        tag, "identity" if not raked else "identity except " + "/".join(raked)),
        "worst %.2f mm, wrong %s" % (worst * 1000, bad))
    # Compare exported vertex surfaces with the generator, independent of Blender.
    from scipy.spatial import cKDTree
    from .mesh import triangles
    for n in want_meshes:
        expected=triangles({n:nodes[n]})[0].reshape(-1,3)-origin
        actual=geo[n].reshape(-1,3)
        error=max(float(cKDTree(expected).query(actual)[0].max()),float(cKDTree(actual).query(expected)[0].max())) if len(actual) else float('inf')
        report(error<=1e-5,f"{tag}: {n} geometry survives export",f"max surface vertex error {error:.8f}m")
    if out.get("clips") and hasattr(a.gen,"clips"):
        expected_clips=set(a.gen.clips(nodes,a.params(out.get("variant"))))
        actual_clips={clip.get('name') for clip in g.js.get('animations',[])}
        report(expected_clips<=actual_clips,f"{tag}: expected animation clips survive export",str(sorted(actual_clips)))
    # budget
    tris = {n: len(geo[n]) if n in want_meshes else 0 for n in want}
    budget = c.get("budget")
    if budget:
        report(sum(tris.values()) <= budget, "%s: %d triangles <= %d" % (tag, sum(tris.values()), budget),
               ", ".join("%s %d" % kv for kv in tris.items()))
    # material, atlas, kit mask
    imgs = g.images()
    kit_name = out.get("kit_mask")
    ok = len(g.js.get("materials", [])) <= c.get("max_materials", 1) and bool(imgs)
    if c.get("square_atlas", True):
        ok = ok and all(im.width == im.height for im in imgs)
    detail = "atlas %s" % str(imgs[0].size if imgs else None)
    if kit_name:
        kp = os.path.join(os.path.dirname(path), kit_name)
        k = Image.open(kp).convert("RGBA")
        mask_channels = c.get("mask_channels", "RGB")
        arr = np.asarray(k) if mask_channels == "RGBA" else np.asarray(k)[:,:,:3]
        uniq = {tuple(x) for x in np.unique(arr.reshape(-1, arr.shape[-1]), axis=0)}
        ex = g.js["materials"][0].get("extras", {})
        ok = ok and k.size == imgs[0].size and uniq <= ({(0,0,0,0),(255,0,0,0),(0,255,0,0),(0,0,255,0),(0,0,0,255)} if mask_channels == "RGBA" else {(0,0,0),(255,0,0),(0,255,0),(0,0,255)}) \
            and ex.get("kitMask") == kit_name
        detail += ", kit %s colours %s, kitMask %s" % (k.size, sorted(uniq), ex.get("kitMask"))
    report(ok, "%s: configured material/atlas policy%s" % (tag, ", exclusive kit mask channels" if kit_name else ""),
           detail)
    # ground contact
    for n in c.get("ground", []):
        lo = geo[n].reshape(-1, 3)[:, 1].min()
        report(abs(lo) <= tolerance, "%s: %s touches y = 0" % (tag, n), "lowest y %+.4f" % lo)
    from lowpoly_workshop.quality import topology
    for name in c.get("closed", []):
        stats = topology(geo.get(name, np.empty((0,3,3))))
        report(stats["triangles"] > 0 and stats["finite"] and not any(stats[k] for k in ("boundary_edges","nonmanifold_edges","winding_edges","duplicates","degenerate")), f"{tag}: {name} closed solid", str(stats))
    if c.get("sweep"):
        sweep(g, c["sweep"], report, tag)
    if c.get("attach"):
        attach(a, g, c["attach"], report, tag)


def sweep(g, sw, report, tag):
    """Rotate joints about their local axes over sampled combinations; test the listed pairs."""
    joints = sw["joints"]               # {node: {"axis": "x", "angles": [...]}}
    follow = sw.get("counter", {})      # {node: joint}: rotates by minus that joint's angle (level pedals)
    pairs = sw["pairs"]
    rest = g.sample()
    names = list(joints)
    combos = list(itertools.product(*[joints[n]["angles"] for n in names]))
    random.Random(1).shuffle(combos)
    combos = combos[:sw.get("samples", 300)]
    for n in names:                     # every joint's extremes alone as well
        for ang in (min(joints[n]["angles"]), max(joints[n]["angles"])):
            combos.append(tuple(ang if m == n else 0.0 for m in names))
    axis = {"x": (1, 0, 0), "y": (0, 1, 0), "z": (0, 0, 1)}
    hits = {}
    for combo in combos:
        loc = {i: [R.copy(), T.copy()] for i, (R, T) in rest.items()}
        ang = dict(zip(names, combo))
        for n, d in ang.items():
            i = g.names.index(n)
            loc[i][0] = rest[i][0] @ G.rot_mat(axis[joints[n]["axis"]], d)
        for n, j in follow.items():
            i = g.names.index(n)
            loc[i][0] = rest[i][0] @ G.rot_mat(axis[joints[j]["axis"]], -ang[j])
        geo, _ = g.posed(loc)
        for p, q in pairs:
            if G.intersect(geo[p], geo[q]):
                hits.setdefault((p, q), combo)
    report(not hits, "%s: joints swept through %d poses, listed pairs never intersect" % (tag, len(combos)),
           "clean" if not hits else "; ".join("%s x %s e.g. at %s" % (p, q, dict(zip(names, c)))
                                              for (p, q), c in hits.items()))


def attach(a, g, at, report, tag):
    """This file parented (identity) to a node of another output; shell clears nodes, _THIN parts may touch."""
    host = G.Glb(a.path(at["file"]))
    geo, W = host.posed(host.sample())
    R, T = W[host.names.index(at["node"])]
    i = 0
    for k, n in enumerate(g.nodes):
        if "mesh" in n:
            i = k
    tri = g.local_geo(i) @ R.T + T
    thin = g.thin_mask(i)
    clash = {n: G.intersect(tri[~thin], geo[n]) for n in at["clear"] if n in geo}
    touch = {n: G.intersect(tri[thin], geo[n]) for n in at["clear"] if n in geo}
    report(not any(clash.values()), "%s: attached to %s it clears %s" % (tag, at["node"], ", ".join(at["clear"])),
           "solid parts intersecting %s; thin parts touching %s" % (clash, touch))


def run(folder):
    a = Asset(folder)
    report = Report()
    for out in a.outputs():
        check_output(a, out, report)
    for feature in a.spec.get('features', []):
        path=Path(a.path(feature['output']))
        if not path.exists():
            report(False, 'Feature '+feature['id']+': export exists');continue
        g=G.Glb(path)
        present=set(g.names)
        meshes={n.get('name') for n in g.nodes if 'mesh' in n}
        okay=set(feature['nodes'])<=present and bool(set(feature['nodes']) & meshes)
        report(okay, 'Feature '+feature['id']+': nodes bind to exported geometry', str(feature['nodes']))
    from lowpoly_workshop.quality import check_relations, uv_diagnostics
    nodes = a.build(a.spec.get("review", {}).get("variant"))
    from .mesh import triangles
    from lowpoly_workshop.quality import topology
    for n,nd in nodes.items():
        if not nd['faces']:continue
        stats=topology(triangles({n:nd})[0])
        report(stats['finite'] and not stats['degenerate'] and not stats['duplicates'],f"Source {n}: finite, nondegenerate, no duplicate triangles",str(stats))
    check_relations(nodes, a.spec.get("relations", []), a.spec.get("poses", {}), report)
    uv_issues = uv_diagnostics(nodes, a.gen.ATLAS)
    report(not uv_issues, "Atlas and decal regions", str(uv_issues))
    if hasattr(a.gen, "extra_checks"):
        a.gen.extra_checks(a, report)
    print("RESULT:", "ALL PASS" if report.ok else "FAILURES")
    import json
    Path(a.out("check.json")).write_text(json.dumps(report.rows,indent=1))
    from lowpoly_workshop.approval import export_hashes
    from lowpoly_workshop.runner import fingerprint
    try:hashes=export_hashes(folder)
    except FileNotFoundError:hashes={}
    Path(a.out('check-meta.json')).write_text(json.dumps(dict(exports=hashes,source=fingerprint(folder)),indent=2))
    return report.ok
