# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Check actual browser pagination, not the number of HTML sections."""
from pathlib import Path
import re, json, sys, unicodedata, html
from pypdf import PdfReader

folder=Path(sys.argv[1]);results=[]
english='--english' in sys.argv[2:]
for name in ('report','restricted','continuation'):
    reader=PdfReader(folder/(name+'-print.pdf'))
    count=len(reader.pages);texts=[]
    for index,page in enumerate(reader.pages,1):
        text=unicodedata.normalize('NFKC',page.extract_text());texts.append(text)
        compact=re.sub(r'\s+','',text)
        footer=f'Page{index}of{count}' if english else f'第{index}頁/共{count}頁'
        assert footer in compact,(name,index,'incorrect footer',text[-150:])
        assert '列印建議' not in text and 'Open BirthChart' not in text,(name,index,'screen-only text')
        assert 'Printing: use' not in text,(name,index,'screen-only English text')
        assert '夏令判定方式' not in text
        assert abs(float(page.mediabox.width)-841.92)<2 and abs(float(page.mediabox.height)-595.92)<2
    if name!='continuation':assert count==5,(name,count)
    else:
        assert count>5
        combined=''.join(texts)
        for i in range(1,101):assert f'{i:03}' in combined,('missing note',i)
    markup=(folder/(name+'.html')).read_text(encoding='utf-8')
    section=re.search(r'<section class="page" id="details">(.*?)</section>',markup,re.S).group(1)
    rows=re.findall(r'<tr>(.*?)</tr>',section,re.S)
    rows=[row for row in rows if '<td>' in row]
    compact_pdf=re.sub(r'\s+','',''.join(texts))
    for row in rows:
        value=html.unescape(re.sub(r'<[^>]+>','',row))
        value=re.sub(r'\s+','',unicodedata.normalize('NFKC',value))
        assert value in compact_pdf,(name,'missing detail row',value)
    results.append(dict(name=name,pages=count,all_page_counters_correct=True,screen_chrome_hidden=True,detail_rows_verified=len(rows)))
(folder/'pdf-checks.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(results,ensure_ascii=False))
