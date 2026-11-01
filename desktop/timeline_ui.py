# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Sky timeline workbench. No personal profile or hardware fields."""
from datetime import datetime, timezone
from pathlib import Path
from html import escape
import math
import threading
import time
import json
from zoneinfo import ZoneInfo

from PySide6.QtCore import Qt, QDate, QTime, QThread, Signal, QTimer, QRectF, QPointF
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF, QPixmap, QIcon
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QPushButton, QScrollArea, QSplitter, QFrame, QDateEdit, QTimeEdit, QComboBox,
    QDoubleSpinBox, QGroupBox, QProgressBar, QTextBrowser, QToolTip, QCompleter, QDialog, QFileDialog, QMessageBox,
    QListWidget, QListWidgetItem, QDialogButtonBox)

from .i18n import tr, error_text
from .model import available_timezones, BirthInput, resolve_local
from .errors import AmbiguousTimeError, UserError
from .timeline import (TimelineInput, TimelineResult, calculate_timeline, Cancelled,
                       BODY_NAMES, RETRO_IDS, ANGLES, DEFAULT_ORBS)
from .theme import TEXT, MUTED, BORDER, SURFACE, SOFT, ACCENT, primary
from .aspects import draw_symbol
from .fields import DateField,TimeField
from .settings import default_orbs
from .timeline_details import event_spans
from .timeline_report import labels_for, sign_description, sign_name, color_legend, sign_description_html
from .timeline_dialog import EventDetailDialog
from .report import TEMPLATES
from .i18n import language

ASPECT_SYMBOLS = {0:'☌',90:'□',120:'△',180:'☍'}
from .timeline_palette import COLORS
from .zodiac import draw_zodiac


def event_label(event):
    if event.kind == 'retro':
        return tr('{body} 逆行',body=tr(BODY_NAMES[event.a]))
    return f'{tr(BODY_NAMES[event.a])} {event.angle}° {tr(BODY_NAMES[event.b])}'


def aspect_icon(angle):
    pixmap=QPixmap(40,40)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter=QPainter(pixmap)
    draw_symbol(painter,QRectF(0,0,40,40),angle,COLORS[angle])
    painter.end()
    pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)


def local_time(stamp, zone, seconds=False):
    return datetime.fromtimestamp(stamp,ZoneInfo(zone)).strftime('%Y/%m/%d %H:%M:%S %z' if seconds else '%Y/%m/%d %H:%M %z')


