# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Minute-sampled geocentric sky events, independent of profiles and houses.

Workers use the same pinned TT conversion and planetary calls as ChartEngine.
Only bounded sample chunks cross process boundaries; the coordinator retains
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

BODY_NAMES = ('太陽', '月亮', '水星', '金星', '火星', '木星', '土星', '天王星', '海王星', '冥王星')
RETRO_IDS = tuple(range(2, 10))
ANGLES = (0, 90, 120, 180)
DEFAULT_ORBS = (4., 3., 3., 3.)
PAIRS = tuple(combinations(range(10), 2))
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
class TimelineResult:
    request: TimelineInput
    start: float
    end: float
    samples: int
    events: list[SkyEvent]
    elapsed: float
    notes: list[str]
    worker_pids: list[int] = field(default_factory=list)


class Cancelled(Exception):
    pass


def physical_core_count():
    """Count physical cores across processor groups; conservative fallback of 1."""
    if sys.platform == 'win32':
        try:
            api = ctypes.WinDLL('kernel32', use_last_error=True).GetLogicalProcessorInformationEx
            api.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
            api.restype = ctypes.c_int
            size = ctypes.c_ulong()
            api(0, None, ctypes.byref(size))  # RelationProcessorCore
            if not size.value:
                return 1
            buffer = ctypes.create_string_buffer(size.value)
            if not api(0, buffer, ctypes.byref(size)):
                return 1
            offset = count = 0
            while offset + 8 <= size.value:
                relationship = ctypes.c_uint32.from_buffer(buffer, offset).value
                length = ctypes.c_uint32.from_buffer(buffer, offset + 4).value
                if length < 8 or offset + length > size.value:
                    return 1
                count += relationship == 0
                offset += length
            return max(1, count)
        except (OSError, ValueError, AttributeError):
            return 1
    try:
        from pathlib import Path
        pairs = set()
        for block in Path('/proc/cpuinfo').read_text().split('\n\n'):
            values = dict(line.split(':', 1) for line in block.splitlines() if ':' in line)
            values = {k.strip(): v.strip() for k, v in values.items()}
            if 'physical id' in values and 'core id' in values:
                pairs.add((values['physical id'], values['core id']))
        return max(1, len(pairs))
    except OSError:
        return 1


def worker_count(cores=None):
    return max(1, (physical_core_count() if cores is None else cores) - 4)


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
    start, offset, count = job
    result = np.empty((count, 10, 2), dtype=np.float64)
    notes = set()
    for i in range(count):
        result[i], found = _positions(start + (offset + i) * 60)
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


def _refine(job):
    """One edge or one minute containing crossings / a relative-speed reversal."""
    kind, a, b, target, orb, left, right = job
    cache = {}

    def get(t):
        if t not in cache:
            cache[t] = _positions(t, (a,) if b is None else (a,b))[0]
        return cache[t]

    def phase(t):
        p = get(t)
        return delta(p[1, 0]-p[0, 0], target)

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


