"""Compose the Tiny Tour building tutorial from actual-export review images."""
import argparse,hashlib,json,sys
from pathlib import Path
from PIL import Image,ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parent))
from readme_visuals import font
from lowpoly_workshop.kit.glb import Glb


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(project,images):
    root=Path(project).resolve();out=Path(images).resolve();out.mkdir(parents=True,exist_ok=True)
    index=json.loads((root/'out/review/index.json').read_text())
    spec=json.loads((root/'asset.json').read_text());counts=[]
    for output in spec['outputs']:
        model=Glb(root/output['file']);geo,_=model.posed(model.sample())
        counts.append(sum(len(t) for t in geo.values()))
    tiles=[('Street-side welcome',0,'quarter'),('Read the architecture',0,'front'),
           ('Inspect the rear',0,'back'),('Reduce detail, keep the building',2,'quarter')]
    sheet=Image.new('RGB',(1440,490),'#101d2d');d=ImageDraw.Draw(sheet)
    d.text((24,20),'Tiny Tour building: Yuzu Station Rest House',font=font(30,True),fill='#f1f4ef')
    d.text((24,66),'Actual exported GLBs · LOD0 / LOD1 / LOD2 / far: '+' / '.join(map(str,counts))+' triangles',font=font(18),fill='#b7c8cd')
    evidence={'source':'Tiny Tour first-party building, owner-requested Workshop adaptation',
              'source_commit':json.loads((root/'provenance.json').read_text())['source_commit'],
              'visual_approval':'not asserted','triangles':counts,
              'source_sha256':{n:digest(root/n) for n in ['gen.py','asset.json','inputs/construction.json','provenance.json']},
              'checks_passed':all(c['ok'] for c in json.loads((root/'out/check.json').read_text())), 'views':[]}
    for i,(label,lod,view) in enumerate(tiles):
        output=spec['outputs'][lod]['file'];sha=digest(root/output)
        shot=next(s for s in index['shots'] if s['output']==output and s['region']=='whole' and s['pose']=='rest' and s['view']==view)
        assert shot['sha256']==sha
        path=root/shot['file'];im=Image.open(path).convert('RGBA');im.thumbnail((336,336))
        x=i*360+12;d.rounded_rectangle((x,108,x+336,448),radius=14,fill='#1c2c3f')
        bg=Image.new('RGBA',im.size,'#1c2c3f');bg.alpha_composite(im);sheet.paste(bg.convert('RGB'),(x+(336-im.width)//2,108))
        d.text((x+8,458),label,font=font(16,True),fill='#e6eee7')
        evidence['views'].append({'output':output,'glb_sha256':sha,'view':view,'image':shot['file'],'image_sha256':digest(path)})
    dest=out/'create-building.png';sheet.save(dest);evidence['contact_sheet_sha256']=digest(dest)
    (out/'create-building-evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print('BUILDING VISUALS',dest)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('project');p.add_argument('--images',default='docs/images')
    a=p.parse_args();run(a.project,a.images)
