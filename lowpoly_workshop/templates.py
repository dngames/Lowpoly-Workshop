"""Independent procedural starter projects; no game-specific assets or paths."""
from pathlib import Path
import json,re,shutil
from .spec import KINDS

def create(folder,kind='static-prop',title=None):
    if kind not in KINDS:raise ValueError('Unknown template kind')
    dest=Path(folder).resolve()
    if dest.exists() and any(dest.iterdir()):raise ValueError('Template destination must be empty')
    dest.mkdir(parents=True,exist_ok=True)
    shutil.copytree(Path(__file__).parent/'assets/templates'/kind,dest,dirs_exist_ok=True)
    path=dest/'asset.json';spec=json.loads(path.read_text())
    spec['name']=re.sub(r'[^a-z0-9_-]+','-',dest.name.lower()).strip('-') or 'asset'
    spec['title']=title or dest.name.replace('-',' ').title()
    path.write_text(json.dumps(spec,indent=2)+'\n',encoding='utf-8')
    (dest/'ref').mkdir(exist_ok=True)
    print('CREATED',dest)
    return dest
