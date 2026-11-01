# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Prominent, offline legal notices and complete application license."""
from common import ROOT
from .i18n import tr
from .model import APP_VERSION

def show_legal(parent):
    from PySide6.QtWidgets import QDialog,QVBoxLayout,QTabWidget,QTextBrowser,QDialogButtonBox
    dialog=QDialog(parent);dialog.setObjectName('legalDialog')
    dialog.setWindowTitle(tr('關於與授權')+' · Open BirthChart '+APP_VERSION)
    dialog.resize(780,620);layout=QVBoxLayout(dialog);tabs=QTabWidget();layout.addWidget(tabs)
    for title,filename,plain in [(tr('授權說明'),'NOTICE.md',False),('AGPL-3.0-only','LICENSE',True),(tr('第三方元件'),'THIRD_PARTY_DESKTOP.md',False)]:
        view=QTextBrowser();view.setOpenExternalLinks(True)
        text=(ROOT/filename).read_text(encoding='utf-8')
        if plain:view.setPlainText(text)
        else:view.setMarkdown(text)
        tabs.addTab(view,title)
    buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Close);buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons);dialog.exec()
