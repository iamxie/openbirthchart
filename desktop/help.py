# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Offline chart notices and shared, bundled help. No network is required."""
from common import ROOT
from .i18n import tr, language


def has_azimuth_notice(chart):
    return bool(chart) and any(n['code'] in ('azimuth_house_numbering','azimuth_numbering_aligned') for n in chart.get('house_notices',[]))


def has_aligned_azimuth_notice(chart):
    return bool(chart) and any(n['code']=='azimuth_numbering_aligned' for n in chart.get('house_notices',[]))


def azimuth_notice_text(chart=None):
    if has_aligned_azimuth_notice(chart):
        return tr('此盤的 Azimuth 空間宮號已依宮頭編號校正；可能與其他軟體不同。')
    return tr('此盤的 Azimuth 宮號存在已知編號差異，請審慎使用歸宮結果。')


def article_html(locale):
    return (ROOT/'docs'/('azimuth-'+locale+'.html')).read_text(encoding='utf-8')


def show_azimuth_help(parent):
    from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextBrowser, QDialogButtonBox
    from PySide6.QtCore import QTimer
    dialog=QDialog(parent);dialog.setWindowTitle(tr('Azimuth 宮制與歸宮說明'))
    dialog.resize(760,650);layout=QVBoxLayout(dialog)
    browser=QTextBrowser();browser.setOpenExternalLinks(True)
    browser.setMarkdown((ROOT/'docs/azimuth.md').read_text(encoding='utf-8'))
    layout.addWidget(browser)
    buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    buttons.rejected.connect(dialog.reject);layout.addWidget(buttons)
    if language()=='en-US':
        cursor=browser.document().find('Azimuth houses and the current placement notice')
        if not cursor.isNull():
            cursor.setPosition(cursor.selectionStart());browser.setTextCursor(cursor)
            def align_heading():
                top=browser.document().documentLayout().blockBoundingRect(cursor.block()).top()
                browser.verticalScrollBar().setValue(int(top))
            QTimer.singleShot(0,align_heading)
    dialog.exec()
