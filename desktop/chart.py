# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Vector wheel inspired by the supplied layout; all positions are calculated."""
from .i18n import tr, localized_wheel, language
import math
from pathlib import Path
from PySide6.QtCore import Qt, QPointF, QRectF, QSize, QTimer
from PySide6.QtGui import QColor, QFont, QFontDatabase, QFontMetricsF, QImage, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtSvg import QSvgGenerator
from PySide6.QtWidgets import QWidget,QScrollArea,QGridLayout,QVBoxLayout,QLabel,QSizePolicy
from .model import SIGNS, HOUSE_SYSTEMS, ASPECTS, house_midpoints, house_direction
from .theme import SURFACE, TEXT, MUTED
from .zodiac import draw_zodiac
from .wheel_geometry import house_view, wheel_points
from .house_positions import validate_chart_houses

def font_family():
    families=set(QFontDatabase.families())
    return next((f for f in ['Microsoft JhengHei','PingFang TC','Heiti TC','LiHei Pro','Noto Sans TC','Noto Sans CJK TC'] if f in families),'sans-serif')

def spaced_labels(points,minimum_gap=5.2):
    """Spread labels only, across the largest empty gap; anchors stay astronomical."""
    values=sorted(enumerate(points),key=lambda item:item[1]['lon'])
    if len(values)<2:return {i:p['lon'] for i,p in values}
    gaps=[(values[(i+1)%len(values)][1]['lon']-v[1]['lon'])%360 for i,v in enumerate(values)]
    start=(max(range(len(gaps)),key=gaps.__getitem__)+1)%len(values)
    values=values[start:]+values[:start];original=[]
    for _,p in values:
        lon=p['lon']
        if original:
            while lon<original[-1]:lon+=360
        original.append(lon)
    placed=[]
    for lon in original:placed.append(max(lon,placed[-1]+minimum_gap) if placed else lon)
    shift=sum(a-b for a,b in zip(placed,original))/len(placed)
    return {i:(v-shift)%360 for (i,_),v in zip(values,placed)}

def house_label_longitudes(cusps,minimum_gap=7.):
    """Move crowded reverse-ring labels only; retain the real sector anchors."""
    mids=house_midpoints(cusps)
    if house_direction(cusps)==1:return mids
    labels=spaced_labels([{'lon':m} for m in mids],minimum_gap)
    return [labels[i] for i in range(12)]

def coordinate_text(value,latitude=False):
    # Round before splitting so 59.999 seconds carries correctly to the next minute.
    hundredths=int(round(abs(value)*3600*100))
    degrees,remainder=divmod(hundredths,360000)
    minutes,seconds=divmod(remainder,6000)
    direction=(tr('北緯') if value>=0 else tr('南緯')) if latitude else (tr('東經') if value>=0 else tr('西經'))
    return f'{direction} {degrees}°{minutes:02}′{seconds/100:05.2f}″（{abs(value):.5f}°）'

def chart_conditions(chart):
    """Use resolved chart data, not the current editable form, for every export."""
    birth=chart['input'];minutes=chart['dst_minutes']
    mode=tr('手動指定') if birth['manual_dst'] else tr('依地區與日期自動判斷')
    dst=tr('已套用（{p0:+g} 分鐘）', p0=minutes) if minutes else tr('未套用（0 分鐘）')
    return [
        tr('出生時間：')+birth['local_iso'].replace('T',' ').replace('-','/'),
        coordinate_text(birth['longitude'])+'   '+coordinate_text(birth['latitude'],True),
        tr('地區時區：{p0}   ｜   實際時差：{p1}（含夏令調整）', p0=birth['zone'], p1=chart['utc_offset']),
        tr('夏令時間：{p0}   ｜   {p1}', p0=dst, p1=mode),
        tr('換算 UTC：')+chart['utc'].removesuffix('+00:00').replace('T',' ').replace('-','/'),
        tr('姓名：{p0}\u3000｜\u3000性別：{p1}', p0=birth.get('name') or tr('未填寫'), p1=tr(birth.get('gender', '男'))),
    ]

