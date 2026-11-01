# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Astronomicon zodiac outlines shared by desktop and offline exports.

The unmodified upstream font is separately licensed under SIL OFL 1.1;
see data/desktop/astronomicon/OFL-License.txt.
"""
from functools import lru_cache
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QRawFont, QTransform, QIcon, QPixmap, QPainter
from common import ROOT

# Upstream character mapping, Aries to Pisces. J is the Capricorn variant
# shown in the approved design preview (the upstream European form).
ZODIAC_CHARACTERS='ABCDEFGHIJKL'


def zodiac_index(longitude):
    """Use the same rounded arcsecond boundary as the displayed degree text."""
    return (round((longitude % 360) * 3600) % (360 * 3600)) // 108000


@lru_cache(maxsize=12)
def zodiac_icon(index):
    image=QPixmap(64,64);image.fill(Qt.GlobalColor.transparent)
    painter=QPainter(image);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    try:draw_zodiac(painter,index,QPointF(32,32),50,'#47382e')
    finally:painter.end()
    image.setDevicePixelRatio(2)
    return QIcon(image)


@lru_cache(maxsize=1)
def zodiac_paths():
    font=QRawFont(str(ROOT/'data/desktop/astronomicon/Astronomicon.ttf'),100,
                  QFont.HintingPreference.PreferNoHinting)
    if not font.isValid():
        raise RuntimeError('Unable to load bundled Astronomicon font')
    paths=[]
    for character in ZODIAC_CHARACTERS:
        indices=font.glyphIndexesForString(character)
        if len(indices)!=1 or not indices[0]:
            raise RuntimeError('Missing Astronomicon zodiac glyph: '+character)
        path=font.pathForGlyph(indices[0]);bounds=path.boundingRect()
        if bounds.isEmpty():raise RuntimeError('Empty Astronomicon zodiac glyph: '+character)
        scale=1/max(bounds.width(),bounds.height())
        transform=QTransform()
        transform.scale(scale,scale)
        transform.translate(-bounds.center().x(),-bounds.center().y())
        paths.append(transform.map(path))
    return tuple(paths)


def draw_zodiac(painter,index,center,size,color):
    """Draw an upright, centered outline; no viewer font installation needed."""
    painter.save()
    try:
        painter.translate(QPointF(center));painter.scale(size,size)
        painter.fillPath(zodiac_paths()[index],QColor(color))
    finally:
        painter.restore()
