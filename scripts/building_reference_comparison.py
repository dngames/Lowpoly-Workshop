"""Original design / clay / painted comparison; original input remains unchanged."""
import argparse,hashlib,json,sys
from pathlib import Path
from PIL import Image,ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parent))
from readme_visuals import font
CROPS={'front':(10,35,575,475),'side':(585,35,1020,475),'quarter':(10,530,575,985),'top':(1030,530,1536,985)}
ANGLES={'front':[0,10],'side':[90,10],'quarter':[35,18],'top':[0,85]}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def run(project,images):
 root=Path(project);out=Path(images);out.mkdir(parents=True,exist_ok=True)
 source=root/'ref/station_rest_house_v01.png';original=Image.open(source).convert('RGB')
 index=json.loads((root/'out/review/index.json').read_text());evidence={'source':'original 2D input versus actual exported geometry','calibrated_overlay':False,'visual_approval':'not asserted','original_sha256':sha(source),'generator_sha256':sha(root/'gen.py'),'cameras':ANGLES,'exposure':-.5,'views':[]}
 def compose(views,name):
  sheet=Image.new('RGB',(1440,140+len(views)*444),'#101d2d');d=ImageDraw.Draw(sheet)
  d.text((22,20),'Reference first: rebuilt proportions, then surface finish',font=font(28,True),fill='#edf1eb')
  for col,label in enumerate(['Original 2D design','Actual exported clay','Same mesh, painted']):d.text((col*480+22,76),label,font=font(22,True),fill='#b7c8cd')
  for row,view in enumerate(views):
   y=113+row*444;d.text((22,y),view.replace('side','right side').title(),font=font(18,True),fill='#a7cbb7')
   frames=[original.crop(CROPS[view]).convert('RGBA')]
   for mode in ['plain','textured']:
    shot=next(s for s in index['shots'] if s['region']=='whole' and s['view']==view and s['mode']==mode)
    assert sha(root/shot['output'])==shot['sha256']
    im=Image.open(root/shot['file']).convert('RGBA');box=im.getchannel('A').getbbox()
    if box:im=im.crop(box)
    frames.append(im)
    if name=='station-rest-house-reference-check':evidence['views'].append({'view':view,'mode':mode,'glb_sha256':shot['sha256'],'image_sha256':sha(root/shot['file']),'original_crop':CROPS[view]})
   for col,im in enumerate(frames):
    im.thumbnail((440,376),Image.Resampling.LANCZOS);bg=Image.new('RGBA',(444,388),'#1c2c3f');bg.alpha_composite(im,((444-im.width)//2,(388-im.height)//2));sheet.paste(bg.convert('RGB'),(18+col*480,y+28))
  d.text((22,sheet.height-15),'Separate framing, not calibrated overlays. Original design sheet preserved unchanged.',font=font(13),fill='#b7c8cd')
  target=out/(name+'.png');sheet.save(target);return sha(target)
 evidence['comparison_sha256']=compose(['front','side','quarter','top'],'station-rest-house-reference-check')
 evidence['preview_sha256']=compose(['quarter'],'station-rest-house-shape-preview')
 (out/'station-rest-house-reference-check-evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
 print('REFERENCE COMPARISON',out/'station-rest-house-reference-check.png')
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('project');p.add_argument('--images',default='docs/images');a=p.parse_args();run(a.project,a.images)
