from pathlib import Path
import hashlib,json
from datetime import datetime,timezone
from .spec import read_spec

def export_hashes(folder):
    folder=Path(folder);s=read_spec(folder)
    names=[o['file'] for o in s['outputs']]
    skin=s.get('out_dir','out')+'/skinned.glb'
    if (folder/skin).exists():names.append(skin)
    return {n:hashlib.sha256((folder/n).read_bytes()).hexdigest() for n in names}

def record(folder,note):
    if not note.strip():raise ValueError('Approval needs a review note')
    folder=Path(folder);spec=read_spec(folder)
    from .workflow import approval_token
    token=approval_token(folder)
    data=dict(status='approved',note=note,exports=export_hashes(folder),reviewed_at=datetime.now(timezone.utc).isoformat())
    if token is not None:data['workflow_token']=token
    path=folder/spec.get('out_dir','out')/'approval.json';path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(data,indent=2))
    return data

def status(folder):
    folder=Path(folder);s=read_spec(folder);p=folder/s.get('out_dir','out')/'approval.json'
    if not p.exists():return dict(status='pending')
    data=json.loads(p.read_text())
    try:current=export_hashes(folder)
    except FileNotFoundError:return dict(status='stale',reason='Export missing')
    if data.get('exports')!=current:return dict(status='stale',reason='Export hashes changed')
    from .features import enabled
    if enabled(s) or data.get('workflow_token') is not None:
        from .workflow import approval_token
        try:token=approval_token(folder)
        except (ValueError,FileNotFoundError):return dict(status='stale',reason='Guided review missing or stale')
        if data.get('workflow_token')!=token:return dict(status='stale',reason='Guided review decisions changed')
    return data
