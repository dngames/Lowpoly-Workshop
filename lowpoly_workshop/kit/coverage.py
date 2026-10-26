"""Geometric observation coverage and extra camera suggestions; never paints or fits.

Recommendations target unseen/poorly observed surface area. The separate review
camera contributes no coverage and is never written into fitted camera inputs.
"""
import os
import hashlib
import json
import numpy as np
from PIL import Image
from . import raster
from .asset import Asset
from .atomic import replacing, write_json
from .camfit import make_cam
from .paintcheck import keyed_triangles


def observation(tris, cam, size=256, min_pixels=3):
    """Per-triangle front-facing quality, with occlusion and silhouette penalties."""
    normal = np.cross(tris[:, 1]-tris[:, 0], tris[:, 2]-tris[:, 0])
    normal /= np.maximum(np.linalg.norm(normal, axis=1, keepdims=True), 1e-15)
    ray = cam.eye-tris.mean(axis=1)
    distance = np.linalg.norm(ray, axis=1)
    direction = np.broadcast_to(-cam.fwd, normal.shape) if cam.ortho else ray/np.maximum(distance[:, None], 1e-15)
    cosine = np.maximum(0, np.sum(normal*direction, axis=1))
    front = np.flatnonzero(cosine > 1e-9)
    _, labels, depth = raster.render(tris[front], list(front), cam, size, size,
        shade=False, palette={i: (0., 0., 0.) for i in front},
        classes={i: int(i)+1 for i in front})
    ids = labels-1
    visible = ids >= 0
    interior = visible.copy()
    # Geometry silhouettes/depth jumps matter; a coplanar triangulation edge does not.
    for axis in [0, 1]:
        for shift in [-1, 1]:
            neighbour = np.roll(visible, shift, axis=axis)
            neighbour_depth = np.roll(depth, shift, axis=axis)
            delta = np.zeros_like(depth)
            both = visible & neighbour
            np.subtract(depth, neighbour_depth, out=delta, where=both)
            interior &= both & (np.abs(delta) <= .04*np.maximum(depth, 1e-12))
    interior[[0, -1], :] = False
    interior[:, [0, -1]] = False
    counts = np.bincount(ids[visible], minlength=len(tris))
    inner = np.bincount(ids[visible & interior], minlength=len(tris))
    edge_weight = .3+.7*inner/np.maximum(counts, 1)
    # Fitted near-orthographic cameras can trade focal scale against distance.
    # Use projected pixel density so equivalent projections get equivalent credit.
    area = np.linalg.norm(np.cross(tris[:, 1]-tris[:, 0], tris[:, 2]-tris[:, 0]), axis=1)/2
    quality = cosine*np.sqrt(counts/np.maximum(area, 1e-15))*edge_weight
    quality[counts < min_pixels] = 0
    return quality


def suggestion_gain(area, known, candidate, ratio=.4):
    """Prioritise unseen area, then genuinely better observations; not face count."""
    newly_seen = (known == 0) & (candidate > 0)
    better = (known > 0) & (candidate > known/ratio)
    return float(np.sum(area*(newly_seen+.25*better)))


def framed(tris, az, el, size):
    points = tris.reshape(-1, 3)
    target = (points.min(0)+points.max(0))/2
    span = max(float(np.max(np.ptp(points, axis=0))), 1e-6)
    distance = max(span*20, 1.)
    probe = make_cam([az, el, 0, distance, 1, 0, 0], target)
    uv, _ = probe.project(points)
    scale = .84*size/max(float(np.max(np.ptp(uv, axis=0))), 1e-12)
    v = [az, el, 0., distance, scale,
         size/2-scale*(uv[:, 0].min()+uv[:, 0].max())/2,
         size/2-scale*(uv[:, 1].min()+uv[:, 1].max())/2]
    return v, target


def plan(tris, known, size=256, budget=4, excluded=()):
    area = np.linalg.norm(np.cross(tris[:, 1]-tris[:, 0], tris[:, 2]-tris[:, 0]), axis=1)/2
    choices = []
    for el in [-35, 0, 35, 75]:
        for az in range(0, 360, 45):
            if any(abs((az-a+180) % 360-180) < 10 and abs(el-e) < 10 for a, e in excluded):
                continue
            v, target = framed(tris, az, el, size)
            q = observation(tris, make_cam(v, target), size)
            choices.append((v, target, q))
    current = known.copy()
    selected = []
    for _ in range(budget):
        gains = [suggestion_gain(area, current, q) for _, _, q in choices]
        if not gains or max(gains) <= 0:
            break
        i = int(np.argmax(gains))
        v, target, q = choices.pop(i)
        selected.append({'cam': v, 'target': target.tolist(), 'gain_m2': gains[i],
                         'new_area_m2': float(area[(current == 0) & (q > 0)].sum())})
        current = np.maximum(current, q)
    return selected, current


