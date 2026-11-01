# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Render representative live UI and bilingual exports in isolated profiles."""
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import copy,json,sys,tempfile
from dataclasses import asdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from latitude_mode_audit import OUT,write
from audit_latitude_results import rows
from desktop.model import ASPECTS,ChartEngine,house_direction
from desktop.window import MainWindow
from desktop.storage import ProfileStore
from desktop.i18n import install_language
from desktop.chart import export_chart,WheelCanvas
from desktop.report import export_html,TEMPLATES,render_html
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase,QFont

app=QApplication([])
font=QFontDatabase.addApplicationFont(str(ROOT/'data/desktop/NotoSansTC.ttf'))
app.setFont(QFont(QFontDatabase.applicationFontFamilies(font)[0],10));engine=ChartEngine()
on=rows(OUT/'final/complete-on/results.jsonl.gz');off=rows(OUT/'final/complete-off/results.jsonl.gz')
valid=[r for r in on.values() if r['result']['status']=='ok']
reverse=next(r['id'] for r in valid if r['raw']['input']['system']=='H' and house_direction(r['raw']['cusps'])<0)
koch=max((r for r in valid if r['raw']['input']['system']=='K'),key=lambda r:sum(p['house'] is None for p in r['raw']['points']))['id']
ids=['complete-1904-01-H',reverse,'complete-1941-07-C','complete-1941-07-R',
     'complete-1914-05-T',koch,'complete-1904-01-W','complete-1904-01-P']
assert len(set(ids))==8
folder=OUT/'exports';folder.mkdir(exist_ok=True);checks=[]
with tempfile.TemporaryDirectory() as tmp:
    for ident in ids:
        for mode,data in (('on',on),('off',off)):
            chart=copy.deepcopy(data[ident]['raw']);chart['orbs']={int(k):v for k,v in chart['orbs'].items()};prefix=f'{ident}-{mode}'
            for locale in ('zh-TW','en-US'):
                install_language(app,locale)
                w=MainWindow(store=ProfileStore(Path(tmp)/f'{prefix}-{locale}.sqlite'),prompt_unsaved=False)
                try:
                    w.restore_profile(dict(schema=1,input=copy.deepcopy(chart['input']),custom_orbs=False,
                        orb_values={str(a):o for a,_,o,_,_ in ASPECTS}))
                    ui_chart=engine.calculate(w.input());w.apply_chart(ui_chart)
                    assert ui_chart['all_points']==chart['all_points']
                    assert ui_chart['cusps']==chart['cusps'] and w.export_ready()
                    assert w.house_latitude.isChecked()==(mode=='on')
                    for i,p in enumerate(chart['points']):
                        assert w.positions.item(i,2).text()==(str(p['house']) if p['house'] is not None else ('未定義' if locale=='zh-TW' else 'Undefined'))
                    for width,height in ((1440,1000),(960,720)):
                        w.resize(width,height);w.show();app.processEvents()
                        w.form_scroll.ensureWidgetVisible(w.house_latitude);app.processEvents()
                        assert w.house_latitude.isVisible()
                        assert w.house_latitude.width()>=w.house_latitude.sizeHint().width()
                        w.grab().save(str(folder/f'{prefix}-{locale}-desktop-{width}.png'))
                    canvas=WheelCanvas();canvas.resize(1000,1000);canvas.set_chart(chart);canvas.show();app.processEvents()
                    canvas.grab().save(str(folder/f'{prefix}-{locale}-wheel.png'));canvas.close();canvas.deleteLater()
                    export_chart(chart,folder/f'{prefix}-{locale}.png',size=1000)
                    export_chart(chart,folder/f'{prefix}-{locale}.svg',format='svg')
                    # Deliberately opposite UI language verifies export independence.
                    install_language(app,'en-US' if locale=='zh-TW' else 'zh-TW')
                    export_html(chart,folder/f'{prefix}-{locale}.html',template_dir=TEMPLATES/locale)
                    checks.append(dict(case=ident,mode=mode,language=locale,points=len(chart['points']),
                        table_houses=[p['house'] for p in chart['points']],cusps=chart['cusps'],
                        undefined=sum(p['house'] is None for p in chart['points']),export_ready=True))
                finally:w.close();w.deleteLater();app.processEvents()
            print(prefix,'bilingual exports verified',flush=True)
write(OUT/'export-checks.json',checks)
