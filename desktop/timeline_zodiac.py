# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Shared zodiac artwork: vector HTML exports and Qt rich-text images."""
import base64
import re
from functools import lru_cache
from PySide6.QtCore import QBuffer,QByteArray,QIODevice,QPointF,Qt
from PySide6.QtGui import QImage,QPainter
from .report import svg_image
from .zodiac import draw_zodiac


@lru_cache(maxsize=24)
def sign_svg(index,color='#47382e'):
    icon=svg_image(24,24,lambda p:draw_zodiac(p,index,QPointF(12,12),20,color))
    icon=re.sub(r'<(?:title|desc)>.*?</(?:title|desc)>','',icon,flags=re.S)
    icon=re.sub(r'>\s+<','><',icon).strip()
    return icon.replace('<svg','<svg class="zodiac-icon" aria-hidden="true" focusable="false"',1)


@lru_cache(maxsize=12)
def qt_sign_image(index):
    # QTextBrowser does not render inline SVG markup. A cached high-resolution
    # image of the identical outline keeps rich-text names and icons together.
    image=QImage(48,48,QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter=QPainter(image);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    try:draw_zodiac(painter,index,QPointF(24,24),40,'#47382e')
    finally:painter.end()
    data=QByteArray();buffer=QBuffer(data);buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer,'PNG'):raise RuntimeError('Unable to render zodiac icon')
    buffer.close()
    return 'data:image/png;base64,'+base64.b64encode(bytes(data)).decode('ascii')


def sign_icon(index,mode='svg'):
    if mode=='qt':return f'<img src="{qt_sign_image(index)}" width="16" height="16" alt="" />'
    return sign_svg(index)
