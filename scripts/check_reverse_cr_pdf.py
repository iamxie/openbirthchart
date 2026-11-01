# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Check every bilingual PDF's pagination/tables and render all pages for visual QA."""
from pathlib import Path
import html
import json
import re
import subprocess
import sys
import unicodedata
from pypdf import PdfReader
from PIL import Image,ImageOps,ImageDraw

folder=Path(sys.argv[1]);poppler=Path(sys.argv[2]);results=[]
compact=lambda s:re.sub(r'\s+','',unicodedata.normalize('NFKC',s))
rendered=folder/'pdf-pages';rendered.mkdir(exist_ok=True)
for pdf in sorted(folder.glob('*.pdf')):
    reader=PdfReader(pdf);texts=[p.extract_text() for p in reader.pages]
    assert len(texts)==5,(pdf.name,len(texts))
    for i,(page,text) in enumerate(zip(reader.pages,texts),1):
        assert abs(float(page.mediabox.width)-841.92)<2 and abs(float(page.mediabox.height)-595.92)<2
        footer=f'Page{i}of{len(texts)}' if 'en-US' in pdf.name else f'第{i}頁/共{len(texts)}頁'
        assert footer in compact(text),(pdf.name,i,footer)
    markup=pdf.with_suffix('.html').read_text(encoding='utf-8');combined=compact(''.join(texts));count=0
    for section in ('positions','houses','details'):
        part=re.search(r'<section[^>]*id="'+section+r'"[^>]*>(.*?)</section>',markup,re.S)
        assert part,(pdf.name,section)
        for row in re.findall(r'<tr>(.*?)</tr>',part[1],re.S):
            if '<td>' not in row:continue
            value=compact(html.unescape(re.sub(r'<[^>]+>','',row)))
            assert value in combined,(pdf.name,section,value)
            count+=1
    subprocess.run([str(poppler),'-r','90','-png',str(pdf),str(rendered/pdf.stem)],check=True,capture_output=True)
    results.append(dict(file=pdf.name,pages=len(texts),a4_landscape=True,footers_correct=True,complete_table_rows=count))
    # Every page is retained at reading resolution; a contact sheet checks page structure.
    pages=sorted(rendered.glob(pdf.stem+'-*.png'))
    sheet=Image.new('RGB',(1260,3*320),'#ddd');draw=ImageDraw.Draw(sheet)
    for index,p in enumerate(pages):
        im=Image.open(p).convert('RGB');im.thumbnail((620,290))
        x=(index%2)*630;y=(index//2)*320
        sheet.paste(im,(x,y+22));draw.text((x+5,y+4),pdf.stem+' page '+str(index+1),fill='black')
    sheet.save(rendered/(pdf.stem+'-contact.jpg'))
for lang in ('zh-TW','en-US'):
    first=sorted(rendered.glob('*'+lang+'-1.png'))
    assert len(first)==8
    for start in (0,4):
        sheet=Image.new('RGB',(1260,940),'#ddd');draw=ImageDraw.Draw(sheet)
        for i,p in enumerate(first[start:start+4]):
            im=Image.open(p).convert('RGB');im.thumbnail((620,438));x=i%2*630;y=i//2*470
            sheet.paste(im,(x,y+25));draw.text((x+5,y+4),p.stem,fill='black')
        sheet.save(rendered/f'{lang}-charts-{start//4+1}.jpg')
(folder/'pdf-checks.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
print('All',len(results),'PDFs passed; rendered',sum(r['pages'] for r in results),'pages')
