# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Timing harness only; never modifies the application or its profile database.

Run with the desktop interpreter. Fresh-process first requests and a sequence of
different births are measured separately. Raw perf_counter_ns samples are kept.
"""
from time import perf_counter_ns
SCRIPT_START_NS = perf_counter_ns()
import argparse
import csv
import json
import os
from pathlib import Path
import random
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]


def statistics_ms(samples):
    values = sorted(value / 1e6 for value in samples)
    return dict(n=len(values), mean_ms=statistics.mean(values), median_ms=statistics.median(values),
                stddev_ms=statistics.pstdev(values), min_ms=values[0], max_ms=values[-1],
                p95_ms=values[max(0, __import__('math').ceil(.95 * len(values)) - 1)])


def worker(args):
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    from guard import RuntimeGuard
    guard = RuntimeGuard(); guard.install()
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QFontDatabase, QFont, QImage, QPainter, QColor
    from PySide6.QtCore import QCoreApplication, QEvent
    from desktop import model
    from desktop import chart as drawing
    from datetime import datetime, timedelta
    from dataclasses import asdict

    app = QApplication([])
    font_id = QFontDatabase.addApplicationFont(str(ROOT / 'data/desktop/NotoSansTC.ttf'))
    if font_id < 0: raise RuntimeError('Bundled font failed to load')
    app.setFont(QFont(QFontDatabase.applicationFontFamilies(font_id)[0], 10))

    # Disable the operation itself, rather than calculate then discard aspects.
    aspect_bypasses = 0
    def no_aspects(*unused_args, **unused_kwargs):
        nonlocal aspect_bypasses
        aspect_bypasses += 1
        return []
    model.find_aspects = no_aspects
    drawing.ASPECTS = ()  # omit the aspect legend as well as all aspect lines

    args.output.mkdir(parents=True, exist_ok=True)
    rng = random.Random(20261028)
    places = [('Asia/Taipei', 120.22582, 23.0), ('Asia/Tokyo', 139.6917, 35.6895),
              ('America/New_York', -74.006, 40.7128), ('Europe/London', -.1278, 51.5074),
              ('Australia/Sydney', 151.2093, -33.8688)]
    cases = [model.BirthInput(local_iso='1979-05-17T08:30:00',longitude=120.22582,
                             latitude=23, manual_dst=True, dst_enabled=False, name='計時示例')]
    for i in range(args.samples):
        dt = datetime(1950, 1, 1) + timedelta(seconds=rng.randrange(int((datetime(2021,1,1)-datetime(1950,1,1)).total_seconds())))
        zone,lon,lat = places[i % len(places)]
        # Noon keeps these fixtures away from ambiguous/nonexistent DST hours.
        dt = dt.replace(hour=12)
        birth = model.BirthInput(local_iso=dt.isoformat(),zone=zone,longitude=lon,latitude=lat,name='計時示例')
        dst = model.resolve_local(birth)['dst'].total_seconds() / 60
        cases.append(model.BirthInput(**dict(asdict(birth),manual_dst=True,dst_enabled=bool(dst),dst_minutes=int(dst) if dst else 60)))

    before_init = perf_counter_ns()
    engine = model.ChartEngine()
    initialization_ns = perf_counter_ns() - before_init
    rows = []
    for i,birth in enumerate(cases):
        before = perf_counter_ns()
        chart = engine.calculate(birth)
        after_calculation = perf_counter_ns()
        image = QImage(1400,1000,QImage.Format.Format_ARGB32)
        image.fill(QColor('white'))
        painter = QPainter(image)
        if not painter.isActive(): raise RuntimeError('Raster painter unavailable')
        drawing.paint_chart(painter,chart)
        painter.end()
        after_drawing = perf_counter_ns()

        # This optional second path uses the application's existing PNG export:
        # render at 2800x2000, compress, then write through the OS file cache.
        png_path=args.output / ('first-no-aspects.png' if i==0 else 'last-no-aspects.png')
        drawing.export_chart(chart,png_path,size=2000)
        after_png = perf_counter_ns()
        rows.append(dict(index=i,phase='first' if i==0 else 'warm',input=asdict(birth),
            compute_ns=after_calculation-before,draw_1400x1000_ns=after_drawing-after_calculation,
            compute_and_draw_ns=after_drawing-before,
            png_2800x2000_ns=after_png-after_drawing,
            compute_and_png_ns=(after_calculation-before)+(after_png-after_drawing),
            points=len(chart['points']),cusps=len(chart['cusps']),aspects=len(chart['aspects'])))
        if len(chart['points'])!=20 or len(chart['cusps'])!=12 or chart['aspects']:
            raise AssertionError('Benchmark content did not match requested scope')
        if i==0 and args.samples:
            print('First request complete; measuring different births.',file=sys.stderr,flush=True)
        if i and i%25==0:
            print(f'{i}/{args.samples} warm samples complete.',file=sys.stderr,flush=True)
    assert aspect_bypasses==len(rows)
    assert not guard.events,guard.events
    first=rows[0]
    result=dict(version=model.APP_VERSION,initialization_ns=initialization_ns,
                bootstrap_and_fixture_ns=before_init-SCRIPT_START_NS,
                first_core_to_image_ns=initialization_ns+first['compute_and_draw_ns'],
                first_core_to_png_ns=initialization_ns+first['compute_and_png_ns'],
                raw=rows,aspect_bypasses=aspect_bypasses,guard_events=guard.events,
                python=sys.version,logical_cpus=os.cpu_count(),cpu_identifier=os.environ.get('PROCESSOR_IDENTIFIER'))
    (args.output/'timings.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
    app.processEvents()


def run(args):
    args.output.mkdir(parents=True,exist_ok=True)
    fresh=[]
    for i in range(args.fresh_runs):
        output=args.output/f'fresh-{i+1}'
        before=perf_counter_ns()
        subprocess.run([sys.executable,__file__,'--worker','--samples','0','--output',str(output)],check=True)
        elapsed=perf_counter_ns()-before
        data=json.loads((output/'timings.json').read_text(encoding='utf-8'));data['process_wall_ns']=elapsed;fresh.append(data)
        print(f'Fresh process {i+1}/{args.fresh_runs} complete.',flush=True)
    subprocess.run([sys.executable,__file__,'--worker','--samples',str(args.samples),'--output',str(args.output/'warm')],check=True)
    warm=json.loads((args.output/'warm/timings.json').read_text(encoding='utf-8'))
    rows=warm['raw'][1:]
    summary=dict(scope=dict(house_system='Placidus',small_bodies=True,total_points=20,
        aspects_computed=False,aspect_lines=False,aspect_legend=False,timezone='IANA region plus explicit DST',
        draw='QImage 1400x1000; completed CPU raster, no PNG encode or disk write',
        png='Application export_chart: render 2800x2000 + encode PNG + buffered disk write',
        fresh='Fresh Python process; OS filesystem cache is not cleared; not a packaged GUI startup latency',
        warm='100 different births; engine and ephemeris loaded; no repeated-birth result reuse'),
        warm={key:statistics_ms([r[key] for r in rows]) for key in
            ['compute_ns','draw_1400x1000_ns','compute_and_draw_ns','png_2800x2000_ns','compute_and_png_ns']},
        fresh={key:statistics_ms([d[key] for d in fresh]) for key in
            ['initialization_ns','first_core_to_image_ns','first_core_to_png_ns','process_wall_ns']},
        environment={k:warm[k] for k in ['version','python','logical_cpus','cpu_identifier']})
    (args.output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    with (args.output/'warm-raw.csv').open('w',encoding='utf-8-sig',newline='') as f:
        columns=['index','local_iso','zone','longitude','latitude','dst_enabled','dst_minutes',
            'compute_ns','draw_1400x1000_ns','compute_and_draw_ns','png_2800x2000_ns','compute_and_png_ns']
        writer=csv.DictWriter(f,fieldnames=columns);writer.writeheader()
        for row in rows:writer.writerow({k:(row[k] if k in row else row['input'][k]) for k in columns})
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--worker',action='store_true')
    parser.add_argument('--samples',type=int,default=100);parser.add_argument('--fresh-runs',type=int,default=5)
    parser.add_argument('--output',type=Path,default=ROOT/'results/desktop/benchmark-no-aspects-0.3.0')
    args=parser.parse_args()
    worker(args) if args.worker else run(args)
