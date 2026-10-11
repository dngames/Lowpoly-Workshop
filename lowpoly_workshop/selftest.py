"""Installed-package smoke tests; no dependency on a source checkout or game."""
from pathlib import Path
import tempfile,json
import numpy as np
from .spec import KINDS
from .templates import create
from .kit.asset import Asset
from .kit.mesh import triangles
from .quality import topology,check_relations

def run(with_blender=False):
    with tempfile.TemporaryDirectory(prefix='lowpoly-selftest-') as tmp:
        root=Path(tmp)
        for kind in KINDS:
            folder=create(root/kind,kind);a=Asset(folder);nodes=a.build()
            for n in a.spec['outputs'][0]['contract']['closed']:
                t=topology(triangles({n:nodes[n]})[0])
                if not t['finite'] or any(t[k] for k in ('boundary_edges','nonmanifold_edges','winding_edges','duplicates','degenerate')):raise ValueError(f'{kind}/{n} topology: {t}')
            results=[];check_relations(nodes,a.spec['relations'],a.spec['poses'],lambda ok,*_:results.append(ok))
            if not all(results):raise ValueError(kind+' relation failed')
            if with_blender:
                from .runner import build
                from .kit.check import run as check
                build(folder)
                if not check(folder):return 1
        if with_blender:
            from .pipeline import blender
            from .kit.page import build_page
            from .distribution import package_asset
            blender('skin_export.py',root/'character')
            folder=root/'wearable';p=folder/'asset.json';spec=json.loads(p.read_text());spec['review']={'size':256,'views':['below'],'modes':['textured'],'regions':[]};p.write_text(json.dumps(spec))
            blender('review.py',folder);blender('check_uv.py')
            articulated=root/'articulated';q=articulated/'asset.json';s=json.loads(q.read_text());s['review']={'size':256,'views':['quarter'],'modes':['plain'],'regions':[]};q.write_text(json.dumps(s))
            blender('review.py',articulated)
            shots=json.loads((articulated/'out/review/index.json').read_text())['shots']
            if len({shot['pose_geometry_sha256'] for shot in shots})!=2:raise ValueError('Review pose was overridden by imported animation')
            page=build_page(folder);package_asset(folder)
            if not page.exists():raise ValueError('Handover page missing')
    print('SELFTEST PASS'+(' (Blender exports, skeletal roundtrip, UV and actual-export render)' if with_blender else ' (installed templates and geometry)'))
    return 0
