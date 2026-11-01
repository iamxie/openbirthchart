# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Startup-only Qt translations. Never translate canonical chart/profile data."""
from PySide6.QtCore import QCoreApplication, QTranslator, QLibraryInfo
from common import ROOT

LANGUAGES={'zh-TW':'繁體中文','en-US':'English'}
_language='zh-TW'
_translators=[]


def install_language(app, language):
    """Called before creating windows. Keep translators alive for the application."""
    global _language
    for translator in _translators:app.removeTranslator(translator)
    _translators.clear()
    _language=language if language in LANGUAGES else 'zh-TW'
    if _language=='zh-TW':
        qt=QTranslator(app)
        if qt.load('qtbase_zh_TW',QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
            app.installTranslator(qt);_translators.append(qt)
    else:
        translator=QTranslator(app)
        if not translator.load(str(ROOT/'translations/desktop_en_US.qm')):
            raise RuntimeError('Unable to load the English interface translation. Please reinstall Open BirthChart.')
        app.installTranslator(translator);_translators.append(translator)
    return _language


def language():return _language


def tr(source, **values):
    result=QCoreApplication.translate('OpenBirthChart',source)
    return result.format(**values) if values else result


def error_text(error):
    from .errors import UserError
    if isinstance(error,UserError):return tr(error.source,**error.values)
    return str(error)


def short_name(point):
    # Context separates short labels such as 日 from unrelated UI text.
    return QCoreApplication.translate('BodyShort',point['short'])


def localized_wheel(chart):
    if chart is None:return None
    return dict(chart,points=[dict(p,short=short_name(p)) for p in chart['points']])


def localized_zodiac(lon):
    from .model import SIGNS
    total=int(round((lon%360)*3600))%(360*3600)
    sign,inside=divmod(total,30*3600);degrees,rest=divmod(inside,3600);minutes,seconds=divmod(rest,60)
    return f'{tr(SIGNS[sign])} {degrees:02}°{minutes:02}′{seconds:02}″'