class EventCollector:
    """Sequential minute states, with the preceding sample retained across chunks."""
    def __init__(self, start, end, orbs):
        self.start, self.end, self.orbs = start, end, orbs
        self.previous = None
        self.active = {}
        self.events = []
        self.jobs = []  # (refinement job, event or pair key, attribute)

    def consume(self, stamp, positions):
        states = {}
        for a in RETRO_IDS:
            if positions[a,1] < 0:
                states[('retro', a, None, None)] = True
        for a,b in PAIRS:
            separation = abs(delta(positions[b,0], positions[a,0]))
            for angle, orb in zip(ANGLES, self.orbs):
                if abs(separation-angle) <= orb:
                    states[('aspect', a, b, angle)] = True
        for key in set(self.active) - states.keys():
            e = self.active.pop(key)
            e.end = stamp
            self.jobs.append((self.edge_job(key, stamp), e, 'end'))
        for key in states.keys() - self.active.keys():
            kind,a,b,angle = key
            e = SkyEvent(kind,a,b,angle,stamp,stamp,clipped_start=self.previous is None)
            self.active[key] = e
            self.events.append(e)
            if self.previous is not None:
                self.jobs.append((self.edge_job(key, stamp), e, 'start'))
        if self.previous is not None:
            pt, pp = self.previous
            for a,b in PAIRS:
                before = (pp[b,0]-pp[a,0]) % 360
                after = (positions[b,0]-positions[a,0]) % 360
                relative_speed_turn = (pp[b,1]-pp[a,1])*(positions[b,1]-positions[a,1]) < 0
                for angle in ANGLES:
                    targets = (angle,) if angle in (0,180) else (angle,360-angle)
                    for target in targets:
                        f0, f1 = delta(before,target), delta(after,target)
                        crossing = f0*f1 <= 0 and abs(f0-f1) < 180
                        near_turn = relative_speed_turn and min(abs(f0),abs(f1)) < .05
                        if crossing or near_turn:
                            job = ('exact',a,b,target,0.,pt,stamp)
                            self.jobs.append((job, ('aspect',a,b,angle), 'exact'))
        self.previous = stamp, positions.copy()

    def edge_job(self, key, stamp):
        kind,a,b,angle = key
        return ('retro' if kind=='retro' else 'orb', a,b,angle,
                0. if kind=='retro' else self.orbs[ANGLES.index(angle)],self.previous[0],stamp)

    def finish(self):
        for e in self.active.values():
            e.end = self.end
            e.clipped_end = True
        # For a one-sample request there are no brackets. A root is reported
        # only if its unrounded value really is exact at that instant.
        if self.previous and self.start == self.end:
            p = self.previous[1]
            for e in self.events:
                if e.kind=='aspect' and abs(abs(delta(p[e.b,0],p[e.a,0]))-e.angle) <= 1e-10:
                    e.exact.append(self.start)

    def apply_refinements(self, answers):
        exacts = []
        for (_, target, attr), values in zip(self.jobs, answers):
            if attr == 'exact':
                exacts.extend((target, value) for value in values)
            else:
                setattr(target, attr, values[0])
        grouped = {}
        for e in self.events:
            grouped.setdefault(e.key, []).append(e)
        for key, stamp in sorted(exacts, key=lambda x:x[1]):
            candidates = grouped.get(key, [])
            event = next((e for e in candidates if e.start-.25 <= stamp <= e.end+.25), None)
            if event is None:
                # Zero or sub-minute orbs still get their genuine exact marker.
                _,a,b,angle = key
                event = SkyEvent('aspect',a,b,angle,stamp,stamp)
                self.events.append(event)
                grouped.setdefault(key, []).append(event)
            if not event.exact or abs(event.exact[-1]-stamp) > .25:
                event.exact.append(stamp)
        self.events.sort(key=lambda e:(e.kind!='retro',e.a,e.b or -1,e.angle or 0,e.start))


def calculate_timeline(request, progress=None, cancelled=None, workers=None, chunk_size=120):
    """Spawn workers; bounded scheduling, heartbeat, and prompt process cleanup.

    Progress payloads contain actual counts and elapsed time. An ETA for sampling
    is separate from later refinement; it is not advertised as whole-job ETA.
    """
    start, end, total = request.resolve()
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
        jobs = ((start.timestamp(),offset,min(chunk_size,total-offset)) for offset in range(0,total,chunk_size))
        for offset, data, found_notes, pid in run_jobs(jobs,_sample_chunk,'sample',total,lambda r:len(r[1])):
            worker_pids.add(pid)
            notes.update(found_notes)
            for i,positions in enumerate(data):
                if i % 20 == 0 and cancelled():
                    raise Cancelled()
                collector.consume(start.timestamp()+(offset+i)*60,positions)
        report('merge',0,1)
        collector.finish()
        answers = list(run_jobs((job for job,_,_ in collector.jobs),_refine,'refine',len(collector.jobs)))
        collector.apply_refinements(answers)
        report('finish',1,1)
        pool.close()
        pool.join()
        return TimelineResult(request,start.timestamp(),end.timestamp(),total,collector.events,
                              time.monotonic()-started,sorted(notes),sorted(worker_pids))
    except BaseException:
        pool.terminate()
        pool.join()
        raise


def result_dict(result):
    return asdict(result)
