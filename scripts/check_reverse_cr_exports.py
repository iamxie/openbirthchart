# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Render all eight real reverse C/R cases in desktop and both report languages."""
import copy
import gzip
import json
import os
from pathlib import Path
import sys
import tempfile

os.environ['QT_QPA_PLATFORM']='offscreen'
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont,QFontDatabase
from PySide6.QtTest import QTest
from desktop.model import ASPECTS,ChartEngine
from complete_regression import exact
from desktop.chart import export_chart
from desktop.window import MainWindow
from desktop.storage import ProfileStore
from desktop.i18n import install_language,localized_zodiac
from desktop.report import export_html,TEMPLATES


def check(folder):
    folder=Path(folder);output=folder/'visuals';output.mkdir(exist_ok=True)
    ids={r['case'] for r in json.loads((ROOT/'tests/fixtures/reverse-cr-original-cusps.json').read_text(encoding='utf-8'))}
    charts={r['id']:r['raw'] for r in (json.loads(line) for line in gzip.open(folder/'product/results.jsonl.gz','rt',encoding='utf-8')) if r['id'] in ids}
    app=QApplication.instance() or QApplication([])
    font=QFontDatabase.addApplicationFont(str(ROOT/'data/desktop/NotoSansTC.ttf'))
    app.setFont(QFont(QFontDatabase.applicationFontFamilies(font)[0],10));checks=[];engine=ChartEngine()
    with tempfile.TemporaryDirectory() as temporary:
        for lang in ('zh-TW','en-US'):
            install_language(app,lang)
            window=MainWindow(auto_start=False,store=ProfileStore(Path(temporary)/(lang+'.sqlite')),prompt_unsaved=False)
            window.resize(1400,950);window.show()
            for ident,raw in charts.items():
                chart=copy.deepcopy(raw);chart['orbs']={int(k):v for k,v in chart['orbs'].items()}
                window.restore_profile(dict(schema=1,input=chart['input'],custom_orbs=False,orb_values={str(a):o for a,_,o,_,_ in ASPECTS}))
                # Auto-DST refresh mirrors the resolved checkbox and clears unused fold.
                # Calculate the real form input and require identical astronomical output.
                ui_chart=engine.calculate(window.input())
                normalized=[k for k,v in chart['input'].items() if ui_chart['input'][k]!=v]
                assert set(normalized)<= {'dst_enabled','fold'} and not chart['input']['manual_dst'], {k:(chart['input'][k],ui_chart['input'][k]) for k in normalized}
                assert exact({k:v for k,v in chart.items() if k!='input'})==exact({k:v for k,v in ui_chart.items() if k!='input'})
                chart=ui_chart
                window.apply_chart(chart);QTest.qWait(50);app.processEvents()
                assert window.export_button.isEnabled(),(ident,'stale chart')
                assert window.wheel.canvas.chart['cusps']==chart['cusps']
                for i,p in enumerate(chart['points']):
                    assert window.positions.item(i,2).text()==str(p['house'])
                for i,cusp in enumerate(chart['cusps']):
                    assert window.houses.item(i,1).text()==localized_zodiac(cusp)
                base=output/(ident+'-'+lang)
                window.grab().save(str(base)+'-desktop.png')
                window.wheel.canvas.grab().save(str(base)+'-wheel.png')
                export_chart(chart,str(base)+'.png',size=1200)
                export_chart(chart,str(base)+'.svg',format='svg')
                export_html(chart,str(base)+'.html',template_dir=TEMPLATES/lang)
                checks.append(dict(case=ident,language=lang,export_enabled=True,all_table_houses_match=True,all_cusps_match=True,ui_normalized_fields=normalized,astronomical_output_exactly_matches_fixed_case=True))
            window.close()
    (output/'desktop-checks.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
    print('Desktop, PNG, SVG and HTML:',len(checks),'case/language combinations')


if __name__=='__main__':check(sys.argv[1])
