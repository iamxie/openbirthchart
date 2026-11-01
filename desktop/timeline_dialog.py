# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Roomy, navigable event details, separate from the timeline's canvas."""
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,
    QTabWidget,QWidget,QTextBrowser,QComboBox)
from .i18n import tr,language
from .report import TEMPLATES
from .timeline_details import local_time,overlapping_events
from .timeline_report import labels_for,event_html,event_title,overlaps_html


class EventDetailDialog(QDialog):
    def __init__(self,page):
        super().__init__(page)
        self.page=page;self.result=None;self.current_event=None;self.history=[]
        self.setWindowTitle(tr('事件詳情'))
        available=self.screen().availableGeometry()
        self.resize(min(1080,available.width()-40),min(740,available.height()-60))
        self.labels=labels_for(TEMPLATES/language())
        layout=QVBoxLayout(self)
        toolbar=QHBoxLayout()
        self.back=QPushButton(tr('上一個事件'));toolbar.addWidget(self.back)
        self.title=QLabel();self.title.setWordWrap(True);self.title.setObjectName('chartTitle');toolbar.addWidget(self.title,1)
        zoom=QPushButton(tr('放大查看這段時間'));toolbar.addWidget(zoom)
        layout.addLayout(toolbar)
        self.tabs=QTabWidget();layout.addWidget(self.tabs,1)
        self.details=QTextBrowser();self.details.setOpenLinks(False)
        self.details.document().setDefaultStyleSheet('table{border-collapse:collapse}td,th{padding:7px;border:1px solid #ded3c6}th{background:#efe7da}h2,h3{color:#995434}')
        self.tabs.addTab(self.details,tr('星座歷程與精確成相'))
        others=QWidget();other_layout=QVBoxLayout(others)
        row=QHBoxLayout();row.addWidget(QLabel(tr('查看範圍')))
        self.scope=QComboBox();row.addWidget(self.scope,1);other_layout.addLayout(row)
        self.overlaps=QTextBrowser();self.overlaps.setOpenLinks(False)
        self.overlaps.document().setDefaultStyleSheet(self.details.document().defaultStyleSheet())
        other_layout.addWidget(self.overlaps,1)
        self.tabs.addTab(others,tr('同時事件'))
        self.scope.currentIndexChanged.connect(self.update_overlaps)
        self.overlaps.anchorClicked.connect(self.navigate)
        self.back.clicked.connect(self.go_back)
        zoom.clicked.connect(self.focus_event)

    def set_event(self,result,event,remember=True):
        if result is not self.result:self.history=[]
        elif remember and self.current_event is not None and self.current_event is not event:self.history.append(self.current_event)
        self.result,self.current_event=result,event
        self.back.setEnabled(bool(self.history))
        self.title.setText(event_title(event,self.labels))
        self.details.setHtml(event_html(result,event,self.labels))
        self.scope.blockSignals(True);self.scope.clear()
        self.scope.addItem(tr('整段事件的重疊區間'),None)
        self.scope.addItem(tr('事件開始當下')+' · '+local_time(event.start,result.request.zone),event.start)
        for stamp in event.exact:self.scope.addItem(tr('精確成相當下')+' · '+local_time(stamp,result.request.zone),stamp)
        self.scope.addItem(tr('事件結束當下')+' · '+local_time(event.end,result.request.zone),event.end)
        self.scope.blockSignals(False);self.update_overlaps()

    def update_overlaps(self):
        if self.current_event is None:return
        stamp=self.scope.currentData()
        self.overlaps.setHtml(overlaps_html(self.result,self.current_event,self.labels,stamp,'event:'))
        self.tabs.setTabText(1,tr('同時事件')+f' ({len(overlapping_events(self.result,self.current_event,stamp))})')

    def navigate(self,url):
        if url.scheme()!='event':return
        try:event=self.result.events[int(url.path())]
        except (IndexError,ValueError):return
        self.page.canvas.selection=event;self.page.canvas.update()
        self.set_event(self.result,event)
        self.tabs.setCurrentIndex(0)

    def go_back(self):
        if self.history:
            event=self.history.pop();self.page.canvas.selection=event;self.page.canvas.update()
            self.set_event(self.result,event,remember=False)

    def focus_event(self):
        self.page.canvas.selection=self.current_event
        self.page.focus_selection();self.hide()