def paint_wheel(p,chart,screen_scale=1,background='white',labels=None):
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.fillRect(QRectF(0,0,1000,1000),QColor(background))
    family=font_family()
    def text(x,y,w,h,value,size=18,color='#566169',align=Qt.AlignmentFlag.AlignLeft,fit=False,min_size=11):
        p.setPen(QColor(color));f=QFont(family);f.setPixelSize(max(size,round(11/max(screen_scale,.1))));p.setFont(f)
        if fit:
            while max(QFontMetricsF(f).horizontalAdvance(line) for line in str(value).split('\n'))>w and f.pixelSize()>min_size:
                f.setPixelSize(f.pixelSize()-1)
            p.setFont(f)
        p.drawText(QRectF(x,y,w,h),align|Qt.AlignmentFlag.AlignVCenter,str(value))
    if not chart:
        text(100,430,800,80,tr('填寫出生資料，開始排盤'),30,'#657c77',Qt.AlignmentFlag.AlignCenter);return
    birth=chart['input'];asc=chart['asc'];cx,cy=500,500;outer,inner,anchor=450,375,275
    spatial=house_view(chart)
    def wording(key,source):return labels[key] if labels is not None else tr(source)
    if 'house_latitude' in birth:
        text(90,0,820,30,wording('house_view_title','宮位位置圖 · 納入天體黃緯') if spatial else
             wording('longitude_view_title','黃經輪盤 · 歸宮黃緯設為零'),17,'#365b4c',Qt.AlignmentFlag.AlignCenter)
        footer=(wording('house_view_note','外緣空心點為真實黃經；內圈為宮位位置。相位角度請讀表格。') if spatial else
                wording('longitude_view_note','行星依真實黃經定位；歸宮計算忽略黃緯。'))
        if any(body['house'] is None for body in chart['points']):
            footer+='\n'+wording('undefined_marker','？表示宮位未定義；僅標示外緣黃經位置。')
        text(65,962,870,34,footer,15,'#566169',Qt.AlignmentFlag.AlignCenter,fit=True)
    def pt(lon,r):
        a=math.radians(180+lon-asc)
        return QPointF(cx+r*math.cos(a),cy-r*math.sin(a))
    def circle(r,color='#9aa6a2',width=1):
        p.setBrush(Qt.BrushStyle.NoBrush);p.setPen(QPen(QColor(color),width))
        p.drawEllipse(QPointF(cx,cy),r,r)
    p.save()
    # Reserve dedicated header/footer bands for the mode explanation. Keep
    # the wheel isotropic and its center fixed; axis labels cannot overlap it.
    if 'house_latitude' in birth:p.translate(50,50);p.scale(.9,.9)
    fills=['#fbd9d7','#ecf5cc','#d8ebfa','#dff1d9'];colors=['#d64643','#708331','#266b9a','#438344']
    for i,name in enumerate(SIGNS):
        angle=180+i*30-asc
        path=QPainterPath();path.moveTo(pt(i*30,outer))
        path.arcTo(QRectF(cx-outer,cy-outer,outer*2,outer*2),angle,30)
        path.lineTo(pt((i+1)*30,inner))
        path.arcTo(QRectF(cx-inner,cy-inner,inner*2,inner*2),angle+30,-30);path.closeSubpath()
        p.setPen(QPen(QColor('#a1aaa5'),1));p.setBrush(QColor(fills[i%4]));p.drawPath(path)
        pos=pt(i*30+15,412)
        draw_zodiac(p,i,pos,42,colors[i%4])
    for degree in range(360):
        p.setPen(QPen(QColor('#b3bcb6'),.7 if degree%5 else 1))
        p.drawLine(pt(degree,inner),pt(degree,inner-(8 if degree%5==0 else 3)))
    mids=house_midpoints(chart['cusps'])
    gap=max(7.,math.degrees((max(19,round(11/max(screen_scale,.1)))*1.3+4)/348))
    house_labels=house_label_longitudes(chart['cusps'],gap)
    for lon in chart['cusps']:
        p.setPen(QPen(QColor('#c5ceca'),1));p.drawLine(QPointF(cx,cy),pt(lon,inner))
    for i,(mid,label) in enumerate(zip(mids,house_labels)):
        if abs(math.remainder(label-mid,360))>.01:
            p.setPen(QPen(QColor('#9aa6a2'),.8));p.drawLine(pt(mid,369),pt(label,359))
        pos=pt(label,348)
        text(pos.x()-20,pos.y()-17,40,34,i+1,19,'#747e77',Qt.AlignmentFlag.AlignCenter,fit=house_direction(chart['cusps'])<0)
    points=wheel_points(chart)
    anchors={body['name']:body for body in points}
    # Aspect membership/angles still use actual longitudes. In the house view
    # connecting lines show relationships, not measurable zodiac angles.
    for aspect in sorted(chart['aspects'],key=lambda a:not a['minor']):
        color=QColor(aspect['color']);color.setAlpha(150 if aspect['minor'] else 205)
        pen=QPen(color,1.1 if aspect['minor'] else 1.45)
        if aspect['minor']:pen.setStyle(Qt.PenStyle.DotLine)
        a,b=anchors[aspect['a']],anchors[aspect['b']]
        p.setPen(pen);p.drawLine(pt(a['plot_lon'],a['plot_radius']),pt(b['plot_lon'],b['plot_radius']))
    body_labels=spaced_labels([dict(body,lon=body['plot_lon']) for body in points])
    for i,body in enumerate(points):
        dot=pt(body['plot_lon'],body['plot_radius']);end=pt(body_labels[i],310)
        if spatial and body['house'] is not None:
            p.setPen(QPen(QColor(body['color']),.8,Qt.PenStyle.DotLine))
            p.drawLine(pt(body['lon'],365),dot)
            p.setBrush(Qt.BrushStyle.NoBrush);p.drawEllipse(pt(body['lon'],365),3.,3.)
        p.setPen(QPen(QColor(body['color']),1.1));p.drawLine(dot,pt(body_labels[i],297))
        p.setBrush(QColor(body['color']) if body['house'] is not None else Qt.BrushStyle.NoBrush)
        p.drawEllipse(dot,2.5,2.5)
        # Transparent HTML charts inherit their paper surface without white tiles.
        if QColor(background).alpha():
            p.fillRect(QRectF(end.x()-13,end.y()-14,26,28),QColor(background))
        text(end.x()-15,end.y()-18,30,36,body['short'],23,body['color'],Qt.AlignmentFlag.AlignCenter,fit=True,min_size=16)
        if body['house'] is None:text(end.x()+12,end.y()-17,18,18,'?',13,body['color'])
        if body['retrograde'] and body['id'] not in (11,-11):
            text(end.x()+12,end.y()+5,15,17,'R',11,body['color'])
    for lon,label,r in [(asc,'ASC',477),((asc+180)%360,'DSC',477),(chart['mc'],'MC',477),((chart['mc']+180)%360,'IC',477)]:
        a,b=pt(lon,anchor-10),pt(lon,outer+9)
        p.setPen(QPen(QColor('#7c8983'),1.7));p.drawLine(a,b)
        direction=b-QPointF(cx,cy);length=math.hypot(direction.x(),direction.y())
        unit=QPointF(direction.x()/length,direction.y()/length);normal=QPointF(-unit.y(),unit.x())
        p.setBrush(QColor('#7c8983'));p.drawPolygon(QPolygonF([b,b-unit*10+normal*4,b-unit*10-normal*4]))
        pos=pt(lon,r);text(pos.x()-29,pos.y()-15,58,30,label,15,'#67746d',Qt.AlignmentFlag.AlignCenter)
    circle(outer);circle(inner);circle(anchor,'#e8eeeb',.7)
    p.restore()