def run(folder, set_name=None, size=256, budget=4):
    if not 32 <= size <= 1024 or not 0 <= budget <= 12:
        raise ValueError('coverage requires size 32..1024 and budget 0..12')
    a = Asset(folder)
    names = [set_name] if set_name else list(a.sets())
    reports = {}
    for st in names:
        views = [v for v in a.views(st) if a.cam(st, v)]
        if not views:
            raise ValueError('No fitted cameras for '+st+'; run fit first')
        anchor = a.cam(st, views[0])['cam']
        nodes, pose = a.scene(st, views[0], anchor[7:])
        tris, cells, keys = keyed_triangles(nodes, pose)
        if not len(tris) or not np.isfinite(tris).all():
            raise ValueError('Coverage needs finite nonempty geometry')
        evidence = hashlib.sha256(np.asarray(tris, dtype="<f8").tobytes())
        known = np.zeros(len(tris))
        lookup = {k: i for i, k in enumerate(keys)}
        excluded = []
        for view in views:
            v = a.cam(st, view)['cam']
            nd, ps = a.scene(st, view, v[7:])
            t, _, k = keyed_triangles(nd, ps)
            evidence.update(np.asarray(t, dtype="<f8").tobytes())
            evidence.update(json.dumps([view, v, list(a.target())]).encode())
            x0, y0, x1, y1 = a.crop_box(st, view)
            # Letterbox the original fitted crop into the diagnostic square.
            scale = size/max(x1-x0, y1-y0)
            adjusted = list(v)
            adjusted[4] *= scale
            adjusted[5] = v[5]*scale+(size-(x1-x0)*scale)/2
            adjusted[6] = v[6]*scale+(size-(y1-y0)*scale)/2
            q = observation(t, make_cam(adjusted, a.target()), size)
            for key, quality in zip(k, q):
                if key in lookup:
                    i = lookup[key]
                    known[i] = max(known[i], quality)
            excluded.append(v[:2])
        # Choose a distinct review angle, but never use it in the planner's evidence.
        review_angles = [(112.5, 22), (247.5, 22), (67.5, -20), (202.5, 55)]
        az, el = max(review_angles, key=lambda p: min(
            np.hypot(abs((p[0]-v[0]+180) % 360-180), p[1]-v[1]) for v in excluded))
        if min(np.hypot(abs((az-v[0]+180) % 360-180), el-v[1]) for v in excluded) < 1:
            raise ValueError('No distinct independent review angle; extend review_angles')
        review, target = framed(tris, az, el, size)
        suggestions, hypothetical = plan(tris, known, size, budget, excluded+[[az, el]])
        area = np.linalg.norm(np.cross(tris[:, 1]-tris[:, 0], tris[:, 2]-tris[:, 0]), axis=1)/2
        total = float(area.sum())
        out = a.out('coverage', st)
        os.makedirs(out, exist_ok=True)
        heat = {i: ([216, 55, 55] if q == 0 else [80, 165, 105]) for i, q in enumerate(known)}
        images = [('review-palette', review, target, a.palette(nodes), cells),
                  ('review-coverage', review, target, heat, list(range(len(tris))))]
        for i, suggestion in enumerate(suggestions, 1):
            label = 'suggestion-%02d' % i
            suggestion['image'] = label+'.png'
            images.append((label, suggestion['cam'], suggestion['target'], a.palette(nodes), cells))
        for label, v, tgt, palette, cs in images:
            rgb, cm, _ = raster.render(tris, cs, make_cam(v, tgt), size, size,
                palette=palette, classes={'_default': 1})
            image = Image.fromarray(np.where((cm > 0)[..., None], rgb, 240).astype(np.uint8))
            with replacing(os.path.join(out, label+'.png')) as tmp:
                image.save(tmp)
        reports[st] = {'input_geometry_cameras_sha256': evidence.hexdigest(), 'resolution': size, 'source_views': views,
            'triangles': len(tris), 'observed_area_fraction': float(area[known > 0].sum()/max(total, 1e-15)),
            'unobserved': [{'node': k[0], 'face': k[1], 'triangle': k[2], 'area_m2': float(ar)}
                           for k, ar, q in zip(keys, area, known) if q == 0],
            'suggestions': suggestions,
            'hypothetical_observed_area_fraction': float(area[hypothetical > 0].sum()/max(total, 1e-15)),
            'review': {'cam': review, 'target': target.tolist(), 'used_for_fit_or_paint': False},
            'note': 'Geometric visibility estimate, not paint correctness. Hidden/internal faces may remain unseen. '
                    'Suggested cameras have no reference evidence until supplied and fitted. Images are CPU palette proofs.'}
        print(st, 'observed %.1f%%; %d suggested cameras' %
              (100*reports[st]['observed_area_fraction'], len(suggestions)))
    write_json(a.out('coverage', 'report.json'), reports, indent=2)
    return reports
