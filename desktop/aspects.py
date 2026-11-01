# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Triangular aspect matrix with font-independent, painted symbols."""
from .i18n import tr, short_name, language
from PySide6.QtCore import Qt, QRectF, QPointF, QTimer
from PySide6.QtGui import QColor, QPen, QPainter, QPolygonF
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QScrollArea,QLabel,QTableWidget,QTableWidgetItem,
    QHeaderView,QAbstractItemView,QStyledItemDelegate,QStyleOptionViewItem,QStyle)
from common import angular_delta
from .model import ASPECTS, ASPECT_IDS
from .theme import SURFACE, TEXT, BORDER, SOFT

SYMBOLS={0:'☌',90:'□',120:'△',180:'☍',60:'✶',30:'⚺',45:'∠',72:'Q',135:'⚼',150:'⚻'}

def draw_symbol(p,rect,angle,color='#202c27'):
    p.save();p.setRenderHint(QPainter.RenderHint.Antialiasing)
    size=min(rect.width(),rect.height());p.translate(rect.center());p.scale(size/30,size/30)
    p.setPen(QPen(QColor(color),1.8));p.setBrush(Qt.BrushStyle.NoBrush)
    def line(x1,y1,x2,y2):p.drawLine(QPointF(x1,y1),QPointF(x2,y2))
    if angle==0:
        p.drawEllipse(QPointF(-4,4),4,4);line(-1,1,8,-8)
    elif angle==180:
        p.drawEllipse(QPointF(-6,6),3.5,3.5);p.drawEllipse(QPointF(6,-6),3.5,3.5);line(-3,3,3,-3)
    elif angle==90:p.drawRect(QRectF(-7,-7,14,14))
    elif angle==120:p.drawPolygon(QPolygonF([QPointF(0,-9),QPointF(-8,7),QPointF(8,7)]))
    elif angle==60:
        line(-9,0,9,0);line(-4.5,-7.8,4.5,7.8);line(-4.5,7.8,4.5,-7.8)
    elif angle in (30,150):
        d=1 if angle==150 else -1
        line(-10,-4*d,10,-4*d);line(0,-4*d,-6,7*d);line(0,-4*d,6,7*d)
    elif angle==45:line(-8,6,8,6);line(-8,6,6,-8)
    elif angle==135:
        p.drawRect(QRectF(-8,-9,13,13));line(-3,-1,-3,9);line(-3,9,8,9)
    elif angle==72:
        p.drawEllipse(QRectF(-7,-8,13,15));line(2,3,9,10)
    p.restore()

