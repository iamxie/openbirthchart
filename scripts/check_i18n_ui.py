# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Capture both interface languages and scan app-owned text using isolated data."""
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import json,sys,re
from pathlib import Path
from dataclasses import asdict
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from PySide6.QtWidgets import QApplication,QLabel,QAbstractButton,QComboBox,QLineEdit,QTabWidget,QGroupBox,QDialog,QMessageBox
from PySide6.QtCore import QTimer,QCoreApplication,QEvent
from PySide6.QtTest import QTest
from PySide6.QtGui import QFontDatabase
from desktop.i18n import install_language
from desktop.window import MainWindow
from desktop.storage import ProfileStore,DuplicateProfile
from desktop.dialogs import ExportDialog,LanguageDialog
from desktop.geocoding import GeocodeDialog
from desktop.model import APP_VERSION,ASPECTS

app=QApplication([]);QFontDatabase.addApplicationFont(str(ROOT/'data/desktop/NotoSansTC.ttf'))
fixture=json.loads((ROOT/'results/desktop/openbirthchart-0.2.0-final-source/chart.json').read_text(encoding='utf-8'))
fixture['input'].update(name='Alex Example',gender='男',notes='Example notes for interface review.')
payload=dict(schema=1,input=fixture['input'],custom_orbs=False,orb_values={str(a):o for a,_,o,_,_ in ASPECTS})

def settle():
    for _ in range(4):app.processEvents();QTest.qWait(15)

for lang in ('zh-TW','en-US'):
    install_language(app,lang)
    out=ROOT/'results/desktop'/('i18n-'+APP_VERSION)/lang;out.mkdir(parents=True,exist_ok=True)
    store=ProfileStore(out/'isolated.sqlite')
    # Reuse the fixture record if the inspection script is rerun.
    rows=store.list();ident=rows[0]['id'] if rows else store.save(payload)
    w=MainWindow(store=store,prompt_unsaved=False);w.resize(1440,900);w.show();settle()
    w.grab().save(str(out/'blank.png'));w.restore_profile(payload,ident);w.apply_chart(fixture);settle()
    for label in w.wheel.rail.findChildren(QLabel):
        if '<span' in label.text():
            assert label.height()>=label.fontMetrics().height(),(lang,'clipped legend',label.text())
    for index,label in enumerate(('chart','positions','houses','aspects')):
        w.tabs.setCurrentIndex(index);settle();w.grab().save(str(out/(label+'.png')))
    w.tabs.widget(3).setCurrentIndex(1);settle();w.grab().save(str(out/'aspect-details.png'))
    w.tabs.setCurrentIndex(0);w.advanced_toggle.setChecked(True);w.form_scroll.verticalScrollBar().setValue(w.form_scroll.verticalScrollBar().maximum());settle()
    w.grab().save(str(out/'advanced.png'))
    leaked=[]
    def scan(widget):
        if lang!='en-US':return
        for obj in [widget]+widget.findChildren(QLabel)+widget.findChildren(QAbstractButton)+widget.findChildren(QComboBox)+widget.findChildren(QLineEdit)+widget.findChildren(QGroupBox)+widget.findChildren(QTabWidget):
            values=[]
            if hasattr(obj,'text'):values.append(obj.text())
            if isinstance(obj,QComboBox):values.extend(obj.itemText(i) for i in range(obj.count()))
            if isinstance(obj,QLineEdit):values.append(obj.placeholderText())
            if isinstance(obj,QGroupBox):values.append(obj.title())
            if isinstance(obj,QTabWidget):values.extend(obj.tabText(i) for i in range(obj.count()))
            values.extend((obj.toolTip(),obj.windowTitle()))
            for value in values:
                if re.search('[\u3400-\u9fff]',value) and value not in ('語言 / Language','繁體中文'):
                    leaked.append(value)
    scan(w)
    for dialog,label in ((ExportDialog(w),'export-dialog'),(LanguageDialog(lang,w),'language-dialog'),(GeocodeDialog(w),'address-dialog')):
        dialog.show();settle();scan(dialog);dialog.grab().save(str(out/(label+'.png')));dialog.reject();dialog.deleteLater();settle()
    def capture_modal(label):
        def capture():
            dialog=app.activeModalWidget();assert dialog is not None
            scan(dialog);dialog.grab().save(str(out/(label+'.png')));dialog.reject()
        QTimer.singleShot(100,capture)
    capture_modal('load-dialog');w.choose_record()
    row=dict(id=ident,**fixture['input']);capture_modal('duplicate-dialog');w.confirm_duplicate(DuplicateProfile([row]),payload)
    w.prompt_unsaved=True;w.name.setText('Unsaved Example');capture_modal('unsaved-dialog');w.confirm_discard()
    w.prompt_unsaved=False;w.close();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()
    (out/'text-scan.json').write_text(json.dumps(sorted(set(leaked)),ensure_ascii=False,indent=2),encoding='utf-8')
    assert not leaked,(lang,'untranslated app text; see text-scan.json')
    print(lang,'captured and scanned')
