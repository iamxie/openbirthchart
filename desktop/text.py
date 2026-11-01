# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Trim invisible boundary characters without rewriting a person's text."""
import unicodedata
from datetime import datetime


def invisible_boundary(char):
    code = ord(char)
    return (char.isspace() or unicodedata.category(char) in {'Cc', 'Cf', 'Zs', 'Zl', 'Zp'}
            or code in (0x034F, 0x115F, 0x1160, 0x17B4, 0x17B5, 0x2800, 0x3164, 0xFFA0)
            or 0xFE00 <= code <= 0xFE0F or 0xE0100 <= code <= 0xE01EF)


def trim_text(value):
    if not isinstance(value, str):
        raise ValueError('文字欄位格式不正確。')
    start, end = 0, len(value)
    while start < end and invisible_boundary(value[start]):
        start += 1
    while end > start and invisible_boundary(value[end - 1]):
        end -= 1
    return value[start:end]


def report_filename(birth):
    """Local birth date, with a portable basename; never rewrite stored identity."""
    name=trim_text(birth.get('name',''))
    name=''.join('_' if c in '<>:"/\\|?*' or unicodedata.category(c)=='Cc' else c for c in name)
    name=name.rstrip(' .') or '未命名'
    date=datetime.fromisoformat(birth['local_iso']).strftime('%Y%m%d')
    filename=f'{name}-{date}.html'
    reserved={'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))}
    if filename.split('.')[0].upper() in reserved:filename='_'+filename
    return filename
