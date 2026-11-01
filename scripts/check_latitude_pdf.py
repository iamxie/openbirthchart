# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Check printed content and render each PDF for visual review."""
from pathlib import Path
import html,json,math,re,subprocess,sys,unicodedata
from pypdf import PdfReader
from PIL import Image,ImageDraw
root=Path(sys.argv[1]);folder=root/'exports';poppler=Path(sys.argv[2]);rendered=folder/'pdf-pages-final';rendered.mkdir(exist_ok=True)
compact=lambda s:re.sub(r'\s+','',unicodedata.normalize('NFKC',s))
results=[]
for pdf in sorted(folder.glob('*.pdf')):
    reader=PdfReader(pdf);texts=[p.extract_text() for p in reader.pages];en='en-US' in pdf.name
    for i,(page,text) in enumerate(zip(reader.pages,texts),1):
        assert abs(float(page.mediabox.width)-841.92)<2 and abs(float(page.mediabox.height)-595.92)<2
        footer=f'Page{i}of{len(texts)}' if en else f'第{i}頁/共{len(texts)}頁'
        assert footer in compact(text),(pdf.name,i,footer)
    combined=compact(''.join(texts));markup=pdf.with_suffix('.html').read_text(encoding='utf-8');count=0
    for section in ('positions','houses','details'):
        part=re.search(r'<section[^>]*id="'+section+r'"[^>]*>(.*?)</section>',markup,re.S)
        assert part,(pdf.name,section)
        for row in re.findall(r'<tr>(.*?)</tr>',part[1],re.S):
            if '<td>' not in row:continue
            value=compact(html.unescape(re.sub(r'<[^>]+>','',row)))
            assert value in combined,(pdf.name,section,value);count+=1
    expected_mode=('House-position view' if '-on-' in pdf.name else 'Longitude wheel') if en else ('宮位位置圖' if '-on-' in pdf.name else '黃經輪盤')
    assert compact(expected_mode) in compact(texts[0]),(pdf.name,'mode missing on chart page')
    warnings=re.search(r'<ul class="warnings">(.*?)</ul>',markup,re.S)
    if warnings:
        for warning in re.findall(r'<li>(.*?)</li>',warnings[1],re.S):
            assert compact(html.unescape(re.sub(r'<[^>]+>','',warning))) in compact(texts[0]),(pdf.name,'warning orphaned on next page')
    if '-H-' not in pdf.name:assert len(texts)==5,(pdf.name,'unexpected continuation',len(texts))
    subprocess.run([str(poppler),'-r','85','-png',str(pdf),str(rendered/pdf.stem)],check=True,capture_output=True)
    results.append(dict(file=pdf.name,pages=len(texts),footers_correct=True,complete_table_rows=count,mode_visible=True))
    pages=sorted(rendered.glob(pdf.stem+'-*.png'))
    sheet=Image.new('RGB',(1280,math.ceil(len(pages)/2)*330),'#ddd');draw=ImageDraw.Draw(sheet)
    for i,p in enumerate(pages):
        im=Image.open(p).convert('RGB');im.thumbnail((630,300));x=i%2*640;y=i//2*330
        sheet.paste(im,(x,y+24));draw.text((x+4,y+3),p.stem,fill='black')
    sheet.save(rendered/(pdf.stem+'-contact.jpg'))
    print(pdf.name,len(texts),'pages',flush=True)
for locale in ('zh-TW','en-US'):
    first=sorted(rendered.glob('*'+locale+'-1.png'));assert len(first)==16
    for start in range(0,16,4):
        sheet=Image.new('RGB',(1580,1160),'#ddd');draw=ImageDraw.Draw(sheet)
        for i,p in enumerate(first[start:start+4]):
            im=Image.open(p).convert('RGB');im.thumbnail((780,550));x=i%2*790;y=i//2*580
            sheet.paste(im,(x,y+25));draw.text((x+4,y+4),p.stem,fill='black')
        sheet.save(rendered/f'{locale}-charts-{start//4+1}.jpg')
(root/'pdf-checks.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
print('Verified',len(results),'PDFs /',sum(r['pages'] for r in results),'pages',flush=True)
