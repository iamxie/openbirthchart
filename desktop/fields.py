# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Explicitly empty inputs: blank never means midnight or zero degrees."""
from .i18n import tr
import math
import re
from datetime import datetime
from PySide6.QtCore import QDate, QTime
from PySide6.QtWidgets import QLineEdit
from .text import trim_text


class DateField(QLineEdit):
    def __init__(self,birth=True):
        super().__init__();self.birth=birth;self.setPlaceholderText('YYYY/MM/DD');self.setMaxLength(24)
    def date(self):
        value=trim_text(self.text()).replace('/','-')
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):raise ValueError(tr('請完整填寫出生日期（YYYY/MM/DD）。') if self.birth else tr('請完整填寫日期（YYYY/MM/DD）。'))
        try:day=datetime.strptime(value,'%Y-%m-%d').date()
        except ValueError:raise ValueError(tr('出生日期無效，請檢查年月日。') if self.birth else tr('日期無效，請檢查年月日。')) from None
        if not 1850<=day.year<=2149:raise ValueError(tr('出生日期需在 1850～2149 年內。') if self.birth else tr('日期需在 1850～2149 年內。'))
        return QDate(day.year,day.month,day.day)
    def setDate(self,value):self.setText(value.toString('yyyy/MM/dd'))


class TimeField(QLineEdit):
    def __init__(self,seconds=True):
        super().__init__();self.seconds=seconds;self.setPlaceholderText('HH:mm:ss' if seconds else 'HH:mm');self.setMaxLength(24)
    def iso_text(self):
        """Keep :60 intact for contextual validation before constructing QTime."""
        value=trim_text(self.text())
        if not self.seconds:
            if not re.fullmatch(r'\d{2}:\d{2}',value) or not QTime.fromString(value,'HH:mm').isValid():
                raise ValueError(tr('請完整填寫有效的時間（HH:mm）。'))
            return value+':00'
        if not re.fullmatch(r'\d{2}:\d{2}:\d{2}',value):raise ValueError(tr('請完整填寫出生時間（HH:mm:ss）；不確定秒數請填 00。'))
        h,m,s=map(int,value.split(':'))
        if not (0<=h<24 and 0<=m<60 and 0<=s<=60):raise ValueError(tr('出生時間無效，請檢查時、分、秒。'))
        return value
    def time(self):
        value=self.iso_text()
        t=QTime.fromString(value,'HH:mm:ss')
        if not t.isValid():raise ValueError(tr('出生時間無效，請檢查時、分、秒。'))
        return t
    def setTime(self,value):self.setText(value.toString('HH:mm:ss' if self.seconds else 'HH:mm'))


class CoordinateField(QLineEdit):
    def __init__(self,maximum,label):
        super().__init__();self.maximum=maximum;self.label=label
        self.setPlaceholderText(tr('十進位度'));self.setMaxLength(32)
    def value(self):
        value=trim_text(self.text())
        if not re.fullmatch(r'\d+(?:\.\d{1,5})?',value):
            raise ValueError(tr('請填寫{p0}的正數或 0，最多五位小數；方向另外選擇。', p0=self.label))
        number=float(value)
        if not math.isfinite(number) or not 0<=number<=self.maximum:raise ValueError(tr('{p0}超出範圍（0～{p1}）。', p0=self.label, p1=self.maximum))
        return number
    def setValue(self,value):self.setText(f'{value:.5f}')
