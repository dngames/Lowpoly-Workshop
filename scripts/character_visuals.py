"""Compose character tutorial evidence from real exported-model review images."""
import argparse,hashlib,json,sys
from pathlib import Path
from PIL import Image,ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parent))
from readme_visuals import font
from lowpoly_workshop.kit.glb import Glb


def run(project,images):
    root=Path(project).resolve();out=Path(images).resolve();out.mkdir(parents=True,exist_ok=True)
    index=json.loads((root/'out/review/index.json').read_text())
    model=root/'out/guide.glb';sha=hashlib.sha256(model.read_bytes()).hexdigest()
    exported=Glb(model);geometry,_=exported.posed(exported.sample());count=sum(len(t) for t in geometry.values())
    tiles=[('Meet the guide','rest','quarter'),('Read the silhouette','rest','side'),
           ('Inspect the back','rest','back'),('Test the greeting','wave','quarter')]
    w,h=360,490;sheet=Image.new('RGB',(w*4, h),'#101d2d');d=ImageDraw.Draw(sheet)
    d.text((24,20),'Create a character: an editable trail guide',font=font(30,True),fill='#f1f4ef')
    d.text((24,66),f'Actual exported GLB · {count:,} triangles · capped joints · looping rigid-node wave',font=font(18),fill='#b7c8cd')
    evidence={'source':'original procedural character example','visual_approval':'not asserted',
        'generator_sha256':hashlib.sha256((root/'gen.py').read_bytes()).hexdigest(),
        'asset_spec_sha256':hashlib.sha256((root/'asset.json').read_bytes()).hexdigest(),
        'glb_sha256':sha,'triangles':count,'checks_passed':all(r['ok'] for r in json.loads((root/'out/check.json').read_text())),
        'views':[]}
    for i,(label,pose,view) in enumerate(tiles):
        shot=next(s for s in index['shots'] if s['region']=='whole' and s['pose']==pose and s['view']==view)
        assert shot['sha256']==sha
        path=root/shot['file'];im=Image.open(path).convert('RGBA');im.thumbnail((336,336))
        x=i*w+12;d.rounded_rectangle((x,108,x+336,448),radius=14,fill='#1c2c3f')
        bg=Image.new('RGBA',im.size,'#1c2c3f');bg.alpha_composite(im);sheet.paste(bg.convert('RGB'),(x+(336-im.width)//2,108))
        d.text((x+12,458),label,font=font(18,True),fill='#e6eee7')
        evidence['views'].append({'pose':pose,'view':view,'image':shot['file'],
            'image_sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    dest=out/'create-character.png';sheet.save(dest)
    evidence['contact_sheet_sha256']=hashlib.sha256(dest.read_bytes()).hexdigest()
    (out/'create-character-evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print('CHARACTER VISUALS',dest)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('project');p.add_argument('--images',default='docs/images');a=p.parse_args();run(a.project,a.images)
