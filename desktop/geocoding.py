# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Opt-in address lookup. Address stays transient; owner persists the user's key."""
from .i18n import tr
import json
import math
import time
from PySide6.QtCore import QUrl,QUrlQuery,QTimer,Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtNetwork import QNetworkAccessManager,QNetworkRequest,QNetworkReply
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QPushButton,
    QListWidget,QDialogButtonBox,QAbstractItemView)
from .text import trim_text
from .model import APP_VERSION
from .theme import dialog_layout, primary


def search_request(address,key):
    address,key=trim_text(address),trim_text(key)
    if not address or not key:raise ValueError(tr('請先填寫 API key 與出生地址。'))
    if any(ord(c)<33 or ord(c)>126 for c in key):raise ValueError(tr('API key 格式不正確。'))
    url=QUrl('https://geocode.maps.co/search');query=QUrlQuery()
    # Provider's documented header method returned 401 for a valid key while
    # api_key returned 200. Never log this URL or expose reply.errorString().
    for name,value in [('q',address),('format','json'),('limit','5'),('api_key',key)]:query.addQueryItem(name,value)
    url.setQuery(query);request=QNetworkRequest(url)
    request.setRawHeader(b'User-Agent',('OpenBirthChart/'+APP_VERSION).encode('ascii'))
    request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,QNetworkRequest.RedirectPolicy.ManualRedirectPolicy)
    request.setTransferTimeout(15000)
    return request


def parse_results(raw):
    try:
        data=json.loads(raw)
        if not isinstance(data,list):raise ValueError()
        results=[]
        for row in data[:5]:
            lat,lon=float(row['lat']),float(row['lon'])
            if not (math.isfinite(lat) and math.isfinite(lon) and -89.99999<=lat<=89.99999 and -180<=lon<=180):raise ValueError()
            results.append(dict(latitude=round(lat,5),longitude=round(lon,5),label=trim_text(row['display_name'])[:700]))
        return results
    except (ValueError,TypeError,KeyError):raise ValueError(tr('服務回傳的座標格式無效，請稍後再試或手動填寫。')) from None


def maps_url(lat,lon):
    url=QUrl('https://www.google.com/maps/search/');q=QUrlQuery()
    q.addQueryItem('api','1');q.addQueryItem('query',f'{lat:.5f},{lon:.5f}');url.setQuery(q);return url