def metadata_lines(chart):
    b=chart['input'];c=chart_conditions(chart)
    return [tr('本命星盤'),c[5],c[0],coordinate_text(b['longitude']),coordinate_text(b['latitude'],True),
            tr('地區時區：')+b['zone'],tr('實際時差：')+chart['utc_offset']+tr('（含夏令調整）'),
            tr('夏令時間：')+(tr('已套用') if chart['dst_minutes'] else tr('未套用'))+tr('（{p0:g} 分鐘）', p0=chart['dst_minutes']),
            tr('手動指定') if b['manual_dst'] else tr('依地區與日期自動判斷'),c[4],
            tr(HOUSE_SYSTEMS[b['system']])+tr(' · 熱帶黃道 · 地心視位置'),tr('真交點'),
            tr('幸運點：')+(tr('日生公式') if chart['day_chart'] else tr('夜生公式')),tr('R 表示逆行')]+(
            [tr('歸宮納入天體黃緯')+'：'+(tr('開啟') if b['house_latitude'] else tr('關閉')),
             tr('宮位位置圖；真實星座與度數請讀位置表。') if b['house_latitude'] else tr('黃經輪盤；歸宮使用零黃緯。')]+
            ([tr('？表示宮位未定義；僅標示外緣黃經位置。')] if any(p['house'] is None for p in chart['points']) else [])
            if 'house_latitude' in b else [])


