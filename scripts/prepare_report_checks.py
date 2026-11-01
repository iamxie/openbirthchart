# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Public synthetic fixtures for print continuation and visibility checks."""
import os,sys,json,argparse
os.environ['QT_QPA_PLATFORM']='offscreen'
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path[:0]=[str(root),str(root/'scripts')]
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase
from dataclasses import replace
from desktop.model import BirthInput,display_chart,ASPECTS,APP_VERSION
from desktop.report import export_html,TEMPLATES
parser=argparse.ArgumentParser()
parser.add_argument('--template',default='zh-TW')
parser.add_argument('--output',type=Path)
parser.add_argument('--fixture',type=Path)
args=parser.parse_args()
app=QApplication([]);QFontDatabase.addApplicationFont(str(root/'data/desktop/NotoSansTC.ttf'))
out=args.output or root/'results/desktop'/('review-'+APP_VERSION)
out.mkdir(parents=True,exist_ok=True)
chart=json.loads((args.fixture or out/'chart.json').read_text(encoding='utf-8'));chart['orbs']={int(a):v for a,v in chart['orbs'].items()}
template=TEMPLATES/args.template
if args.template=='en-US':chart['input']['name']='Alex Example'
export_html(chart,out/'report.html',template_dir=template)
birth=BirthInput(**chart['input'])
restricted=display_chart(chart,replace(birth,small_bodies=False,minor_aspects=False))
export_html(restricted,out/'restricted.html',template_dir=template)
note='Continuation test {i:03}: preserve all content.' if args.template=='en-US' else '備註續頁測試 {i:03}：保留完整內容。'
crowded=display_chart(chart,replace(birth,notes='\n'.join(note.format(i=i) for i in range(1,101))),{a:15. for a,_,_,_,_ in ASPECTS})
export_html(crowded,out/'continuation.html',include_notes=True,template_dir=template)
print('Generated 3 reports; crowded aspects:',len(crowded['aspects']))
