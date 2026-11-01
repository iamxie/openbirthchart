# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Retained graphics items driven exclusively by persisted ten-minute frames."""
import math
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from PySide6.QtCore import Qt, QPointF, QRectF, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QFont
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QGraphicsView, QGraphicsScene, QGraphicsItem, QGraphicsSimpleTextItem,
    QStyle, QMessageBox)

from .chart import spaced_labels, font_family
from .i18n import tr, short_name, error_text
from .model import BODIES
from .sky_history import FrameReader
from .timeline import PAIRS, ANGLES, delta
from .timeline_palette import COLORS
from .timeline_report import color_legend, labels_for
from .i18n import language
from .report import TEMPLATES
from .theme import SURFACE, TEXT, BORDER, SOFT
from .zodiac import draw_zodiac


def point(longitude, radius):
    angle=math.radians(180+longitude)
    return QPointF(500+radius*math.cos(angle),500-radius*math.sin(angle))


def active_aspects(positions, orbs):
    for a,b in PAIRS:
        separation=abs(delta(positions[b,0],positions[a,0]))
        for angle,orb in zip(ANGLES,orbs):
            if abs(separation-angle)<=orb:yield a,b,angle


class ZodiacRing(QGraphicsItem):
    def __init__(self):
        super().__init__()
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)

    def boundingRect(self):return QRectF(10,10,980,980)

    def paint(self,p,option,widget=None):
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        fills=['#fbd9d7','#ecf5cc','#d8ebfa','#dff1d9']
        colors=['#d64643','#708331','#266b9a','#438344']
        for i in range(12):
            path=QPainterPath();path.moveTo(point(i*30,470))
            path.arcTo(QRectF(30,30,940,940),180+i*30,30)
            path.lineTo(point((i+1)*30,405))
            path.arcTo(QRectF(95,95,810,810),210+i*30,-30);path.closeSubpath()
            p.setPen(QPen(QColor(BORDER),1));p.setBrush(QColor(fills[i%4]));p.drawPath(path)
            draw_zodiac(p,i,point(i*30+15,438),38,colors[i%4])
        for degree in range(360):
            p.setPen(QPen(QColor('#a9b4ae'),.8))
            p.drawLine(point(degree,405),point(degree,397 if degree%5==0 else 402))


class SkyView(QGraphicsView):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self));self.setSceneRect(0,0,1000,1000)
        self.setBackgroundBrush(QColor(SURFACE));self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scene().addItem(ZodiacRing())
        self.lines={}
        for a,b in PAIRS:
            line=self.scene().addLine(0,0,0,0);line.setZValue(1);line.hide();self.lines[a,b]=line
        self.icons=[];self.retro=[];self.anchors=[];self.leaders=[]
        font=QFont(font_family());font.setPixelSize(24)
        small=QFont(font_family());small.setPixelSize(14)
        for ident,name,short,color in BODIES[:10]:
            leader=self.scene().addLine(0,0,0,0,QPen(QColor(color),1));leader.setZValue(2)
            anchor=self.scene().addEllipse(-2.5,-2.5,5,5,QPen(QColor(color)),QColor(color));anchor.setZValue(3)
            item=QGraphicsSimpleTextItem(short_name({'short':short}));item.setFont(font)
            item.setBrush(QColor(color));item.setZValue(4)
            item.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
            self.scene().addItem(item)
            retro=QGraphicsSimpleTextItem('R',item);retro.setFont(small);retro.setBrush(QColor(color))
            retro.setPos(item.boundingRect().width()+2,8);retro.hide()
            self.icons.append(item);self.retro.append(retro);self.anchors.append(anchor);self.leaders.append(leader)
        self.visible_aspects=[]
        self.last_positions=None
        self.label_gap=11

    def resizeEvent(self,event):
        super().resizeEvent(event);self.fitInView(self.sceneRect(),Qt.AspectRatioMode.KeepAspectRatio)
        scale=max(.1,self.transform().m11())
        size=max(24,round(12/scale));self.label_gap=max(11,math.degrees((size*1.7+12)/350))
        for item,retro in zip(self.icons,self.retro):
            font=item.font();font.setPixelSize(size);item.setFont(font)
            font=retro.font();font.setPixelSize(max(14,round(9/scale)));retro.setFont(font)
            retro.setPos(item.boundingRect().width()+2,8)
        if self.last_positions is not None:self.show_frame(self.last_positions,self.last_orbs)

    def show_frame(self,positions,orbs):
        self.last_positions=positions;self.last_orbs=orbs
        labels=spaced_labels([{'lon':p[0]} for p in positions],minimum_gap=self.label_gap)
        for i,(longitude,speed) in enumerate(positions):
            anchor=point(longitude,280);label=point(labels[i],350)
            self.anchors[i].setPos(anchor)
            bounds=self.icons[i].boundingRect()
            self.icons[i].setPos(label.x()-bounds.width()/2,label.y()-bounds.height()/2)
            self.leaders[i].setLine(anchor.x(),anchor.y(),label.x(),label.y())
            self.retro[i].setVisible(bool(i>=2 and speed<0))
            self.icons[i].setToolTip(f'{tr(BODIES[i][1])} · {longitude%360:.4f}°')
        self.visible_aspects=list(active_aspects(positions,orbs))
        for line in self.lines.values():line.hide()
        for a,b,angle in self.visible_aspects:
            left=point(positions[a,0],280);right=point(positions[b,0],280)
            line=self.lines[a,b];line.setLine(left.x(),left.y(),right.x(),right.y())
            line.setPen(QPen(QColor(COLORS[angle]),1.5));line.show()


