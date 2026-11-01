# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Recognize a pinned positive UTC leap second, but never return chart time.

The preceding ordinary second is only an offset-lookup anchor. The original
input is neither replaced nor returned as a normalized timestamp.
"""
from datetime import datetime, timedelta, timezone
from functools import lru_cache
import re
from common import ROOT, read, sha
from .errors import UserError

_LEAP = re.compile(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:(?P<second>60)(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2}(?::?\d{2})?)?')


@lru_cache(maxsize=1)
def leap_anchors():
    """UTC 23:59:59 preceding each confirmed +1 insertion, from shipped data."""
    relative='data/time/Leap_Second.dat'
    record=next(item for item in read(ROOT/'time-data-sources.lock.json')['files'] if item['path']==relative)
    if sha(ROOT/relative)!=record['sha256']:
        raise UserError('閏秒資料損壞，請重新安裝程式。')
    anchors=set();previous=None
    for line in (ROOT/relative).read_text(encoding='ascii').splitlines():
        if not line.strip() or line.lstrip().startswith('#'):continue
        _,day,month,year,offset=map(float,line.split())
        effective=datetime(int(year),int(month),int(day),tzinfo=timezone.utc)
        if previous is not None and offset-previous==1:
            anchors.add(effective-timedelta(seconds=1))
        previous=offset
    return frozenset(anchors)


def reject_leap_second(birth, resolve_wall):
    """Return only for ordinary input; all :60 candidates remain rejected.

    resolve_wall applies the same zone, fold and manual-DST policy as ordinary
    chart input. Ambiguities and nonexistent civil times retain their own errors.
    """
    match=_LEAP.fullmatch(birth.local_iso)
    if match is None:return
    start,end=match.span('second')
    anchor=datetime.fromisoformat(birth.local_iso[:start]+'59'+birth.local_iso[end:])
    resolved=resolve_wall(birth,anchor)
    utc=resolved['utc'].replace(microsecond=0)
    if utc in leap_anchors():
        raise UserError('此時間包含閏秒（秒數為 60）。本程式目前不支援閏秒輸入，因此無法排盤。原輸入時間未變更。')
    raise UserError('秒數 60 無法依指定時區及內附閏秒表確認為合法閏秒，請核對日期、時間與時區。原輸入時間未變更。')
