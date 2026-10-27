"""Compare reference roof and entrance crops with the actual exported front view."""
import argparse, hashlib, json
from pathlib import Path
from PIL import Image, ImageDraw
from readme_visuals import font


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run(project, images):
    root, out = Path(project), Path(images)
    out.mkdir(parents=True, exist_ok=True)
    original = root / 'ref/station_rest_house_v01.png'
    index = json.loads((root / 'out/review/index.json').read_text())
    shot = next(s for s in index['shots'] if s['region'] == 'whole' and s['view'] == 'front' and s['mode'] == 'textured')
    glb, rendered = root / shot['output'], root / shot['file']
    assert sha(glb) == shot['sha256']
    source, actual = Image.open(original).convert('RGBA'), Image.open(rendered).convert('RGBA')
    crops = [
        ('Gable braces and tile edges', (35, 55, 565, 220), (55, 125, 457, 250)),
        ('Two door leaves and stone post bases', (150, 285, 455, 453), (150, 306, 364, 400)),
    ]
    sheet = Image.new('RGB', (1440, 940), '#101d2d')
    draw = ImageDraw.Draw(sheet)
    draw.text((24, 16), 'Station Rest House: construction details', font=font(29, True), fill='#edf1eb')
    draw.text((24, 60), 'Original 2D design', font=font(22, True), fill='#b7c8cd')
    draw.text((744, 60), 'Actual exported model', font=font(22, True), fill='#b7c8cd')
    for row, (label, ref_box, actual_box) in enumerate(crops):
        y = 104 + row * 408
        draw.text((24, y), label, font=font(20, True), fill='#a7cbb7')
        for col, im in enumerate((source.crop(ref_box), actual.crop(actual_box))):
            scale = min(676 / im.width, 355 / im.height)
            im = im.resize((round(im.width * scale), round(im.height * scale)), Image.Resampling.LANCZOS)
            # Both reference and render are shown against a neutral surface; no geometry is changed.
            bg = Image.new('RGBA', (684, 363), '#1c2c3f')
            bg.alpha_composite(im, ((684 - im.width) // 2, (363 - im.height) // 2))
            sheet.paste(bg.convert('RGB'), (18 + col * 720, y + 29))
    draw.text((24, 923), 'Crops use separate framing; reference art is unchanged.', font=font(13), fill='#b7c8cd')
    target = out / 'station-rest-house-details.png'
    sheet.save(target)
    evidence = {'reference_sha256': sha(original), 'glb_sha256': sha(glb), 'render_sha256': sha(rendered),
                'comparison_sha256': sha(target), 'views': [{'label': n, 'reference_crop': r, 'render_crop': a} for n, r, a in crops],
                'visual_approval': 'not asserted'}
    (out / 'station-rest-house-details-evidence.json').write_text(json.dumps(evidence, indent=2) + '\n')
    print('DETAIL COMPARISON', target)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project')
    parser.add_argument('--images', default='docs/images')
    args = parser.parse_args()
    run(args.project, args.images)
