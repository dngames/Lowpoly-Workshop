"""New explanatory 2D diagrams for procedural demos; never historical reference art."""
from pathlib import Path
from html import escape

OUT=Path(__file__).resolve().parents[1]/'docs/images'

def write(name,title,description,body,width=1200,height=420):
    svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
<title id="title">{escape(title)}</title><desc id="desc">{escape(description)}</desc>
<rect width="{width}" height="{height}" rx="18" fill="#101d2d"/>
<g font-family="DejaVu Sans,Arial,sans-serif" fill="#edf1eb">
<text x="28" y="42" font-size="26" font-weight="bold">{escape(title)}</text>
<text x="28" y="72" font-size="16" fill="#b7c8cd">New explanatory diagram · procedural demo · no historical 2D original exists</text>
{body}</g></svg>\n'''
    (OUT/name).write_text(svg)


def run():
    write('character-design-notes.svg','Character construction notes: the written brief in 2D',
          'Front and side schematics explain the procedural guide. These are newly authored notes, not original concept art or a model render.', '''
<g stroke="#a7cbb7" stroke-width="2" fill="none"><path d="M80 112V348M72 112h16M72 348h16"/><path d="M60 350H585"/></g>
<text x="25" y="240" font-size="16" transform="rotate(-90 25 240)">1.72 m including cap</text>
<g stroke="#243645" stroke-width="2">
<rect x="185" y="273" width="36" height="66" rx="12" fill="#3b4f65"/><rect x="236" y="273" width="36" height="66" rx="12" fill="#3b4f65"/>
<rect x="178" y="330" width="46" height="20" rx="7" fill="#76513d"/><rect x="235" y="330" width="46" height="20" rx="7" fill="#76513d"/>
<rect x="177" y="198" width="103" height="91" rx="26" fill="#477d70"/>
<path d="M179 214L158 279M279 214L301 279" stroke="#477d70" stroke-width="25" stroke-linecap="round"/>
<circle cx="158" cy="288" r="12" fill="#dda678"/><circle cx="301" cy="288" r="12" fill="#dda678"/>
<ellipse cx="228" cy="164" rx="48" ry="43" fill="#dda678"/><path d="M178 145Q180 108 228 110Q276 110 278 145Z" fill="#477d70"/>
<circle cx="212" cy="165" r="3" fill="#352f32"/><circle cx="244" cy="165" r="3" fill="#352f32"/><path d="M219 182Q228 188 237 182" fill="none"/>
<rect x="252" y="222" width="11" height="16" fill="#e8d8ab"/>
<rect x="478" y="210" width="35" height="76" rx="8" fill="#b8824d"/>
<rect x="435" y="199" width="55" height="90" rx="22" fill="#477d70"/><ellipse cx="461" cy="165" rx="35" ry="43" fill="#dda678"/>
<path d="M426 145Q426 110 462 110Q494 110 497 145Z" fill="#477d70"/>
<rect x="447" y="282" width="28" height="57" rx="9" fill="#3b4f65"/><rect x="428" y="330" width="50" height="20" rx="7" fill="#76513d"/>
</g>
<text x="180" y="382" font-size="18">Front / +Z</text><text x="424" y="382" font-size="18">Side / pack</text>
<text x="650" y="130" font-size="22" font-weight="bold">Original input: a written design brief</text>
<text x="650" y="173" font-size="18">Cap · teal jacket · dark trousers · boots</text>
<text x="650" y="208" font-size="18">Backpack · friendly face · standing wave</text>
<text x="650" y="258" font-size="18">Low detail: 1,010 triangles</text>
<text x="650" y="291" font-size="18">Higher density: 21,162 triangles</text>
<text x="650" y="340" font-size="16" fill="#b7c8cd">Both models predate this diagram.</text>
<text x="650" y="369" font-size="16" fill="#b7c8cd">Neither matches the detailed character target yet.</text>''')
    write('starter-design-notes.svg','Starter construction notes: five small technical exercises',
          'New schematic notes for the five procedural starter models; no original input art existed.', '''
<g stroke="#a7cbb7" stroke-width="3" fill="#477d70">
<rect x="65" y="145" width="110" height="105" rx="3"/>
<path d="M290 145H400V250H290Z M303 157V235H387V157Z" fill-rule="evenodd"/>
<ellipse cx="565" cy="200" rx="51" ry="59" fill="#dda678"/>
<path d="M515 186Q565 140 615 186" fill="none" stroke="#354353" stroke-width="15"/>
<rect x="745" y="225" width="110" height="30"/><path d="M800 225V135" stroke="#e8d8ab" stroke-width="17"/>
<circle cx="800" cy="225" r="8" fill="#dda678"/>
<circle cx="1040" cy="142" r="26" fill="#dda678"/><rect x="1010" y="172" width="60" height="65"/>
<path d="M1025 237V275M1055 237V275M1010 185L990 230M1070 185L1090 230" fill="none" stroke-width="15"/>
</g>
<g font-size="18" text-anchor="middle">
<text x="120" y="307">Solid prop</text><text x="345" y="307">Hollow shell</text><text x="565" y="307">Surface wrap</text><text x="800" y="307">Moving pivot</text><text x="1040" y="307">Character joints</text>
</g><text x="28" y="380" font-size="17" fill="#b7c8cd">These explain source-code exercises. They are not reference-to-model success examples.</text>''')
    write('repair-design-notes.svg','Repair construction notes: fit matters beyond closure',
          'New schematic cross sections showing a flat fringe separating from a curved head and a surface-following fringe. Not historical reference art.', '''
<g stroke-width="5" fill="none">
<path d="M90 310Q120 100 380 140" stroke="#dda678"/><path d="M100 150H380" stroke="#e8d8ab"/>
<path d="M660 310Q690 100 950 140" stroke="#dda678"/><path d="M675 305Q705 87 955 126" stroke="#a7cbb7"/>
<path d="M510 210H580M560 190L580 210L560 230" stroke="#b7c8cd"/>
</g><g font-size="20"><text x="110" y="348">Flat patch: a visible gap</text><text x="670" y="348">Wrapped patch: follows the host</text></g>
<text x="28" y="390" font-size="17" fill="#b7c8cd">The original input is a procedural repair case, not a supplied drawing. Compare the exported views below.</text>''')
    print('Wrote three labelled explanatory SVG diagrams')

if __name__=='__main__':run()
