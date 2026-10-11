"""Pattern search over generator parameters against every solved view at once (cameras held fixed).

    python lowpoly.py <asset> refine saddle_top:0.01 fork_x:0.005 bar_curve.0:0.008 --sweeps 4 --sets side,top

A list parameter entry is addressed as name.index. Accepted steps are written to
out/refine_overrides.json; read them, judge them (a parameter that only helps one view is usually the
drawing disagreeing with itself), then fold the ones you keep into gen.py's params.
"""
import json
import os
from multiprocessing import Pool

import numpy as np

from . import raster as rs
from .asset import Asset
from .camfit import ViewFit

G = {}


def _init(folder, views):
    G["a"] = Asset(folder)
    G["fits"] = {}
    for s, v in views:
        if G["a"].cam(s, v):
            G["fits"][(s, v)] = ViewFit(G["a"], s, v)


def _score(args):
    key, over = args
    a, vf = G["a"], G["fits"].get(key)
    if vf is None:
        return key, None
    a.overrides = over
    a._cache.clear()
    s, _ = vf.evaluate(a.cam(*key)["cam"], 0.5)
    return key, rs.objective(s) / 2.0


def _get(p, k):
    if "." in k:
        base, i = k.split(".")
        return p[base][int(i)]
    return p[k]


def run(folder, specs, sweeps=4, sets=None):
    a = Asset(folder)
    views = [(s, v) for s in a.sets() if (not sets or s in sets) for v in a.views(s) if a.cam(s, v)]
    path = a.out("refine_overrides.json")
    over = json.load(open(path)) if os.path.exists(path) else {}
    p0 = a.params(a.spec.get("fit_variant"))
    steps = {k: float(s) for k, s in specs}

    def expand(o):
        out = {}
        for k, v in o.items():
            if "." in k:
                base, i = k.split(".")
                lst = list(out.get(base, p0[base]))
                lst[int(i)] = v
                out[base] = lst
            else:
                out[k] = v
        return out

    def total(pool, o):
        res = dict(pool.map(_score, [(key, expand(o)) for key in views]))
        vals = [x for x in res.values() if x is not None]
        return float(np.mean(vals)), res

    with Pool(min(len(views), os.cpu_count() or 4), initializer=_init, initargs=(folder, views)) as pool:
        best, per = total(pool, over)
        print("start %.4f over %d views" % (best, len(views)), flush=True)
        for sw in range(sweeps):
            improved = False
            for k in steps:
                cur = over.get(k, _get(p0, k))
                for d in (steps[k], -steps[k]):
                    trial = dict(over)
                    trial[k] = round(cur + d, 5)
                    sc, per_t = total(pool, trial)
                    if sc > best + 1e-5:
                        best, over, per = sc, trial, per_t
                        improved = True
                        print("  sweep %d  %-16s %+.4f -> %.4f  mean %.4f" % (sw, k, d, trial[k], sc), flush=True)
                        json.dump(over, open(path, "w"), indent=1)
                        break
            if not improved:
                steps = {k: v / 2 for k, v in steps.items()}
                print("  sweep %d: no gain, halving steps" % sw, flush=True)
    print("final %.4f" % best)
    for key, v in sorted(per.items()):
        print("   %-14s %-10s %.3f" % (key[0], key[1], v if v is not None else float("nan")))
    print(json.dumps(over, indent=1))
    return over
