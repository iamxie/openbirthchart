# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Capture the real offline help dialog in both interface languages."""
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from PySide6.QtWidgets import QApplication,QTextBrowser
from PySide6.QtCore import QTimer,QCoreApplication,QEvent
from PySide6.QtGui import QFontDatabase
from desktop.i18n import install_language
from desktop.window import MainWindow
from desktop.storage import ProfileStore
from desktop.help import show_azimuth_help
from desktop.model import APP_VERSION

app=QApplication([]);QFontDatabase.addApplicationFont(str(ROOT/'data/desktop/NotoSansTC.ttf'))
out=ROOT/'results/desktop'/('review-'+APP_VERSION)/'help';out.mkdir(parents=True,exist_ok=True)
checks=[]
for locale in ('zh-TW','en-US'):
    install_language(app,locale)
    w=MainWindow(store=ProfileStore(out/(locale+'.sqlite')),prompt_unsaved=False)
    w.show();app.processEvents()
    def capture():
        dialog=app.activeModalWidget();assert dialog is not None
        browser=dialog.findChild(QTextBrowser);text=browser.toPlainText()
        assert 'Azimuth 宮制與目前的歸宮提示' in text and 'Azimuth houses and the current placement notice' in text
        assert browser.horizontalScrollBar().maximum()==0
        if locale=='en-US':
            assert browser.verticalScrollBar().value()>0
            assert browser.cursorRect().top()<browser.fontMetrics().height()*2
        dialog.grab().save(str(out/(locale+'.png')))
        checks.append(dict(locale=locale,title=dialog.windowTitle(),bilingual_content=True,scroll=browser.verticalScrollBar().value()))
        browser.verticalScrollBar().setValue(browser.verticalScrollBar().maximum());app.processEvents()
        dialog.grab().save(str(out/(locale+'-bottom.png')));dialog.reject()
    QTimer.singleShot(200,capture);show_azimuth_help(w)
    w.close();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()
(out/'checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
print('Both offline help dialogs verified.')