def paint_chart(p,chart):
    """Landscape export: full wheel and a readable, complete right-hand rail."""
    p.fillRect(QRectF(0,0,1400,1000),QColor('white'))
    paint_wheel(p,localized_wheel(chart))
    if not chart:return
    p.setPen(QPen(QColor('#dce5df'),1));p.drawLine(QPointF(1000,25),QPointF(1000,975))
    font=QFont(font_family());font.setPixelSize(18);p.setFont(font);y=35
    from .help import has_azimuth_notice, azimuth_notice_text
    lines=metadata_lines(chart)+([azimuth_notice_text(chart)] if has_azimuth_notice(chart) else [])
    for i,line in enumerate(lines):
        font.setPixelSize(24 if i==0 else 18);p.setFont(font);p.setPen(QColor('#365b4c'))
        rect=QRectF(1025,y,350,220)
        bounds=p.boundingRect(rect,Qt.TextFlag.TextWordWrap,line)
        p.drawText(QRectF(1025,y,350,bounds.height()+4),Qt.TextFlag.TextWordWrap,line)
        y+=bounds.height()+13
    y+=12
    for i,(angle,name,orb,color,minor) in enumerate(a for a in ASPECTS if not a[4] or chart['input']['minor_aspects']):
        x=1025+(i%2)*178;row=y+(i//2)*34;pen=QPen(QColor(color),2)
        if minor:pen.setStyle(Qt.PenStyle.DotLine)
        p.setPen(pen);p.drawLine(QPointF(x,row+10),QPointF(x+25,row+10))
        p.setPen(QColor('#365b4c'));p.drawText(QRectF(x+32,row-3,140,28),Qt.AlignmentFlag.AlignVCenter,f'{angle}° {tr(name)}')

def export_chart(chart,path,format='png',size=2000):
    validate_chart_houses(chart)
    path=Path(path)
    if format=='svg':
        device=QSvgGenerator();device.setFileName(str(path));device.setSize(QSize(1400,1000))
        device.setViewBox(QRectF(0,0,1400,1000));device.setTitle(tr('本命星盤 ')+chart['input']['local_iso'])
        device.setDescription('LibEphemeris · '+' | '.join(chart_conditions(chart)))
    else:
        device=QImage(round(size*1.4),size,QImage.Format.Format_ARGB32);device.fill(QColor('white'))
    painter=QPainter(device)
    if not painter.isActive():raise OSError(tr('無法建立圖片。'))
    if format!='svg':painter.scale(size/1000,size/1000)
    paint_chart(painter,chart);painter.end()
    if format!='svg' and not device.save(str(path),'PNG'):raise OSError(tr('無法儲存圖片。'))
    if not path.exists() or path.stat().st_size==0:raise OSError(tr('圖片沒有成功儲存。'))

class WheelCanvas(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent);self.chart=None;self.setMinimumSize(280,280)
    def set_chart(self,chart):self.chart=localized_wheel(chart);self.update()
    def paintEvent(self,event):
        p=QPainter(self);p.fillRect(self.rect(),QColor(SURFACE))
        side=min(self.width(),self.height());p.translate((self.width()-side)/2,(self.height()-side)/2)
        p.scale(side/1000,side/1000);paint_wheel(p,self.chart,side/1000,background=SURFACE);p.end()


class ChartWidget(QScrollArea):
    def __init__(self,parent=None):
        super().__init__(parent);self.chart=None;self.setWidgetResizable(True);self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.content=QWidget();self.content.setObjectName('chartContent');self.setWidget(self.content)
        self.grid=QGridLayout(self.content);self.grid.setContentsMargins(12,12,12,12);self.grid.setSpacing(12)
        self.canvas=WheelCanvas();self.grid.addWidget(self.canvas,0,0,Qt.AlignmentFlag.AlignTop)
        self.rail=QWidget();self.rail.setFixedWidth(250);self.details=QVBoxLayout(self.rail)
        self.details.setContentsMargins(12,12,4,12);self.details.setSpacing(9)
        self.grid.addWidget(self.rail,0,1);self.grid.setColumnStretch(0,1);self.rail.hide();self.stacked=False
    def set_chart(self,chart):
        self.chart=chart;self.canvas.set_chart(chart)
        while self.details.count():
            item=self.details.takeAt(0)
            if item.widget():item.widget().hide();item.widget().deleteLater()
        self.rail.setVisible(bool(chart))
        if chart:
            for i,line in enumerate(metadata_lines(chart)):
                label=QLabel(line);label.setTextFormat(Qt.TextFormat.PlainText);label.setWordWrap(True)
                label.setSizePolicy(QSizePolicy.Policy.Preferred,QSizePolicy.Policy.Minimum)
                if i==0:label.setObjectName('chartTitle')
                self.details.addWidget(label)
            legends=QWidget();grid=QGridLayout(legends);grid.setContentsMargins(0,8,0,0);grid.setSpacing(6)
            for i,(angle,name,_,color,minor) in enumerate(a for a in ASPECTS if not a[4] or chart['input']['minor_aspects']):
                label=QLabel(f'<span style="color:{color}">{"┄" if minor else "━"}</span> {angle}° {tr(name)}')
                label.setToolTip(tr('容許度 ±{p0:g}°', p0=chart['orbs'][angle]))
                grid.addWidget(label,i if language()=='en-US' else i//2,0 if language()=='en-US' else i%2);label.setWordWrap(True)
                label.setMinimumHeight(label.fontMetrics().height()+8)
                label.setSizePolicy(QSizePolicy.Policy.Preferred,QSizePolicy.Policy.Minimum)
            self.details.addWidget(legends);self.details.addStretch()
        self.reflow()
        QTimer.singleShot(0,self,self.reflow)
    def reflow(self):
        stacked=self.viewport().width()<600
        if stacked!=self.stacked:
            self.stacked=stacked;self.grid.removeWidget(self.rail)
            self.rail.setFixedWidth(250 if not stacked else max(250,self.viewport().width()-32))
            self.grid.addWidget(self.rail,1 if stacked else 0,0 if stacked else 1)
        elif stacked:self.rail.setFixedWidth(max(250,self.viewport().width()-32))
        height=max(280,self.viewport().height()-24)
        self.canvas.setFixedHeight(height)
        self.details.activate()
        rail_height=max(self.details.sizeHint().height(),self.details.totalHeightForWidth(self.rail.width())) if self.chart else 0
        self.rail.setMinimumHeight(rail_height)
        self.content.setMinimumHeight((height+rail_height+40) if stacked and self.chart else max(height+24,rail_height+24))
    def resizeEvent(self,event):super().resizeEvent(event);self.reflow()
