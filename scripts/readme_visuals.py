"""Build README illustrations from the five bundled starters and their actual GLBs.

No reference downloads or image-generation service. Keep generated projects outside
this repository; only the contact sheet and relative hash evidence are published.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lowpoly_workshop.templates import create

KINDS = [('static-prop','Static prop','Origins & sockets'),
         ('hollow-prop','Hollow prop','Walls & thickness'),
         ('wearable','Wearable','Fit & wrapping'),
         ('articulated','Articulated','Pivots & movement'),
         ('character','Character','Joints & support')]


def font(size, bold=False):
    candidates = [Path('/usr/share/fonts/truetype/dejavu')/('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf'),
                  Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/('arialbd.ttf' if bold else 'arial.ttf')]
    for path in candidates:
        if path.exists():return ImageFont.truetype(str(path),size)
    try:return ImageFont.load_default(size=size)
    except TypeError:return ImageFont.load_default()


def run(destination, images):
    root=Path(destination).resolve();out=Path(images).resolve()
    if root.exists() and any(root.iterdir()):raise ValueError('Destination must be empty')
    root.mkdir(parents=True,exist_ok=True);out.mkdir(parents=True,exist_ok=True)
    evidence={'source':'bundled original procedural starters','render_source':'actual exported GLBs',
              'purpose':'workflow illustration, not a quality benchmark','visual_approval':'not asserted','examples':[]}
    canvas=Image.new('RGB',(1500,650),'#101d2d');draw=ImageDraw.Draw(canvas)
    draw.text((42,30),'From an editable source to a model you can inspect',font=font(36,True),fill='#f1f4ef')
    draw.text((42,87),'Five bundled starters · actual GLB renders · no generated concept art',font=font(22),fill='#b7c8cd')
    for i,(kind,title,caption) in enumerate(KINDS):
        folder=create(root/kind,kind)
        p=folder/'asset.json';spec=json.loads(p.read_text());spec['review']={'size':384,'views':['quarter'],'modes':['textured'],'regions':[]};p.write_text(json.dumps(spec,indent=2)+'\n')
        for command in ('build','check','review'):
            subprocess.run([sys.executable,'-m','lowpoly_workshop',str(folder),command],check=True)
        index=json.loads((folder/'out/review/index.json').read_text());shot=next(s for s in index['shots'] if s['view']=='quarter' and s['mode']=='textured')
        model=folder/'out/model.glb';sha=hashlib.sha256(model.read_bytes()).hexdigest();assert shot['sha256']==sha
        im=Image.open(folder/shot['file']).convert('RGBA');im.thumbnail((264,360))
        x=30+i*294;y=146
        draw.rounded_rectangle((x,y,x+276,y+450),radius=18,fill='#1c2c3f',outline='#35495b',width=2)
        background=Image.new('RGBA',im.size,'#1c2c3f');background.alpha_composite(im);canvas.paste(background.convert('RGB'),(x+(276-im.width)//2,y+35+(310-im.height)//2))
        draw.text((x+18,y+350),title,font=font(24,True),fill='#f1f4ef')
        draw.text((x+18,y+391),caption,font=font(18),fill='#a7cbb7')
        evidence['examples'].append({'kind':kind,'generator':str((folder/'gen.py').relative_to(root)),
            'generator_sha256':hashlib.sha256((folder/'gen.py').read_bytes()).hexdigest(),
            'glb':str(model.relative_to(root)),'glb_sha256':sha,'checks_passed':True,
            'review_image':str((folder/shot['file']).relative_to(root)),
            'review_image_sha256':hashlib.sha256((folder/shot['file']).read_bytes()).hexdigest()})
    draw.text((42,616),'Small starting points for your own assets. The artist authors the geometry; Workshop supports the iteration.',font=font(18),fill='#b7c8cd')
    target=out/'workshop-starters.png';canvas.save(target)
    evidence['contact_sheet_sha256']=hashlib.sha256(target.read_bytes()).hexdigest()
    (out/'workshop-starters-evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print('README VISUALS',target)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('destination');parser.add_argument('--images',default='docs/images')
    args=parser.parse_args();run(args.destination,args.images)
