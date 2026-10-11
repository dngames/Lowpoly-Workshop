"""Offline handover page with local Three.js; served through localhost, no CDN."""
import hashlib,html,json,shutil
from pathlib import Path
from .asset import Asset

def build_page(folder,scripts_dir=None):
    a=Asset(folder);pkg=Path(__file__).parents[1];root=Path(a.out('page','index.html')).parent
    root.mkdir(parents=True,exist_ok=True)
    shutil.copytree(pkg/'viewer',root,dirs_exist_ok=True)
    def copy(src,rel):
        dest=root/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest);return rel
    outputs=[]
    for i,out in enumerate(a.outputs()):
        src=Path(a.path(out['file']))
        if src.exists():outputs.append(dict(label=out.get('label',src.stem),url=copy(src,f'models/{i}.glb'),sha256=hashlib.sha256(src.read_bytes()).hexdigest()))
    skin=Path(a.out('skinned.glb'))
    if skin.exists():outputs.append(dict(label='Skinned character',url=copy(skin,'models/skinned.glb'),sha256=hashlib.sha256(skin.read_bytes()).hexdigest()))
    refs=[]
    for i,ref in enumerate(a.spec.get('references',[])):
        src=Path(a.path(ref['path']))
        if src.exists():refs.append({**ref,'url':copy(src,f'images/reference-{i}{src.suffix.lower()}')})
    feature_refs=[]
    for i,feature in enumerate(a.spec.get('features',[])):
        for j,evidence in enumerate(feature.get('evidence',[])):
            src=Path(a.path(evidence['path']))
            registered=next(r for r in a.spec['references'] if r['path']==evidence['path'])
            if evidence.get('box'):
                from PIL import Image
                rel=f'images/feature-{i}-reference-{j}.png';dest=root/rel
                dest.parent.mkdir(parents=True,exist_ok=True)
                with Image.open(src) as image:image.convert('RGB').crop(evidence['box']).save(dest)
            else:rel=copy(src,f'images/feature-{i}-reference-{j}{src.suffix.lower()}')
            feature_refs.append(dict(feature_id=feature['id'],url=rel,source=registered['source'],view=evidence.get('view','reference')))
    review=Path(a.out('review','index.json'));shots=[]
    if review.exists():
        for i,shot in enumerate(json.loads(review.read_text())['shots']):
            src=Path(a.path(shot['file']))
            if src.exists():shots.append({**shot,'url':copy(src,f'images/review-{i}.png')})
    checks=Path(a.out('check.json'));scores=Path(a.out('compare','scores.json'))
    from lowpoly_workshop.approval import status,export_hashes
    from lowpoly_workshop.runner import fingerprint
    check_rows=json.loads(checks.read_text()) if checks.exists() else []
    meta=Path(a.out('check-meta.json'))
    try:
        evidence=json.loads(meta.read_text())
        fresh=evidence.get('exports')==export_hashes(folder) and evidence.get('source')==fingerprint(folder)
    except FileNotFoundError:fresh=False
    if not fresh:check_rows.insert(0,dict(ok=False,text='Check evidence missing or stale; rerun check',detail='Current export/source hashes differ'))
    for shot in shots:
        source=next((o for o in outputs if o.get('sha256')==shot.get('sha256')),None)
        src=Path(a.path(shot['file']))
        shot['stale']=source is None or not src.exists() or hashlib.sha256(src.read_bytes()).hexdigest()!=shot.get('image_sha256')
    from lowpoly_workshop.workflow import status as workflow_status
    workflow=workflow_status(folder)
    manifest=dict(title=a.spec.get('title',a.spec['name']),outputs=outputs,references=refs,shots=shots,checks=check_rows,fit_scores=json.loads(scores.read_text()) if scores.exists() else {},visual_approval=status(folder),workflow=workflow,feature_references=feature_refs)
    (root/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('PAGE',root/'index.html')
    return root/'index.html'