class SymbolDelegate(QStyledItemDelegate):
    def paint(self,p,option,index):
        opt=QStyleOptionViewItem(option);self.initStyleOption(opt,index);opt.text=''
        option.widget.style().drawControl(QStyle.ControlElement.CE_ItemViewItem,opt,p,option.widget)
        background=index.data(Qt.ItemDataRole.BackgroundRole)
        if background is not None:p.fillRect(option.rect,background)
        angle=index.data(Qt.ItemDataRole.UserRole)
        if angle is not None:
            margin=min(4,max(0,(option.rect.height()-24)//4))
            draw_symbol(p,QRectF(option.rect).adjusted(margin,margin,-margin,-margin),angle)
        elif index.row()==index.column():
            p.save();p.setPen(QPen(QColor(BORDER),1));p.drawLine(option.rect.topLeft(),option.rect.bottomRight());p.restore()

class AspectLegend(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent);self.setMinimumHeight(350);self.entries=ASPECTS
        self.setToolTip('\n'.join(f'{angle}° {tr(name)}' for angle,name,_,_,_ in ASPECTS))
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        width=self.width()
        for i,(angle,name,orb,color,minor) in enumerate(self.entries):
            x=0;y=i*34+4
            pen=QPen(QColor(color),2)
            if minor:pen.setStyle(Qt.PenStyle.DotLine)
            p.setPen(pen);p.drawLine(QPointF(x+8,y+15),QPointF(x+28,y+15))
            draw_symbol(p,QRectF(x+31,y,28,28),angle)
            p.setPen(QColor(TEXT));p.drawText(QRectF(x+64,y,width-64,30),Qt.AlignmentFlag.AlignVCenter,f'{angle}° {tr(name)}')
        p.end()

class AspectMatrix(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent);layout=QHBoxLayout(self);layout.setContentsMargins(8,8,8,8);layout.setSpacing(12)
        self.table=QTableWidget();self.table.setItemDelegate(SymbolDelegate(self.table))
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setMinimumSectionSize(20)
        self.table.verticalHeader().setMinimumSectionSize(20)
        self.table.horizontalHeader().setFixedHeight(30);self.table.verticalHeader().setFixedWidth(30)
        self.table.setStyleSheet(f'QTableWidget {{gridline-color:{BORDER};}} QTableWidget::item {{padding:0;border:0;}} QHeaderView::section {{padding:2px;font-weight:600;}}')
        if language()=='en-US':
            self.table.setStyleSheet(self.table.styleSheet()+' QHeaderView::section {padding:0;font-size:10pt;font-weight:400;}')
        layout.addWidget(self.table,0,Qt.AlignmentFlag.AlignTop)
        self.rail=QScrollArea();self.rail.setWidgetResizable(True);self.rail.setFrameShape(QScrollArea.Shape.NoFrame)
        self.rail.setStyleSheet(f'QScrollArea, QScrollArea > QWidget > QWidget {{background:{SURFACE};}}')
        self.rail_width=240 if language()=='en-US' else 190
        self.rail.setMinimumWidth(self.rail_width);layout.addWidget(self.rail,1)
        content=QWidget();self.rail.setWidget(content);rail_layout=QVBoxLayout(content);rail_layout.setContentsMargins(2,4,4,4)
        self.detail=QLabel(tr('點選下三角格子，查看兩個天體的相位與角度。'));self.detail.setWordWrap(True)
        self.detail.setMinimumHeight(65);rail_layout.addWidget(self.detail)
        self.legend=AspectLegend();rail_layout.addWidget(self.legend);rail_layout.addStretch()
        self.table.cellClicked.connect(self.selected);self.points=[];self.lookup={}
        self.fit_timer=QTimer(self);self.fit_timer.setSingleShot(True);self.fit_timer.timeout.connect(self.fit_cells)

    def set_chart(self,chart):
        self.points=sorted((p for p in chart['points'] if p['id'] in ASPECT_IDS),key=lambda p:ASPECT_IDS.index(p['id']))
        self.lookup={frozenset((a['a'],a['b'])):a for a in chart['aspects']}
        n=len(self.points);self.table.clear();self.table.setRowCount(n);self.table.setColumnCount(n)
        for i,point in enumerate(self.points):
            for vertical in (False,True):
                item=QTableWidgetItem(short_name(point));item.setToolTip(tr(point['name']))
                if vertical:self.table.setVerticalHeaderItem(i,item)
                else:self.table.setHorizontalHeaderItem(i,item)
            for j in range(n):
                item=QTableWidgetItem();item.setBackground(QColor(SOFT if j>=i else SURFACE))
                if i>j:
                    a=self.lookup.get(frozenset((point['name'],self.points[j]['name'])))
                    if a:
                        item.setText(SYMBOLS[a['angle']]);item.setData(Qt.ItemDataRole.UserRole,a['angle'])
                    item.setToolTip(self.description(i,j))
                self.table.setItem(i,j,item)
        self.detail.setText(tr('點選下三角格子查看詳情；空白表示未符合目前的相位設定。'))
        self.legend.entries=[a for a in ASPECTS if not a[4] or chart['input']['minor_aspects']]
        self.legend.setMinimumHeight(len(self.legend.entries)*34+10);self.legend.update()
        self.fit_cells()
        self.fit_timer.start(0)

    def description(self,row,col):
        a,b=self.points[row],self.points[col];angle=abs(angular_delta(a['lon'],b['lon']))
        prefix=tr('{p0} × {p1}\u3000實際夾角 {p2:.4f}°', p0=tr(a['name']), p1=tr(b['name']), p2=angle)
        aspect=self.lookup.get(frozenset((a['name'],b['name'])))
        if aspect:return prefix+tr('\n{p0} {p1}°\u3000偏離 {p2:.4f}°\u3000容許 ±{p3:g}°', p0=tr(aspect['name']), p1=aspect['angle'], p2=aspect['orb'], p3=aspect['limit'])
        return prefix+tr('\n未符合目前的相位設定。')

    def selected(self,row,col):
        if row>col:self.detail.setText(self.description(row,col))

    def fit_cells(self):
        n=len(self.points)
        if n:
            side=min(self.height()-16,self.width()-self.rail_width-28)
            cell=max(20,min(58,(side-34)//n))
            self.table.horizontalHeader().setDefaultSectionSize(cell)
            self.table.verticalHeader().setDefaultSectionSize(cell)
            full=n*cell+34
            available=max(80,self.height()-16)
            # Keep readable cells when a chart notice leaves too little height.
            # The table must scroll within its panel, never extend behind the status bar.
            scrollbar=self.style().pixelMetric(QStyle.PixelMetric.PM_ScrollBarExtent) if full>available else 0
            self.table.setFixedSize(full+scrollbar,min(full,available))

    def resizeEvent(self,event):super().resizeEvent(event);self.fit_cells()
