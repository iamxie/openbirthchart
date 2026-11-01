# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Capture real Qt dialog states using an isolated fixture database, offline."""
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
from pathlib import Path
import sys,json
root=Path(__file__).resolve().parents[1];sys.path[:0]=[str(root),str(root/'scripts')]
from PySide6.QtWidgets import QApplication,QMessageBox
from PySide6.QtCore import QTimer,QCoreApplication,QEvent
from PySide6.QtTest import QTest
from PySide6.QtGui import QFontDatabase
from desktop.window import MainWindow
from desktop.storage import ProfileStore
from desktop.model import APP_VERSION,ASPECTS
from desktop.dialogs import ExportDialog
from desktop.geocoding import GeocodeDialog

app=QApplication([]);QFontDatabase.addApplicationFont(str(root/'data/desktop/NotoSansTC.ttf'))
out=root/'results/desktop'/('review-'+APP_VERSION)
w=MainWindow(store=ProfileStore(out/'data.sqlite'),prompt_unsaved=False);w.show()
chart=json.loads((out/'chart.json').read_text(encoding='utf-8'))
w.restore_profile(dict(schema=1,input=chart['input'],custom_orbs=False,orb_values={str(a):o for a,_,o,_,_ in ASPECTS}))
w.apply_chart(chart);w.resize(1440,900)
def settle():
    for _ in range(4):app.processEvents();QTest.qWait(20)
settle()
for index,label in [(1,'positions'),(2,'houses')]:
    w.tabs.setCurrentIndex(index);settle();w.grab().save(str(out/(label+'.png')))
w.tabs.setCurrentIndex(3);w.tabs.widget(3).setCurrentIndex(1);settle();w.grab().save(str(out/'aspect-details.png'))
for dialog,label in [(ExportDialog(w),'export-dialog'),(GeocodeDialog(w),'address-dialog')]:
    dialog.show();settle();dialog.grab().save(str(out/(label+'.png')));dialog.reject();dialog.deleteLater();settle()
def capture_modal():
    dialog=app.activeModalWidget()
    assert dialog is not None
    dialog.grab().save(str(out/'load-dialog.png'));dialog.reject()
QTimer.singleShot(150,capture_modal);w.choose_record()
message=QMessageBox(QMessageBox.Icon.Warning,'請確認出生資料','請填寫出生日期後再排星盤。',QMessageBox.StandardButton.Ok,w)
message.show();settle();message.grab().save(str(out/'warning-dialog.png'));message.accept()
w.close();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()
print('Captured tables, export, address, load and warning dialogs; no address request made.')
