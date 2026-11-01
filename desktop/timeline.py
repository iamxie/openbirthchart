# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Coarse-scan geocentric sky events, independent of profiles and houses.

Workers use the same pinned TT conversion and planetary calls as ChartEngine.
Only bounded ten-minute sample chunks cross process boundaries; the coordinator retains
events, not hundreds of thousands of complete charts. All event edges and exact
aspects are refined in those isolated workers, never on Qt's GUI thread.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from itertools import combinations
import ctypes
import math
import multiprocessing as mp
import os
import sys
import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import numpy as np

from .errors import UserError, AmbiguousTimeError
from .model import BirthInput, resolve_local
from .settings import default_orbs

BODY_NAMES = ('太陽', '月亮', '水星', '金星', '火星', '木星', '土星', '天王星', '海王星', '冥王星')
RETRO_IDS = tuple(range(2, 10))
ANGLES = (0, 90, 120, 180)
DEFAULT_ORBS = tuple(default_orbs()[angle] for angle in ANGLES)
PAIRS = tuple(combinations(RETRO_IDS, 2))
UTC = timezone.utc


@dataclass(frozen=True)
class TimelineInput:
    start: str
    end: str
    zone: str = 'Asia/Taipei'
    orbs: tuple[float, ...] = DEFAULT_ORBS
    start_fold: int | None = None
    end_fold: int | None = None

    def resolve(self):
        try:
            ZoneInfo(self.zone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise UserError('請選擇有效的時區。') from exc
        if len(self.orbs) != 4 or any(isinstance(v, bool) or not isinstance(v, (int, float))
                or not math.isfinite(v) or not 0 <= v <= 15 for v in self.orbs):
            raise UserError('相位容許度需在 0～15 度內。')
        resolved = []
        for iso, fold in ((self.start, self.start_fold), (self.end, self.end_fold)):
            try:
                wall = datetime.fromisoformat(iso)
            except (ValueError, TypeError) as exc:
                raise UserError('請輸入完整的開始與結束日期時間。') from exc
            if wall.tzinfo is not None or wall.second or wall.microsecond:
                raise UserError('請輸入當地時間到分鐘，時區另外選擇。')
            try:
                resolved.append(resolve_local(BirthInput(local_iso=iso, zone=self.zone, fold=fold))['utc'])
            except AmbiguousTimeError:
                raise
            except UserError as exc:
                if '不存在' in exc.source:
                    raise UserError('這個當地時間因夏令時間切換而不存在，請調整時間。') from exc
                raise
        start, end = resolved
        if end < start:
            raise UserError('結束時間不可早於開始時間。')
        if not datetime(1850, 1, 2, tzinfo=UTC) <= start <= end < datetime(2149, 12, 31, tzinfo=UTC):
            raise UserError('本版可計算 UTC 1850/01/02～2149/12/30；邊界預留給光行時與速度計算。')
        seconds = int((end-start).total_seconds())
        if seconds % 60:
            raise UserError('此區間的歷史時差含秒數變更，無法對齊逐分鐘取樣，請分段查詢。')
        return start, end, seconds // 60 + 1


@dataclass
class SkyEvent:
    kind: str
    a: int
    b: int | None
    angle: int | None
    start: float
    end: float
    clipped_start: bool = False
    clipped_end: bool = False
    exact: list[float] = field(default_factory=list)

    @property
    def key(self):
        return self.kind, self.a, self.b, self.angle


@dataclass
class ZodiacSegment:
    body: int
    start: float
    end: float
    sign: int


@dataclass
class TimelineResult:
    request: TimelineInput
    start: float
    end: float
    samples: int
    events: list[SkyEvent]
    elapsed: float
    notes: list[str]
    worker_pids: list[int] = field(default_factory=list)
    zodiac_segments: list[ZodiacSegment] = field(default_factory=list)


class Cancelled(Exception):
    pass


def logical_processor_count():
    """Match Task Manager's logical processor count, including Windows groups."""
    if sys.platform=='win32':
        try:
            api=ctypes.WinDLL('kernel32',use_last_error=True).GetActiveProcessorCount
            api.argtypes=[ctypes.c_ushort];api.restype=ctypes.c_ulong
            count=api(0xffff)  # ALL_PROCESSOR_GROUPS
            if count:return int(count)
        except (OSError,AttributeError):pass
    return os.cpu_count() or 1


def worker_count(cores=None):
    return max(1,(logical_processor_count() if cores is None else cores)-4)


_ENGINE = None
_INIT_ERROR = None


def _initialize_worker():
    global _ENGINE, _INIT_ERROR
    try:
        from guard import RuntimeGuard
        RuntimeGuard().install()
        from .model import ChartEngine
        _ENGINE = ChartEngine()
        _ENGINE.e.set_calc_mode('skyfield')
    except Exception as exc:
        # A Pool initializer that raises is repeatedly respawned. Return errors
        # through normal tasks instead, so failures are bounded and visible.
        _INIT_ERROR = str(exc)


def _positions(stamp, bodies=tuple(range(10))):
    if _INIT_ERROR:
        raise RuntimeError(_INIT_ERROR)
    dt = datetime.fromtimestamp(stamp, UTC)
    t, notes = _ENGINE.times(dt.replace(microsecond=0))
    tt = t['tt_jd'] + dt.microsecond / 86400000000.
    result = []
    for ident in bodies:
        values, flags = _ENGINE.e.calc(tt, ident, _ENGINE.e.FLG_SWIEPH | _ENGINE.e.FLG_SPEED)
        if not all(math.isfinite(v) for v in values):
            raise ValueError('Non-finite planetary position')
        result.append((float(values[0]), float(values[3])))
    # Houses/rotation are not used here. Retain applicable clock assumptions,
    # but do not report unused UT1 predictions as a planetary limitation.
    notes = [n for n in notes if not n.startswith('此日期的地球自轉時間')]
    return np.asarray(result), notes


def _sample_chunk(job):
    start, end, offset, count, step = job
    result = np.zeros((count, 10, 2), dtype=np.float64)
    notes = set()
    for i in range(count):
        positions, found = _positions(min(end,start + (offset + i) * step), RETRO_IDS)
        result[i,list(RETRO_IDS)] = positions
        notes.update(found)
    return offset, result, sorted(notes), os.getpid()


def delta(a, b):
    return (a-b+180.) % 360. - 180.


def _bisect(fn, left, right, fleft=None, fright=None):
    fleft = fn(left) if fleft is None else fleft
    fright = fn(right) if fright is None else fright
    if fleft == 0:
        return left
    if fright == 0:
        return right
    if fleft * fright > 0:
        raise ValueError('Unbracketed event boundary')
    for _ in range(32):
        middle = (left+right)/2
        fm = fn(middle)
        if fm == 0:
            return middle
        if right-left <= .125:
            return middle
        if fleft * fm <= 0:
            right = middle
        else:
            left, fleft = middle, fm
    return (left+right)/2


def _refine(job, positions=None):
    """Refine a directed-angle crossing; split at a relative-speed extremum."""
    positions = positions or _positions
    kind, a, b, target, orb, left, right = job
    cache = {}

    def get(t):
        if t not in cache:
            cache[t] = positions(t, (a,) if b is None else (a,b))[0]
        return cache[t]

    def phase(t):
        p = get(t)
        return delta(p[0,0] if b is None else p[1, 0]-p[0, 0], target)

    def speed(t):
        p = get(t)
        return p[0, 1] if b is None else p[1, 1]-p[0, 1]

    if kind == 'retro':
        return [_bisect(speed, left, right)]
    if kind == 'edge':
        return [_bisect(lambda t: abs(delta(get(t)[1,0],get(t)[0,0]))-target-orb,
                        left, right)]
    if kind == 'orb':
        return [_bisect(lambda t: abs(abs(delta(get(t)[1,0],get(t)[0,0]))-target)-orb,
                        left, right)]
    cuts = [left, right]
    vl, vr = speed(left), speed(right)
    if vl*vr < 0:
        cuts.insert(1, _bisect(speed, left, right, vl, vr))
    roots = []
    for lo, hi in zip(cuts, cuts[1:]):
        fl, fh = phase(lo), phase(hi)
        if abs(fl-fh) >= 180:
            continue  # the opposite side of the circular coordinate
        if fl*fh <= 0:
            roots.append(_bisect(phase, lo, hi, fl, fh))
        # A tangent exact aspect has no sign crossing. Distinguish it from a
        # near miss using the actual extremum, not rounded displayed degrees.
        elif hi != right and abs(fh) <= 1e-8:
            roots.append(hi)
    return roots


def _unique_times(values):
    result=[]
    for value in sorted(values):
        if not result or value-result[-1]>.125:result.append(value)
    return result


def _refine_bundle(jobs):
    # All thresholds for one pair / interval reuse positions and speed roots.
    cache={}
    def positions(stamp,bodies):
        key=(stamp,bodies)
        if key not in cache:cache[key]=_positions(stamp,bodies)
        return cache[key]
    answer={'edge':[],'exact':[]}
    for job,kind in jobs:
        answer[kind].extend(_refine(job,positions))
    return {kind:_unique_times(values) for kind,values in answer.items()}


def _inside(key,p,orb):
    kind,a,b,angle=key
    if kind=='retro':return bool(p[0,1]<0)
    return bool(abs(abs(delta(p[1,0],p[0,0]))-angle)<=orb)


def _assemble_events(job):
    key,start,end,orb,edges,exacts,initial,final=job
    kind,a,b,angle=key
    edges=_unique_times([max(start,min(end,t)) for t in edges])
    exacts=_unique_times([max(start,min(end,t)) for t in exacts])
    events=[]
    cuts=_unique_times([start,*edges,end])
    for left,right in zip(cuts,cuts[1:]):
        if kind=='aspect' and orb==0:
            active=False
        elif not edges:
            active=initial
        else:
            p,_=_positions((left+right)/2,(a,) if b is None else (a,b))
            active=_inside(key,p,orb)
        if active:
            if events and abs(events[-1].end-left)<=.125:events[-1].end=right
            else:events.append(SkyEvent(*key,left,right))
    # Boundary tangencies and exact-only zero-orb events are genuine instants.
    points=list(exacts)
    if kind=='aspect':points+=edges
    if initial:points.append(start)
    if final:points.append(end)
    for stamp in _unique_times(points):
        event=next((e for e in events if e.start-.125<=stamp<=e.end+.125),None)
        if event is None:
            event=SkyEvent(*key,stamp,stamp);events.append(event)
    for e in events:
        e.clipped_start=initial and abs(e.start-start)<=.125
        e.clipped_end=final and abs(e.end-end)<=.125
        e.exact=[t for t in exacts if e.start-.125<=t<=e.end+.125]
    return sorted(events,key=lambda e:e.start)


def _assemble_sign_segments(job):
    body,start,end,edges = job
    cuts = [start,*_unique_times(t for t in edges if start<t<end),end] if end>start else [start]
    intervals = list(zip(cuts,cuts[1:])) or [(start,end)]
    segments = []
    for left,right in intervals:
        p,_ = _positions((left+right)/2,(body,))
        sign = int(p[0,0]%360//30)
        if segments and segments[-1].sign == sign:
            segments[-1].end = right
        else:
            segments.append(ZodiacSegment(body,left,right,sign))
    return segments


class EventCollector:
    """Collect boundary candidates, including an entire orb visit between samples.

    Directed-angle thresholds avoid the absolute-angle cusp at conjunction and
    opposition. Every observed relative-speed reversal is inspected, even when
    both endpoint states agree. Brackets remain continuous across worker chunks.
    """
    def __init__(self,start,end,orbs):
        self.start,self.end,self.orbs=start,end,orbs
        self.previous=None;self.first=None;self.jobs=[];self.roots={}

    def consume(self,stamp,p):
        if self.first is None:self.first=p.copy()
        if self.previous is not None:
            pt,pp=self.previous
            for a in RETRO_IDS:
                jobs=[]
                turn=pp[a,1]*p[a,1]<0
                for target in range(0,360,30):
                    fl,fr=delta(pp[a,0],target),delta(p[a,0],target)
                    if turn or (fl*fr<=0 and abs(fl-fr)<180):
                        jobs.append((('ingress',a,None,target,0.,pt,stamp),'edge'))
                if jobs:self.jobs.append((jobs,('sign',a,None,None)))
            for a in RETRO_IDS:
                if pp[a,1]*p[a,1]<=0 and pp[a,1]!=p[a,1]:
                    self.jobs.append(([ (('retro',a,None,None,0.,pt,stamp),'edge') ],('retro',a,None,None)))
            for a,b in PAIRS:
                before=(pp[b,0]-pp[a,0])%360;after=(p[b,0]-p[a,0])%360
                turn=(pp[b,1]-pp[a,1])*(p[b,1]-p[a,1])<0
                for angle,orb in zip(ANGLES,self.orbs):
                    targets={}
                    for center in ((angle,) if angle in (0,180) else (angle,360-angle)):
                        targets.setdefault(center%360,set()).add('exact')
                        if orb:
                            for target in (center-orb,center+orb):targets.setdefault(target%360,set()).add('edge')
                    jobs=[]
                    for target,kinds in targets.items():
                        fl,fr=delta(before,target),delta(after,target)
                        if turn or (fl*fr<=0 and abs(fl-fr)<180):
                            for kind in kinds:jobs.append((('exact',a,b,target,0.,pt,stamp),kind))
                    if jobs:self.jobs.append((jobs,('aspect',a,b,angle)))
        self.previous=stamp,p.copy()

    def finish(self):
        pass

    def apply_refinements(self,answers):
        for (_,key),answer in zip(self.jobs,answers):
            roots=self.roots.setdefault(key,{'edge':[],'exact':[]})
            for kind in roots:roots[kind].extend(answer[kind])

    def assembly_jobs(self):
        last=self.previous[1]
        keys=[('retro',a,None,None) for a in RETRO_IDS]+[('aspect',a,b,angle) for a,b in PAIRS for angle in ANGLES]
        for key in keys:
            kind,a,b,angle=key;ids=[a] if b is None else [a,b]
            orb=0 if kind=='retro' else self.orbs[ANGLES.index(angle)]
            initial=_inside(key,self.first[ids],orb);final=_inside(key,last[ids],orb)
            roots=self.roots.get(key,{'edge':[],'exact':[]})
            if self.start==self.end and kind=='aspect' and abs(abs(delta(self.first[b,0],self.first[a,0]))-angle)<=1e-10:
                roots['exact'].append(self.start)
            if initial or final or roots['edge'] or roots['exact']:
                yield key,self.start,self.end,orb,roots['edge'],roots['exact'],initial,final

    def zodiac_jobs(self):
        for body in RETRO_IDS:
            yield body,self.start,self.end,self.roots.get(('sign',body,None,None),{}).get('edge',[])


def calculate_timeline(request, progress=None, cancelled=None, workers=None, chunk_size=60, sample_step=600):
    """Spawn workers; bounded scheduling, heartbeat, and prompt process cleanup.

    Progress payloads contain actual counts and elapsed time. An ETA for sampling
    is separate from later refinement; it is not advertised as whole-job ETA.
    """
    start, end, minutes = request.resolve()
    if sample_step not in (60,600):raise ValueError('Supported scan steps: 60 or 600 seconds')
    total=math.ceil((end-start).total_seconds()/sample_step)+1
    started = time.monotonic()
    progress = progress or (lambda payload: None)
    cancelled = cancelled or (lambda: False)
    stage_clock = [None, started]

    def report(stage, done, count):
        if cancelled():
            raise Cancelled()
        now = time.monotonic()
        if stage_clock[0] != stage:
            stage_clock[:] = stage,now
        progress(dict(stage=stage,done=done,total=count,elapsed=now-started,stage_elapsed=now-stage_clock[1]))

    report('prepare',0,total)
    chunks = math.ceil(total/chunk_size)
    count = min(chunks, worker_count() if workers is None else max(1,workers))
    # Avoid hidden nested BLAS pools multiplying CPU use inside each process.
    env_names = ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS')
    previous_env = {key:os.environ.get(key) for key in env_names}
    for key in env_names:
        os.environ[key] = '1'
    pool = None
    try:
        pool = mp.get_context('spawn').Pool(count, initializer=_initialize_worker)
    finally:
        for key,value in previous_env.items():
            if value is None:
                os.environ.pop(key,None)
            else:
                os.environ[key] = value
    collector = EventCollector(start.timestamp(),end.timestamp(),request.orbs)
    notes = set()
    worker_pids = set()
    original_processes = tuple(pool._pool)

    def run_jobs(jobs, fn, stage, job_total, unit=lambda result:1):
        pending = deque()
        iterator = iter(jobs)
        done = 0
        exhausted = False
        while pending or not exhausted:
            while not exhausted and len(pending)<count*2:
                try:
                    job = next(iterator)
                except StopIteration:
                    exhausted=True
                    break
                pending.append(pool.apply_async(fn,(job,)))
            if not pending:
                break
            report(stage,done,job_total)
            try:
                value = pending[0].get(timeout=.25)
            except mp.TimeoutError:
                if any(process.exitcode is not None for process in original_processes):
                    raise UserError('背景計算意外停止，請重新開始。')
                continue
            pending.popleft()
            done += unit(value)
            yield value
            report(stage,done,job_total)

    try:
        jobs = ((start.timestamp(),end.timestamp(),offset,min(chunk_size,total-offset),sample_step) for offset in range(0,total,chunk_size))
        for offset, data, found_notes, pid in run_jobs(jobs,_sample_chunk,'sample',total,lambda r:len(r[1])):
            worker_pids.add(pid)
            notes.update(found_notes)
            for i,positions in enumerate(data):
                if i % 20 == 0 and cancelled():
                    raise Cancelled()
                collector.consume(min(end.timestamp(),start.timestamp()+(offset+i)*sample_step),positions)
        report('merge',0,1)
        collector.finish()
        answers = list(run_jobs((jobs for jobs,key in collector.jobs),_refine_bundle,'refine',len(collector.jobs)))
        collector.apply_refinements(answers)
        assembly=list(collector.assembly_jobs())
        events=[]
        for group in run_jobs(assembly,_assemble_events,'assemble',len(assembly)):events.extend(group)
        zodiac=[]
        for group in run_jobs(collector.zodiac_jobs(),_assemble_sign_segments,'zodiac',len(RETRO_IDS)):zodiac.extend(group)
        events.sort(key=lambda e:(e.kind!='retro',e.a,e.b or -1,e.angle or 0,e.start))
        report('finish',1,1)
        pool.close()
        pool.join()
        return TimelineResult(request,start.timestamp(),end.timestamp(),total,events,
                              time.monotonic()-started,sorted(notes),sorted(worker_pids),zodiac)
    except BaseException:
        pool.terminate()
        pool.join()
        raise


def result_dict(result):
    return asdict(result)