class SkyPlayer(QDialog):
    def __init__(self,path,result,parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr('看實際星盤'));self.resize(960,850);self.setMinimumSize(600,540)
        self.result=result
        self.index=0;self.rate=0;self.closed=False;self.painted_frames=0
        layout=QVBoxLayout(self)
        self.timestamp=QLabel();self.timestamp.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.timestamp.setObjectName('chartTitle');layout.addWidget(self.timestamp)
        self.view=SkyView();layout.addWidget(self.view,1)
        self.slider=QSlider(Qt.Orientation.Horizontal);self.slider.setRange(0,result.samples-1)
        self.slider.setAccessibleName(tr('播放時間'));layout.addWidget(self.slider)
        controls=QHBoxLayout();controls.addStretch();self.buttons=[]
        specs=[(QStyle.StandardPixmap.SP_MediaSkipBackward,tr('跳到開始'),lambda:self.seek(0)),
               (QStyle.StandardPixmap.SP_MediaSeekBackward,tr('倒播 · 30 fps'),lambda:self.play(-30)),
               (QStyle.StandardPixmap.SP_MediaStop,tr('停止，停留在目前時刻'),self.pause),
               (QStyle.StandardPixmap.SP_MediaPlay,tr('播放／暫停 · 15 fps'),self.toggle),
               (QStyle.StandardPixmap.SP_MediaSeekForward,tr('快轉 · 30 fps'),lambda:self.play(30)),
               (QStyle.StandardPixmap.SP_MediaSkipForward,tr('跳到結束'),lambda:self.seek(self.reader.count-1))]
        for icon,label,callback in specs:
            button=QPushButton();button.setIcon(self.style().standardIcon(icon));button.setFixedSize(48,36)
            button.setToolTip(label);button.setAccessibleName(label);button.clicked.connect(callback)
            controls.addWidget(button);self.buttons.append(button)
        controls.addStretch();layout.addLayout(controls)
        self.status=QLabel();self.status.setAlignment(Qt.AlignmentFlag.AlignCenter);layout.addWidget(self.status)
        legend=QLabel(color_legend(labels_for(TEMPLATES/language())));legend.setWordWrap(True);legend.setObjectName('hint');layout.addWidget(legend)
        note=QLabel(tr('每幀為已儲存的十分鐘採樣點；日月只顯示位置，不參與相位。無宮位，牡羊座 0° 固定在左側。'))
        note.setWordWrap(True);note.setObjectName('hint');layout.addWidget(note)
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.timeout.connect(self.tick);self.slider.valueChanged.connect(self.seek)
        self.reader=FrameReader(path,result.history_id)
        try:self.show_frame(0)
        except BaseException:
            self.reader.close();self.closed=True
            raise

    def show_frame(self,index):
        stamp,positions=self.reader.frame(index);self.index=index
        self.view.show_frame(positions,self.result.request.orbs);self.painted_frames+=1
        self.timestamp.setText(datetime.fromtimestamp(stamp,ZoneInfo(self.result.request.zone)).strftime('%Y/%m/%d %H:%M %z')+' · '+self.result.request.zone)
        self.slider.blockSignals(True);self.slider.setValue(index);self.slider.blockSignals(False)
        self.update_status()

    def update_status(self):
        state=tr('已停止') if not self.rate else (tr('倒播') if self.rate<0 else tr('播放中'))
        self.status.setText(tr('{state} · {current:,} / {total:,} 幀',state=state,current=self.index+1,total=self.reader.count))
        self.buttons[3].setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause if self.rate else QStyle.StandardPixmap.SP_MediaPlay))

    def seek(self,index):
        self.pause()
        try:self.show_frame(index)
        except Exception as exc:self.fail(exc)

    def play(self,rate):
        if self.closed:return
        if (rate>0 and self.index==self.reader.count-1) or (rate<0 and self.index==0):
            self.pause();return
        self.rate=rate;self.due=time.monotonic()+1/abs(rate);self.update_status();self.schedule()

    def toggle(self):
        if self.rate:self.pause()
        else:self.play(15)

    def pause(self):
        self.timer.stop();self.rate=0;self.update_status()

    def schedule(self):
        self.timer.start(max(1,round((self.due-time.monotonic())*1000)))

    def tick(self):
        if not self.rate:return
        target=self.index+(1 if self.rate>0 else -1)
        if not 0<=target<self.reader.count:self.pause();return
        try:self.show_frame(target)
        except Exception as exc:self.fail(exc);return
        if target in (0,self.reader.count-1):self.pause();return
        # Preserve every sample; late frames slow playback instead of skipping data.
        period=1/abs(self.rate);self.due=max(self.due+period,time.monotonic());self.schedule()

    def fail(self,exc):
        self.pause();QMessageBox.warning(self,tr('無法播放'),error_text(exc));self.close()

    def done(self,result):
        self.pause()
        if not self.closed:self.reader.close();self.closed=True
        super().done(result)

    def closeEvent(self,event):
        self.done(QDialog.DialogCode.Rejected);event.accept()
