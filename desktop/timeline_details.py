# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Shared, timezone-independent event/sign and overlap semantics."""
from datetime import datetime
from zoneinfo import ZoneInfo


def local_time(stamp, zone, seconds=True):
    return datetime.fromtimestamp(stamp,ZoneInfo(zone)).strftime(
        '%Y/%m/%d %H:%M:%S %z' if seconds else '%Y/%m/%d %H:%M %z')


def sign_at(result, body, stamp):
    segments=[s for s in result.zodiac_segments if s.body==body]
    # Ingress boundaries belong to the new interval; query end is included.
    for s in reversed(segments):
        if s.start<=stamp<=s.end:return s.sign
    return None


def event_spans(result,event):
    """Combined sign history, retaining re-entry and both bodies of an aspect."""
    bodies=(event.a,) if event.b is None else (event.a,event.b)
    cuts=sorted({event.start,event.end,*[s.start for s in result.zodiac_segments
        if s.body in bodies and event.start<s.start<event.end]})
    intervals=list(zip(cuts,cuts[1:])) or [(event.start,event.end)]
    answer=[]
    for left,right in intervals:
        signs=tuple(sign_at(result,b,(left+right)/2) for b in bodies)
        if answer and answer[-1][2]==signs:answer[-1]=(answer[-1][0],right,signs)
        else:answer.append((left,right,signs))
    return answer


def sign_path(result,event,body):
    index=0 if body==event.a else 1
    path=[]
    for _,_,signs in event_spans(result,event):
        if not path or path[-1]!=signs[index]:path.append(signs[index])
    return path


def overlapping_events(result,event,stamp=None):
    """All calculated events, independent of display filters; closed event edges.

    A shared endpoint is returned as a zero-duration simultaneous instant.
    Zodiac intervals, unlike event membership, are half-open at ingress.
    """
    left,right=(event.start,event.end) if stamp is None else (stamp,stamp)
    found=[]
    for index,other in enumerate(result.events):
        if other is event:continue
        lo,hi=max(left,other.start),min(right,other.end)
        if lo<=hi:found.append((index,other,lo,hi))
    return sorted(found,key=lambda row:(row[2],row[3],row[0]))