def duration(seconds):
    seconds = max(0,int(seconds))
    if seconds < 60:
        return tr('{n} 秒',n=seconds)
    if seconds < 3600:
        return tr('{n} 分鐘',n=seconds//60)
    hours, minutes = divmod(seconds//60,60)
    return tr('{hours} 小時 {minutes} 分鐘',hours=hours,minutes=minutes)


class TimelineWorker(QThread):
    progress = Signal(dict)
    succeeded = Signal(object)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, request, parent=None, workers=None):
        super().__init__(parent)
        self.request = request
        self.stop = threading.Event()
        self.workers = workers
        self.history_path = getattr(parent,'history_path',None)

    def run(self):
        history=None;run_id=None
        try:
            if self.history_path:
                from .sky_history import SkyHistory
                history=SkyHistory(self.history_path)
                start,end,_=self.request.resolve()
                run_id=history.begin(self.request,math.ceil((end-start).total_seconds()/600)+1)
            save=(lambda offset,stamps,data:history.append(run_id,offset,stamps,data)) if history else None
            result = calculate_timeline(self.request,self.progress.emit,self.stop.is_set,self.workers,samples_ready=save)
            if self.stop.is_set():
                raise Cancelled()
            if history:
                self.progress.emit(dict(stage='save',done=0,total=1,elapsed=result.elapsed,stage_elapsed=0))
                history.complete(run_id,result);result.history_id=run_id
            self.succeeded.emit(result)
        except Cancelled:
            if history and run_id:
                try:history.abort(run_id,'cancelled')
                except Exception:pass
            self.cancelled.emit()
        except Exception as exc:
            if history and run_id:
                try:history.abort(run_id,'failed')
                except Exception:pass  # Incomplete runs remain ineligible for playback.
            self.failed.emit(error_text(exc))


class TimelineAxis(QWidget):
    def __init__(self, chart, parent=None):
        super().__init__(parent)
        self.chart = chart
        self.setFixedHeight(36)

    def paintEvent(self,event):
        p = QPainter(self)
        p.fillRect(self.rect(),QColor(SOFT))
        p.setPen(QColor(MUTED))
        p.drawText(QRectF(12,0,self.chart.label_width-15,36),Qt.AlignmentFlag.AlignVCenter,tr('天體／相位'))
        p.setClipRect(QRectF(self.chart.label_width,0,max(1,self.width()-self.chart.label_width),36))
        for stamp,text in self.chart.ticks():
            x = self.chart.x(stamp)
            width = p.fontMetrics().horizontalAdvance(text)+6
            x = min(x+4,self.chart.width()-width-4)
            if x >= self.chart.label_width:
                p.drawText(QRectF(x,0,width,36),Qt.AlignmentFlag.AlignVCenter,text)


class TimelineCanvas(QWidget):
    selected = Signal(object)
    view_changed = Signal()

    def __init__(self,parent=None):
        super().__init__(parent)
        self.result = None
        self.rows = []
        self.selection = None
        self.start = self.end = 0.
        self.hits = []
        self.label_width = 165
        self.row_height = 56
        self.labels = labels_for(TEMPLATES/language())
        self.body = None
        self.angle = 'all'
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(tr('天象時間軸'))
        self.setAccessibleDescription(tr('點選色帶查看事件；方向鍵切換事件。'))

    def set_result(self,result):
        self.result = result
        self.selection = None
        if result:
            self.start,self.end = result.start,max(result.end,result.start+60)
        self.rebuild()

    def rebuild(self):
        self.rows = []
        if self.result:
            self.rows.append(('heading',tr('逆行'),[]))
            for a in RETRO_IDS:
                if self.body is None or self.body==a:
                    self.rows.append(('lane',tr(BODY_NAMES[a]),[e for e in self.result.events if e.kind=='retro' and e.a==a]))
            if self.body in (0,1):
                self.rows.append(('empty',tr('這顆天體不列入逆行檢查。'),[]))
            self.rows.append(('heading',tr('相位區間'),[]))
            groups = {}
            for e in self.result.events:
                if e.kind!='aspect' or (self.body is not None and self.body not in (e.a,e.b)):
                    continue
                if self.angle=='hard' and e.angle not in (90,180):
                    continue
                if isinstance(self.angle,int) and e.angle!=self.angle:
                    continue
                groups.setdefault((e.a,e.b,e.angle),[]).append(e)
            for events in groups.values():
                self.rows.append(('lane',event_label(events[0]),events))
            if not groups:
                self.rows.append(('empty',tr('此範圍沒有符合篩選的相位。'),[]))
        self.setMinimumHeight(max(180,len(self.rows)*self.row_height))
        if self.selection and not any(self.selection in events for _,_,events in self.rows):
            self.selection = None
            self.selected.emit(None)
        self.update()
        self.view_changed.emit()

    def x(self,stamp):
        return self.label_width+(self.width()-self.label_width-12)*(stamp-self.start)/max(1,self.end-self.start)

    def ticks(self):
        if not self.result:
            return []
        zone = ZoneInfo(self.result.request.zone)
        span = self.end-self.start
        sample = '12/31' if span>86400*2 else '12/31 23:59'
        tick_width = self.fontMetrics().horizontalAdvance(sample)+18
        count = max(2,min(6,(self.width()-self.label_width)//tick_width))
        result = []
        for i in range(count):
            stamp = self.start+span*i/count
            dt = datetime.fromtimestamp(stamp,zone)
            text = dt.strftime('%m/%d') if span>86400*2 else dt.strftime('%m/%d %H:%M')
            result.append((stamp,text))
        return result

    def resizeEvent(self,event):
        super().resizeEvent(event)
        self.view_changed.emit()

    def paintEvent(self,event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(),QColor(SURFACE))
        self.hits = []
        if not self.result:
            p.setPen(QColor(MUTED))
            p.drawText(self.rect().adjusted(20,20,-20,-20),Qt.AlignmentFlag.AlignCenter|Qt.TextFlag.TextWordWrap,
                       tr('選擇時間範圍與時區，按「開始計算」查看天象。'))
            return
        for i,(kind,label,events) in enumerate(self.rows):
            y = i*self.row_height
            row = QRectF(0,y,self.width(),self.row_height)
            if kind=='heading':
                p.fillRect(row,QColor(SOFT))
                p.setPen(QColor(TEXT))
                p.drawText(row.adjusted(12,0,-12,0),Qt.AlignmentFlag.AlignVCenter,label)
                continue
            if kind=='empty':
                p.setPen(QColor(MUTED))
                p.drawText(row.adjusted(12,0,-12,0),Qt.AlignmentFlag.AlignVCenter,label)
                continue
            if self.selection in events:
                p.fillRect(row,QColor('#f7eadd'))
            p.setPen(QPen(QColor(BORDER),.5))
            p.drawLine(QPointF(0,y+self.row_height),QPointF(self.width(),y+self.row_height))
            for tick,_ in self.ticks():
                p.drawLine(QPointF(self.x(tick),y),QPointF(self.x(tick),y+self.row_height))
            p.setPen(QColor(TEXT))
            if events and events[0].kind=='aspect':
                e=events[0]
                first=tr(BODY_NAMES[e.a])
                text_width=p.fontMetrics().horizontalAdvance(first)
                p.drawText(QRectF(12,y,text_width,self.row_height),Qt.AlignmentFlag.AlignVCenter,first)
                draw_symbol(p,QRectF(16+text_width,y+9,20,20),e.angle,COLORS[e.angle])
                second=tr(BODY_NAMES[e.b])
                available=self.label_width-text_width-43
                second=p.fontMetrics().elidedText(second,Qt.TextElideMode.ElideRight,max(10,available))
                p.drawText(QRectF(39+text_width,y,max(10,available),self.row_height),Qt.AlignmentFlag.AlignVCenter,second)
            else:
                p.drawText(QRectF(12,y,self.label_width-16,self.row_height),Qt.AlignmentFlag.AlignVCenter,label)
            visible = [e for e in events if e.end>=self.start and e.start<=self.end]
            if not visible:
                p.setPen(QColor(MUTED))
                p.drawText(QRectF(self.label_width+8,y,self.width()-self.label_width-16,self.row_height),
                    Qt.AlignmentFlag.AlignVCenter,tr('此視窗無事件') if events else tr('區間內無逆行'))
            p.save()
            p.setClipRect(QRectF(self.label_width,y,self.width()-self.label_width-8,self.row_height))
            for e in visible:
                color = QColor(COLORS[e.angle])
                left,right = self.x(max(e.start,self.start)),self.x(min(e.end,self.end))
                rect = QRectF(left,y+10,max(3,right-left),self.row_height-20)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(color)
                p.drawRoundedRect(rect,3,3)
                for lo,hi,signs in event_spans(self.result,e):
                    if hi<self.start or lo>self.end:continue
                    l,r=self.x(max(lo,self.start)),self.x(min(hi,self.end))
                    p.setPen(QPen(QColor(SURFACE),1,Qt.PenStyle.DashLine))
                    if e.start<lo<e.end:
                        p.drawLine(QPointF(l,rect.top()),QPointF(l,rect.bottom()))
                    p.setPen(QColor(SURFACE))
                    font=p.font();small=p.font();small.setPointSizeF(max(8,font.pointSizeF()-2));p.setFont(small)
                    for j,sign in enumerate(signs):
                        text=sign_name(sign,self.labels)
                        icon_size=12 if sign is not None and self.labels['lang'].startswith('en') else 0
                        text_width=p.fontMetrics().horizontalAdvance(text)
                        total_width=text_width+(icon_size+4 if icon_size else 0)
                        if total_width+8<r-l:
                            line_height=rect.height()/len(signs)
                            tx=(l+r-total_width)/2
                            cy=rect.top()+(j+.5)*line_height
                            if icon_size:
                                draw_zodiac(p,sign,QPointF(tx+icon_size/2,cy),icon_size,SURFACE)
                                tx+=icon_size+4
                            p.drawText(QRectF(tx,rect.top()+j*line_height,text_width,line_height),Qt.AlignmentFlag.AlignCenter,text)
                    p.setFont(font)
                if e is self.selection:
                    p.setPen(QPen(color,1.5))
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawRoundedRect(rect.adjusted(-2,-3,2,3),4,4)
                self.hits.append((rect.adjusted(-4,-8,4,8),e))
                for exact in e.exact:
                    if self.start<=exact<=self.end:
                        x,cy = self.x(exact),y+7
                        p.setPen(QPen(QColor(SURFACE),1))
                        p.setBrush(color)
                        p.drawPolygon(QPolygonF([QPointF(x,cy-5),QPointF(x+5,cy),QPointF(x,cy+5),QPointF(x-5,cy)]))
            p.restore()

    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:
            for rect,e in reversed(self.hits):
                if rect.contains(event.position()):
                    self.selection = e
                    self.selected.emit(e)
                    self.update()
                    return
        super().mousePressEvent(event)

    def mouseMoveEvent(self,event):
        for rect,e in reversed(self.hits):
            if rect.contains(event.position()):
                text = event_label(e)+'\n'+local_time(e.start,self.result.request.zone)+'\n'+local_time(e.end,self.result.request.zone)
                text = escape(text).replace('\n','<br>')+'<br>'+sign_description_html(self.result,e,self.labels,icon_mode='qt')
                QToolTip.showText(event.globalPosition().toPoint(),text,self)
                return
        QToolTip.hideText()

    def keyPressEvent(self,event):
        if event.key() in (Qt.Key.Key_Left,Qt.Key.Key_Right,Qt.Key.Key_Up,Qt.Key.Key_Down):
            visible = [e for _,_,events in self.rows for e in events if e.end>=self.start and e.start<=self.end]
            if visible:
                index = visible.index(self.selection) if self.selection in visible else -1
                direction = -1 if event.key() in (Qt.Key.Key_Left,Qt.Key.Key_Up) else 1
                self.selection = visible[(index+direction)%len(visible)]
                self.selected.emit(self.selection)
                self.update()
            event.accept()
            return
        super().keyPressEvent(event)


class TimelinePage(QWidget):
    activity_changed = Signal()

    def __init__(self,parent=None,orb_provider=None,history_path=None):
        super().__init__(parent)
        self.orb_provider=orb_provider or default_orbs
        self.history_path=history_path
        self.player=None
        self.worker = None
        self.result = None
        self.last_progress = None
        self.started = 0.
        self.closing = False
        self.initializing = True
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        actions = QHBoxLayout()
        self.run_button = QPushButton(tr('開始計算'))
        primary(self.run_button)
        self.cancel_button = QPushButton(tr('取消計算'))
        self.cancel_button.hide()
        self.summary = QLabel(tr('每十分鐘掃描，局部細查事件時間。'))
        self.summary.setObjectName('hint')
        self.summary.setWordWrap(True)
        self.toggle_button = QPushButton(tr('收合設定'))
        self.history_button=QPushButton(tr('天象歷史'))
        self.history_button.setEnabled(history_path is not None)
        for widget in (self.run_button,self.cancel_button,self.summary):
            actions.addWidget(widget)
        actions.addStretch()
        actions.addWidget(self.history_button)
        actions.addWidget(self.toggle_button)
        layout.addLayout(actions)
        self.splitter = QSplitter()
        self.splitter.setChildrenCollapsible(False)
        layout.addWidget(self.splitter,1)
        self.settings_scroll = QScrollArea()
        self.settings_scroll.setWidgetResizable(True)
        self.settings_scroll.setMinimumWidth(310)
        self.settings_scroll.setMaximumWidth(400)
        self.settings_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.splitter.addWidget(self.settings_scroll)
        self.settings = QWidget()
        self.settings.setObjectName('settings')
        self.settings_scroll.setWidget(self.settings)
        settings_layout = QVBoxLayout(self.settings)
        settings_layout.setContentsMargins(0,6,10,16)
        settings_layout.setSpacing(18)

        def section(title):
            box = QFrame()
            box.setObjectName('section')
            box_layout = QVBoxLayout(box)
            box_layout.setContentsMargins(16,16,16,18)
            box_layout.setSpacing(12)
            label = QLabel(title)
            label.setObjectName('sectionTitle')
            box_layout.addWidget(label)
            settings_layout.addWidget(box)
            return box_layout

        time_layout = section(tr('01  時間範圍'))
        self.start_date = DateField(birth=False)
        self.start_date.setDate(QDate.currentDate())
        self.end_date = DateField(birth=False)
        self.end_date.setDate(QDate.currentDate().addMonths(1))
        self.start_time = TimeField(seconds=False)
        self.start_time.setTime(QTime(0,0))
        self.end_time = TimeField(seconds=False)
        self.end_time.setTime(QTime(23,59))
        self.start_fold,self.end_fold = QComboBox(),QComboBox()
        for title,date,clock,fold in ((tr('開始'),self.start_date,self.start_time,self.start_fold),
                                     (tr('結束'),self.end_date,self.end_time,self.end_fold)):
            time_layout.addWidget(QLabel(title))
            time_layout.addWidget(date)
            time_layout.addWidget(clock)
            fold.addItem(tr('重複鐘點：請選擇'),None)
            fold.addItem(tr('第一次（較早的時刻）'),0)
            fold.addItem(tr('第二次（較晚的時刻）'),1)
            time_layout.addWidget(fold)
            fold.hide()
        self.zone = QComboBox()
        self.zone.setEditable(True)
        self.zone.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.zone.setMinimumContentsLength(12)
        self.zone.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.zone.addItems(['Asia/Taipei','UTC']+sorted(available_timezones()-{'Asia/Taipei','UTC'}))
        self.zone.completer().setFilterMode(Qt.MatchFlag.MatchContains)
        self.zone.completer().setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        time_layout.addWidget(QLabel(tr('時區')))
        time_layout.addWidget(self.zone)
        self.time_note = QLabel()
        self.time_note.setWordWrap(True)
        self.time_note.setObjectName('hint')
        time_layout.addWidget(self.time_note)
        content_layout = section(tr('02  計算內容'))
        for text in (tr('逆行：水、金、火、木、土、天、海、冥，共八顆。'),
                     tr('相位：水星至冥王星，共 28 組配對；不含太陽與月亮。')):
            label = QLabel(text)
            label.setWordWrap(True)
            content_layout.addWidget(label)
        orb_note=QLabel(tr('相位容許度統一由上方「設定」修改。'))
        orb_note.setWordWrap(True);orb_note.setObjectName('hint');content_layout.addWidget(orb_note)
        settings_layout.addStretch()
        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(5,0,0,0)
        self.splitter.addWidget(center)
        heading = QLabel(tr('天象時間軸'))
        heading.setObjectName('chartTitle')
        heading_row=QHBoxLayout()
        heading_row.addWidget(heading,1)
        center_layout.addLayout(heading_row)
        self.range_label = QLabel()
        self.range_label.setWordWrap(True)
        self.range_label.setObjectName('hint')
        center_layout.addWidget(self.range_label)
        filters = QHBoxLayout()
        self.aspect_filter = QComboBox()
        for label,value in ((tr('全部四種相位'),'all'),(tr('只看 90°／180°'),'hard')):
            self.aspect_filter.addItem(label,value)
        for angle in ANGLES:
            self.aspect_filter.addItem(aspect_icon(angle),f'{angle}°',angle)
        self.body_filter = QComboBox()
        self.body_filter.addItem(tr('全部天體'),None)
        for i in RETRO_IDS:
            name=BODY_NAMES[i]
            self.body_filter.addItem(tr(name),i)
        self.zoom = QComboBox()
        for title,days in ((tr('全期'),None),(tr('月視圖'),30),(tr('週視圖'),7),(tr('日視圖'),1)):
            self.zoom.addItem(title,days)
        self.previous_button,self.next_button = QPushButton('‹'),QPushButton('›')
        self.previous_button.setFixedWidth(36)
        self.next_button.setFixedWidth(36)
        self.zoom.setMinimumWidth(145)
        self.zoom.setMaximumWidth(155)
        self.previous_button.setAccessibleName(tr('上一段時間'))
        self.next_button.setAccessibleName(tr('下一段時間'))
        for widget in (self.aspect_filter,self.body_filter,self.zoom,self.previous_button,self.next_button):
            filters.addWidget(widget)
        self.detail_button=QPushButton(tr('事件詳情'))
        self.export_button=QPushButton(tr('匯出文件'))
        self.player_button=QPushButton(tr('看實際星盤'))
        heading_row.addWidget(self.player_button)
        heading_row.addWidget(self.export_button)
        heading_row.addWidget(self.detail_button)
        center_layout.addLayout(filters)
        self.result_splitter = QSplitter()
        self.result_splitter.setChildrenCollapsible(False)
        center_layout.addWidget(self.result_splitter,1)
        chart_area = QWidget()
        chart_layout = QVBoxLayout(chart_area)
        chart_layout.setContentsMargins(0,0,0,0)
        chart_layout.setSpacing(0)
        self.canvas = TimelineCanvas()
        self.axis = TimelineAxis(self.canvas)
        chart_layout.addWidget(self.axis)
        self.chart_scroll = QScrollArea()
        self.chart_scroll.setWidgetResizable(True)
        self.chart_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.chart_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.chart_scroll.setWidget(self.canvas)
        chart_layout.addWidget(self.chart_scroll,1)
        legend = QLabel(color_legend(self.canvas.labels))
        legend.setObjectName('hint')
        legend.setWordWrap(True)
        chart_layout.addWidget(legend)
        sign_hint=QLabel(tr('◆ 精確成相，虛線為換座；上／下列分別對應兩顆天體。短區段可懸停或點選查看星座歷程。'))
        sign_hint.setWordWrap(True);sign_hint.setObjectName('hint');chart_layout.addWidget(sign_hint)
        self.result_splitter.addWidget(chart_area)
        self.splitter.setSizes([290,1100])
        self.status = QLabel(tr('設定時間範圍與時區，按「開始計算」。'))
        self.status.setObjectName('status')
        self.status.setWordWrap(True)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0,100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(10)
        self.progress_bar.hide()
        self.timing = QLabel()
        self.timing.setObjectName('hint')
        self.timing.setWordWrap(True)
        layout.addWidget(self.status)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.timing)
        self.run_button.clicked.connect(self.start_calculation)
        self.cancel_button.clicked.connect(self.cancel)
        self.toggle_button.clicked.connect(self.toggle_settings)
        self.aspect_filter.currentIndexChanged.connect(self.filter_changed)
        self.body_filter.currentIndexChanged.connect(self.filter_changed)
        self.zoom.currentIndexChanged.connect(self.zoom_changed)
        self.previous_button.clicked.connect(lambda:self.shift(-1))
        self.next_button.clicked.connect(lambda:self.shift(1))
        self.export_button.clicked.connect(self.export)
        self.detail_button.clicked.connect(self.show_detail_dialog)
        self.player_button.clicked.connect(self.show_player)
        self.history_button.clicked.connect(self.open_history)
        self.detail_dialog=None
        self.canvas.selected.connect(self.show_event)
        self.canvas.view_changed.connect(self.update_axis)
        self.heartbeat = QTimer(self)
        self.heartbeat.setInterval(1000)
        self.heartbeat.timeout.connect(self.update_elapsed)
        for widget in (self.start_date,self.end_date):
            widget.textChanged.connect(self.conditions_changed)
        for widget in (self.start_time,self.end_time):
            widget.textChanged.connect(self.conditions_changed)
        self.zone.editTextChanged.connect(self.conditions_changed)
        for widget in (self.start_fold,self.end_fold):
            widget.currentIndexChanged.connect(self.conditions_changed)
        self.initializing = False
        self.conditions_changed()
        self.show_event(None)

    def request(self):
        def iso(date,clock):
            return date.date().toString('yyyy-MM-dd')+'T'+clock.time().toString('HH:mm')
        return TimelineInput(iso(self.start_date,self.start_time),iso(self.end_date,self.end_time),
            self.zone.currentText(),tuple(self.orb_provider()[a] for a in ANGLES),
            self.start_fold.currentData(),self.end_fold.currentData())

    def conditions_changed(self,*args):
        if self.initializing:
            return
        self.enable_results(False)
        self.close_player()
        self.result = None
        self.canvas.set_result(None)
        self.show_event(None)
        self.range_label.clear()
        self.progress_bar.hide()
        self.timing.clear()
        try:request = self.request()
        except ValueError as exc:
            self.summary.setText(tr('請核對時間設定。'))
            self.time_note.setText(str(exc))
            self.status.setText(tr('設定時間範圍與時區，按「開始計算」。'))
            return
        for iso,combo in ((request.start,self.start_fold),(request.end,self.end_fold)):
            try:
                resolve_local(BirthInput(local_iso=iso,zone=request.zone))
                combo.hide()
            except AmbiguousTimeError:
                combo.show()
            except Exception:
                combo.hide()
        try:
            start,end,total = request.resolve()
            self.summary.setText(tr('每十分鐘掃描 · {n:,} 個掃描點',n=math.ceil((total-1)/10)+1))
            self.time_note.setText(tr('夏令時間依所選時區與日期自動判斷。'))
            self.status.setText(tr('設定已更新，按「開始計算」產生結果。'))
        except Exception as exc:
            self.summary.setText(tr('請核對時間設定。'))
            self.time_note.setText(error_text(exc))
            self.status.setText(tr('設定時間範圍與時區，按「開始計算」。'))
        self.enable_results(False)

    def enable_results(self,enabled):
        for widget in (self.aspect_filter,self.body_filter,self.zoom,self.previous_button,self.next_button,self.export_button):
            widget.setEnabled(enabled)
        self.player_button.setEnabled(enabled and self.history_path is not None and getattr(self.result,'history_id',None) is not None)

    def toggle_settings(self):
        show = self.settings_scroll.isHidden()
        self.settings_scroll.setVisible(show)
        self.toggle_button.setText(tr('收合設定') if show else tr('展開設定'))

    def start_calculation(self):
        if self.worker is not None:
            return
        try:
            request = self.request()
            request.resolve()
        except Exception as exc:
            self.status.setText(error_text(exc))
            return
        self.result = None
        self.close_player()
        self.history_button.setEnabled(False)
        self.canvas.set_result(None)
        self.show_event(None)
        self.settings.setEnabled(False)
        self.run_button.setEnabled(False)
        self.cancel_button.show()
        self.cancel_button.setEnabled(True)
        self.enable_results(False)
        self.progress_bar.show()
        self.progress_bar.setRange(0,0)
        self.status.setText(tr('正在準備星曆資料，請稍候。'))
        self.started = time.monotonic()
        self.last_progress = None
        self.heartbeat.start()
        self.worker = TimelineWorker(request,self)
        self.worker.progress.connect(self.on_progress)
        self.worker.succeeded.connect(self.apply_result)
        self.worker.cancelled.connect(self.on_cancelled)
        self.worker.failed.connect(self.on_failed)
        self.worker.finished.connect(self.worker_finished)
        self.activity_changed.emit()
        self.worker.start()

    def on_progress(self,payload):
        self.last_progress = payload
        if self.worker and self.worker.stop.is_set():
            return
        stage,done,total = payload['stage'],payload['done'],payload['total']
        if stage in ('prepare','merge','finish','save'):
            self.progress_bar.setRange(0,0)
            if stage=='prepare':
                self.status.setText(tr('正在準備星曆資料，請稍候。'))
            elif stage=='merge':
                self.status.setText(tr('正在接合逆行與相位區間。'))
            elif stage=='save':
                self.status.setText(tr('正在儲存天象歷史，即將完成。'))
            else:
                self.status.setText(tr('正在建立時間軸，即將完成。'))
        else:
            self.progress_bar.setRange(0,max(1,total))
            self.progress_bar.setValue(done)
            if stage=='sample':
                self.status.setText(tr('第 1 階段：掃描時間區間 · 已完成 {done:,} / {total:,} 個掃描點',done=done,total=total))
            elif stage=='refine':
                self.status.setText(tr('第 2 階段：細查事件時間 · 已完成 {done:,} / {total:,} 項',done=done,total=total))
            elif stage=='zodiac':
                self.status.setText(tr('正在建立星座歷程 · 已完成 {done} / {total} 顆天體',done=done,total=total))
            else:
                self.status.setText(tr('第 3 階段：建立事件區間 · 已完成 {done:,} / {total:,} 項',done=done,total=total))
        self.update_elapsed()

    def update_elapsed(self):
        elapsed = time.monotonic()-self.started
        text = tr('已用時間：{time}',time=duration(elapsed))
        p = self.last_progress
        if p and p['stage'] in ('sample','refine','assemble','zodiac') and p['done']>0 and p.get('stage_elapsed',0)>10:
            remaining = p['stage_elapsed']*(p['total']-p['done'])/p['done']
            text += ' · '+tr('本階段預估尚需 {time}（隨實際速度更新）',time=duration(remaining))
        elif not p or p['done']==0:
            text += ' · '+tr('正在取得運算速度，稍後提供估計。')
        self.timing.setText(text)

    def cancel(self):
        if self.worker:
            self.worker.stop.set()
            self.cancel_button.setEnabled(False)
            self.status.setText(tr('正在停止計算並釋放資源，請稍候。'))
            self.progress_bar.setRange(0,0)

    def on_cancelled(self):
        self.progress_bar.hide()
        self.status.setText(tr('計算已取消。可調整條件後重新開始。'))

    def on_failed(self,message):
        self.progress_bar.hide()
        self.status.setText(tr('計算未完成：{reason}',reason=message))

    def worker_finished(self):
        worker = self.worker
        self.worker = None
        self.activity_changed.emit()
        worker.deleteLater()
        self.settings.setEnabled(True)
        self.run_button.setEnabled(True)
        self.history_button.setEnabled(self.history_path is not None)
        self.cancel_button.hide()
        self.heartbeat.stop()
        if self.closing:
            self.closing=False
            QTimer.singleShot(0,self.window().close)

    def apply_result(self,result):
        if self.worker and self.worker.stop.is_set():
            self.on_cancelled()
            return
        self.result = result
        self.canvas.set_result(result)
        self.filter_changed()
        self.enable_results(True)
        self.zoom_changed()
        self.range_label.setText(local_time(result.start,result.request.zone)+' — '+local_time(result.end,result.request.zone)+' · '+result.request.zone)
        self.progress_bar.hide()
        self.status.setText(tr('計算完成 · {n:,} 個掃描點 · {events:,} 段事件',n=result.samples,events=len(result.events)))
        self.timing.setText(tr('總用時：{time}',time=duration(result.elapsed)))
        if result.notes:
            self.timing.setText(self.timing.text()+'\n'+' '.join(tr(n) for n in result.notes))
        self.show_event(None)

    def filter_changed(self,*args):
        self.canvas.body = self.body_filter.currentData()
        self.canvas.angle = self.aspect_filter.currentData()
        self.canvas.rebuild()

    def zoom_changed(self,*args):
        if not self.result:
            return
        days = self.zoom.currentData()
        if days is None:
            self.canvas.start,self.canvas.end = self.result.start,max(self.result.start+60,self.result.end)
        else:
            width = min(days*86400,max(60,self.result.end-self.result.start))
            anchor = self.canvas.selection.start if self.canvas.selection else self.canvas.start
            self.canvas.start = max(self.result.start,min(anchor-width*.2,self.result.end-width))
            self.canvas.end = self.canvas.start+width
        self.canvas.update()
        self.update_axis()

    def shift(self,direction):
        if not self.result:
            return
        width = self.canvas.end-self.canvas.start
        self.canvas.start = max(self.result.start,min(self.canvas.start+direction*width,self.result.end-width))
        self.canvas.end = self.canvas.start+width
        self.canvas.update()
        self.update_axis()

    def update_axis(self):
        self.axis.update()
        if self.result:
            self.previous_button.setEnabled(self.canvas.start>self.result.start)
            self.next_button.setEnabled(self.canvas.end<self.result.end)

    def show_event(self,event):
        self.detail_button.setEnabled(event is not None and self.result is not None)
        if event is None or self.result is None:
            if self.detail_dialog:self.detail_dialog.hide()
            return
        self.canvas.selection=event
        if self.detail_dialog is None:self.detail_dialog=EventDetailDialog(self)
        self.detail_dialog.set_event(self.result,event)
        self.show_detail_dialog()

    def show_detail_dialog(self):
        if self.detail_dialog and self.canvas.selection is not None:
            self.detail_dialog.show();self.detail_dialog.raise_()

    def export(self):
        if self.result is None:return
        from .dialogs import ExportDialog
        from .storage import default_database_path
        from .timeline_report import export_timeline_html
        dialog=ExportDialog(self,timeline=True,has_selection=self.canvas.selection is not None)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        directory=default_database_path().parent
        try:directory.mkdir(parents=True,exist_ok=True)
        except OSError as exc:
            QMessageBox.warning(self,tr('無法匯出'),str(exc));return
        name='sky-timeline-'+self.result.request.start[:10]+'.html'
        path,_=QFileDialog.getSaveFileName(self,tr('匯出文件'),str(directory/name),'HTML (*.html)')
        if path:
            if not path.lower().endswith('.html'):path+='.html'
            try:
                export_timeline_html(self.result,path,dialog.templates.currentData(),
                    self.canvas.selection if dialog.scope.currentData()=='selected' else None)
                self.status.setText(tr('已匯出文件：')+path)
            except Exception as exc:QMessageBox.warning(self,tr('無法匯出'),error_text(exc))

    def focus_selection(self):
        e = self.canvas.selection
        if e is None:
            return
        self.zoom.blockSignals(True)
        self.zoom.setCurrentIndex(1)
        self.zoom.blockSignals(False)
        width = max(86400,(e.end-e.start)*1.3)
        width = min(width,max(60,self.result.end-self.result.start))
        self.canvas.start = max(self.result.start,min(e.start-width*.1,self.result.end-width))
        self.canvas.end = self.canvas.start+width
        self.canvas.update()
        self.update_axis()

    def request_close(self):
        self.close_player()
        if self.worker is not None:
            self.closing = True
            self.cancel()
            return False
        return True

    def close_player(self):
        if self.player:
            self.player.close();self.player.deleteLater();self.player=None

    def show_player(self):
        if self.result is None or not self.history_path or not getattr(self.result,'history_id',None):return
        self.close_player()
        try:
            from .sky_player import SkyPlayer
            self.player=SkyPlayer(self.history_path,self.result,self)
            self.player.show()
        except Exception as exc:QMessageBox.warning(self,tr('無法播放'),error_text(exc))

    def load_history(self,run_id):
        from .sky_history import SkyHistory
        result=SkyHistory(self.history_path).load(run_id)
        self.close_player();self.initializing=True
        try:
            for value,date,clock,fold in ((result.request.start,self.start_date,self.start_time,self.start_fold),
                                         (result.request.end,self.end_date,self.end_time,self.end_fold)):
                wall=datetime.fromisoformat(value)
                date.setDate(QDate(wall.year,wall.month,wall.day));clock.setTime(QTime(wall.hour,wall.minute))
            self.zone.setCurrentText(result.request.zone)
            self.start_fold.setCurrentIndex(self.start_fold.findData(result.request.start_fold))
            self.end_fold.setCurrentIndex(self.end_fold.findData(result.request.end_fold))
        finally:self.initializing=False
        self.conditions_changed();self.apply_result(result)
        self.status.setText(tr('已載入天象歷史，可直接播放或匯出，無須重新計算。'))
        self.timing.setText(tr('歷史紀錄使用當時計算的容許度；不會覆寫全域設定。')+' '+
                            ' · '.join(f'{a}° ±{o:g}°' for a,o in zip(ANGLES,result.request.orbs)))

    def open_history(self):
        from .sky_history import SkyHistory
        try:rows=SkyHistory(self.history_path).list_complete()
        except Exception as exc:QMessageBox.warning(self,tr('無法讀取天象歷史'),error_text(exc));return
        dialog=QDialog(self);dialog.setWindowTitle(tr('天象歷史'));dialog.resize(750,430)
        layout=QVBoxLayout(dialog)
        note=QLabel(tr('選擇已完成的紀錄，直接查看時間軸與播放。未完成的計算不會列入。'))
        note.setWordWrap(True);layout.addWidget(note)
        listing=QListWidget();layout.addWidget(listing)
        for run_id,created,raw,count in rows:
            request=json.loads(raw)
            item=QListWidgetItem(f"{request['start'].replace('T',' ')} — {request['end'].replace('T',' ')} · {request['zone']}\n"+
                tr('{n:,} 個採樣點',n=count)+' · '+created[:19].replace('T',' ')+' UTC')
            item.setData(Qt.ItemDataRole.UserRole,run_id);listing.addItem(item)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Open|QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Open).setText(tr('載入'))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr('取消'))
        buttons.button(QDialogButtonBox.StandardButton.Open).setEnabled(bool(rows))
        layout.addWidget(buttons);buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject)
        listing.itemDoubleClicked.connect(lambda _:dialog.accept())
        if rows:listing.setCurrentRow(0)
        else:layout.addWidget(QLabel(tr('尚無已完成的天象歷史。')))
        if dialog.exec()==QDialog.DialogCode.Accepted and listing.currentItem():
            try:self.load_history(listing.currentItem().data(Qt.ItemDataRole.UserRole))
            except Exception as exc:QMessageBox.warning(self,tr('無法讀取天象歷史'),error_text(exc))
