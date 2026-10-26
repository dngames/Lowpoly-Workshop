"""Compare old and remodelled actual-export building renders, with source/model hashes."""
import argparse,hashlib,json,sys
from pathlib import Path
from PIL import Image,ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parent))
from readme_visuals import font

def run(before,after,images):
    out=Path(images);out.mkdir(parents=True,exist_ok=True)
    sheet=Image.new('RGB',(1280,740),'#101d2d');d=ImageDraw.Draw(sheet)
    d.text((26,20),'Station Rest House: correcting the reference geometry',font=font(26,True),fill='#edf1eb')
    d.text((26,62),'Same historical 2D design · actual exported models · quarter view',font=font(19),fill='#b7c8cd')
    evidence={'source':'actual-export comparison','visual_approval':'not asserted','models':[]}
    for i,(project,title) in enumerate([(before,'Before: textured old massing'),(after,'After: rebuilt reference geometry')]):
        root=Path(project);index=json.loads((root/'out/review/index.json').read_text())
        shot=next(s for s in index['shots'] if s['output'].endswith('_LOD0.glb') and s['region']=='whole' and s['view']=='quarter')
        model=root/shot['output'];sha=hashlib.sha256(model.read_bytes()).hexdigest();assert sha==shot['sha256']
        image=root/shot['file'];im=Image.open(image).convert('RGBA').resize((580,580),Image.Resampling.LANCZOS)
        bg=Image.new('RGBA',im.size,'#1c2c3f');bg.alpha_composite(im);sheet.paste(bg.convert('RGB'),(20+i*640,110))
        d.text((28+i*640,706),title,font=font(21,True),fill='#edf1eb')
        evidence['models'].append({'title':title,'glb_sha256':sha,'generator_sha256':hashlib.sha256((root/'gen.py').read_bytes()).hexdigest(),'image_sha256':hashlib.sha256(image.read_bytes()).hexdigest(),'view':'quarter','source':'exported-model-render'})
    dest=out/'station-rest-house-remodel.png';sheet.save(dest);evidence['comparison_sha256']=hashlib.sha256(dest.read_bytes()).hexdigest()
    (out/'station-rest-house-remodel-evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print('COMPARISON',dest)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('before');p.add_argument('after');p.add_argument('--images',default='docs/images');a=p.parse_args();run(a.before,a.after,a.images)