class GeocodeDialog(QDialog):
    def __init__(self,parent=None,key='',manager=None):
        super().__init__(parent);self.setWindowTitle(tr('由出生地址查詢經緯度'));self.resize(620,560)
        self.manager=manager or QNetworkAccessManager(self);self.reply=None;self.results=[];self.coordinates=None
        self.last_request=0;self.timed_out=False
        layout=QVBoxLayout(self);dialog_layout(layout)
        def label(text):
            w=QLabel(text);w.setWordWrap(True);layout.addWidget(w);return w
        label(tr('查詢時會將地址傳送給 geocode.maps.co。地址不會寫入個人檔案或操作紀錄；只帶回你選擇的經緯度。'))
        label(tr('你的 geocode.maps.co API key（關閉此視窗後存入本機資料庫；清空後關閉即可移除）'))
        self.key=QLineEdit(key);self.key.setEchoMode(QLineEdit.EchoMode.Password);layout.addWidget(self.key)
        label(tr('出生地址或醫院名稱（可加上國家、城市）'))
        self.address=QLineEdit();self.address.setPlaceholderText(tr('輸入地址後按查詢'));layout.addWidget(self.address)
        self.search=QPushButton(tr('查詢座標'));layout.addWidget(self.search)
        self.list=QListWidget();self.list.setWordWrap(True);self.list.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection);layout.addWidget(self.list,1)
        self.info=label(tr('請從查詢結果選擇地點，並開啟地圖確認位置。'))
        self.map=QPushButton(tr('在 Google Maps 確認位置'));self.map.setEnabled(False);layout.addWidget(self.map)
        label(tr('資料來源：© OpenStreetMap contributors · Nominatim / geocode.maps.co'))
        buttons=QDialogButtonBox();self.adopt=buttons.addButton(tr('使用這組座標'),QDialogButtonBox.ButtonRole.AcceptRole)
        primary(self.adopt)
        self.adopt.setEnabled(False);buttons.addButton(tr('取消'),QDialogButtonBox.ButtonRole.RejectRole);layout.addWidget(buttons)
        buttons.accepted.connect(self.use_selected);buttons.rejected.connect(self.reject)
        self.search.clicked.connect(self.lookup);self.address.returnPressed.connect(self.lookup)
        self.address.textChanged.connect(self.invalidate);self.list.currentRowChanged.connect(self.select)
        self.map.clicked.connect(self.open_map)
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.timeout.connect(self.timeout)

    def invalidate(self):
        self.list.clear();self.results=[];self.adopt.setEnabled(False);self.map.setEnabled(False)

    def lookup(self):
        if self.reply is not None:return
        if time.monotonic()-self.last_request<1.1:
            self.info.setText(tr('請稍候一秒再查詢。'));return
        try:request=search_request(self.address.text(),self.key.text())
        except ValueError as exc:self.info.setText(str(exc));return
        self.key.setText(trim_text(self.key.text()));self.address.setText(trim_text(self.address.text()))
        self.invalidate();self.search.setEnabled(False);self.address.setEnabled(False);self.key.setEnabled(False)
        self.last_request=time.monotonic();self.timed_out=False;self.info.setText(tr('正在查詢…'))
        self.reply=self.manager.get(request);self.reply.finished.connect(self.completed);self.timer.start(15000)

    def timeout(self):
        if self.reply is not None:self.timed_out=True;self.reply.abort()

    def completed(self):
        reply=self.reply
        if reply is None:return
        self.timer.stop();self.reply=None;self.search.setEnabled(True);self.address.setEnabled(True);self.key.setEnabled(True)
        status=reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        try:
            if self.timed_out:raise ValueError(tr('查詢逾時；仍可取消後手動填寫經緯度。'))
            if status==429:raise ValueError(tr('查詢次數或額度已達限制，請稍後再試。'))
            if status in (401,403):raise ValueError(tr('API key 無效、已過期或目前無法使用，請確認你的 key。'))
            if status!=200 or reply.error()!=QNetworkReply.NetworkError.NoError:
                raise ValueError(tr('目前無法連線至查詢服務；請稍後再試，或手動填寫經緯度。'))
            if reply.bytesAvailable()>1000000:raise ValueError(tr('服務回應過大，已停止處理。'))
            self.results=parse_results(bytes(reply.readAll()))
            for row in self.results:
                self.list.addItem(tr('{p0}\n緯度 {p1:.5f}\u3000經度 {p2:.5f}', p0=row['label'], p1=row['latitude'], p2=row['longitude']))
            self.info.setText(tr('請選擇地點，開啟地圖核對；採用後請自行確認出生地區時區。') if self.results else tr('沒有找到結果，請補上城市／國家，或改為手動填寫。'))
        except ValueError as exc:self.info.setText(str(exc))
        finally:reply.deleteLater()

    def select(self,index):
        valid=0<=index<len(self.results);self.adopt.setEnabled(valid);self.map.setEnabled(valid)
    def open_map(self):
        row=self.results[self.list.currentRow()]
        if not QDesktopServices.openUrl(maps_url(row['latitude'],row['longitude'])):
            self.info.setText(tr('無法開啟預設瀏覽器，請手動在地圖核對顯示的座標。'))
    def use_selected(self):
        index=self.list.currentRow()
        if 0<=index<len(self.results):
            row=self.results[index];self.coordinates=(row['longitude'],row['latitude']);self.accept()
    def done(self,result):
        self.timer.stop()
        if self.reply is not None:
            reply=self.reply;self.reply=None;reply.finished.disconnect(self.completed);reply.abort();reply.deleteLater()
        super().done(result)
