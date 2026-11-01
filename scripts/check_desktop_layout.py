# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Offscreen visual QA across sizes, scroll positions, panels and scale factors."""
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
from pathlib import Path
import sys,json,argparse
root=Path(__file__).resolve().parents[1];sys.path[:0]=[str(root),str(root/'scripts')]
from PySide6.QtWidgets import QApplication,QLabel,QFrame
from PySide6.QtGui import QFontDatabase,QFont
from PySide6.QtCore import QPoint,QCoreApplication,QEvent
from PySide6.QtTest import QTest
from desktop.window import MainWindow
from desktop.storage import ProfileStore
from desktop.model import BirthInput,APP_VERSION,ASPECTS
from dataclasses import asdict

app=QApplication([]);font=QFontDatabase.addApplicationFont(str(root/'data/desktop/NotoSansTC.ttf'))
parser=argparse.ArgumentParser();parser.add_argument('--language',choices=['zh-TW','en-US'],default='zh-TW')
parser.add_argument('--chart',type=Path,default=root/'results/desktop/openbirthchart-0.2.0-final-source/chart.json')
args=parser.parse_args()
from desktop.i18n import install_language
install_language(app,args.language)
app.setFont(QFont(QFontDatabase.applicationFontFamilies(font)[0],10))
out=root/'results/desktop'/('layout-'+APP_VERSION+'-'+args.language+'-scale-'+os.environ.get('QT_SCALE_FACTOR','1'));out.mkdir(parents=True,exist_ok=True)
w=MainWindow(store=ProfileStore(out/'unused.sqlite'),prompt_unsaved=False);w.show()
chart=json.loads(args.chart.read_text(encoding='utf-8'))
w.restore_profile(dict(schema=1,input=chart['input'],custom_orbs=False,orb_values={str(a):o for a,_,o,_,_ in ASPECTS}))
w.apply_chart(chart);checks=[]
def settle():
    for _ in range(4):app.processEvents();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);QTest.qWait(15)
def visible(widget):
    point=widget.mapTo(w,QPoint(0,0))
    return w.rect().contains(point) and w.rect().contains(widget.mapTo(w,widget.rect().bottomRight())) and widget.isVisible()
for width,height in [(1440,900),(1280,720),(1024,650),(920,540)]:
    w.resize(width,height);w.tabs.setCurrentIndex(0)
    for expanded in (False,True):
        w.advanced_toggle.setChecked(expanded);settle()
        scroll=w.form_scroll.verticalScrollBar()
        for position in [0,scroll.maximum()//2,scroll.maximum()]:
            scroll.setValue(position);settle()
            assert visible(w.calculate_button) and visible(w.status),(width,height,'hidden action/status')
            assert w.form_scroll.horizontalScrollBar().maximum()==0,(width,height,'form overflow')
            name=f'{width}x{height}-'+('expanded' if expanded else 'collapsed')+f'-scroll{position}'
            w.grab().save(str(out/(name+'.png')))
        checks.append(dict(size=[width,height],expanded=expanded,action_visible=True,status_visible=True,scroll_max=scroll.maximum()))
    w.tabs.setCurrentIndex(3);settle();w.grab().save(str(out/f'{width}x{height}-aspects.png'))
    if w.matrix.height()-16>=len(w.matrix.points)*20+34:
        assert w.matrix.table.verticalScrollBar().maximum()==0,(width,height,'unexpected matrix overflow')
    else:
        assert w.matrix.table.verticalScrollBar().maximum()>0,(width,height,'clipped matrix without scrolling')
        w.matrix.table.scrollToBottom();settle()
        last=w.matrix.table.model().index(w.matrix.table.rowCount()-1,0)
        assert w.matrix.table.viewport().rect().contains(w.matrix.table.visualRect(last)),(width,height,'last matrix row inaccessible')
        w.grab().save(str(out/f'{width}x{height}-aspects-bottom.png'))
    assert w.matrix.table.horizontalScrollBar().maximum()==0,(width,height,'matrix horizontal overflow')
    assert visible(w.matrix.table),(width,height,'matrix outside viewport')
    w.tabs.setCurrentIndex(0);w.toggle_form();settle();w.grab().save(str(out/f'{width}x{height}-chart-focus.png'));w.toggle_form()
    # Every section title belongs inside its own card; no floating group-box text.
    for frame in w.form_scroll.findChildren(QFrame):
        if frame.objectName()=='section':
            label=frame.findChild(QLabel,'sectionTitle');assert frame.rect().contains(label.geometry())
(out/'checks.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
print(f'Layout checks passed: {len(checks)} size/expanded combinations, top/middle/bottom and focused chart.')
w.close();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()
