# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""One interpreter, one engine. Outputs raw values, never reads the other result."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import importlib.metadata as md
import os
import platform
import sys
import time
import traceback
from common import ROOT, BODIES, HOUSES, dump, read, sha, finite_vector, configure_core

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('engine', choices=['core', 'reference'])
    parser.add_argument('--output', required=True)
    parser.add_argument('--quick', action='store_true')
    args = parser.parse_args()
    start = time.perf_counter()
    cases = read(ROOT/'cases.json')
    manifest = read(ROOT/'data-sources.lock.json')
    # Each worker verifies ONLY its own data; core never opens reference files.
    for item in manifest['files']:
        if f'data/{args.engine}/' in item['path'] and sha(ROOT/item['path']) != item['sha256']:
            raise RuntimeError(f'Input data changed: {item["path"]}')
    result = {'engine':args.engine, 'python':sys.version, 'platform':platform.platform(),
              'started_utc':datetime.now(timezone.utc).isoformat(), 'cases_sha256':sha(ROOT/'cases.json'),
              'manifest':manifest, 'packages':{d.metadata['Name']: d.version for d in md.distributions()},
              'planet_rows':[], 'house_rows':[], 'polar_rows':[], 'chart_rows':[], 'errors':[]}
    guard = None
    if args.engine == 'core':
        result['configuration'] = configure_core()
        from guard import RuntimeGuard
        guard = RuntimeGuard()
        guard.install()
        result['guard_self_test'] = guard.self_test()
        import libephemeris as engine
        from kerykeion import AstrologicalSubjectFactory, ChartDataFactory
        from kerykeion.ephemeris_backend.backend import BACKEND_NAME
        if BACKEND_NAME != 'libephemeris': raise AssertionError(BACKEND_NAME)
        result['backend'] = BACKEND_NAME
        result['mode'] = engine.get_calc_mode()
        if result['mode'] != 'skyfield': raise AssertionError(result['mode'])
        # Both frames are system barycenters for outer planets: do not provision optional center SPKs.
        engine.set_ephe_path(str(ROOT/'data/core'))
        engine.set_ephemeris_file('de440s.bsp')
        result['planet_center_kernel'] = str(engine.state.get_planet_centers())
    else:
        import swisseph as engine
        engine.set_ephe_path(str(ROOT/'data/reference'))
        result['swiss_library_version'] = engine.version
    flags = engine.FLG_SWIEPH | engine.FLG_SPEED
    result['requested_flags'] = flags
    epochs = cases['epochs'][:3] if args.quick else cases['epochs']
    for index, epoch in enumerate(epochs):
        for scale in ('TT', 'UT1'):
            for body in range(12):
                row = {'id':f'{epoch["id"]}:{scale}:{body}', 'epoch':epoch['id'], 'jd':epoch['jd'],
                       'scale':scale, 'body':body, 'name':BODIES[body]}
                try:
                    tick = time.perf_counter()
                    values, returned = (engine.calc if scale == 'TT' else engine.calc_ut)(epoch['jd'], body, flags)
                    row.update(values=finite_vector(values,6), returned_flags=returned, seconds=time.perf_counter()-tick)
                    if args.engine == 'reference' and body < 10 and returned & 7 != engine.FLG_SWIEPH:
                        raise AssertionError(f'Swiss silently fell back: {returned}')
                except Exception as exc:
                    row['error'] = f'{type(exc).__name__}: {exc}'
                    result['errors'].append({'id':row['id'], 'error':row['error']})
                result['planet_rows'].append(row)
        if index % 50 == 0: print(f'{args.engine}: {index+1}/{len(epochs)} epochs', flush=True)
    for case in (cases['houses'][:10] if args.quick else cases['houses']):
        row = dict(case)
        try:
            tick = time.perf_counter()
            cusps, angles = engine.houses(case['jd'],case['lat'],case['lon'],case['system'].encode('ascii'))
            row.update(cusps=finite_vector(cusps,12), angles=finite_vector(angles,8), seconds=time.perf_counter()-tick)
        except Exception as exc:
            row['error'] = f'{type(exc).__name__}: {exc}'
            result['errors'].append({'id':row['id'], 'error':row['error']})
        result['house_rows'].append(row)
    for case in cases['polar']:
        row = dict(case)
        try:
            engine.houses(case['jd'],case['lat'],case['lon'],case['system'].encode('ascii'))
            row['rejected'] = False
        except Exception as exc:
            row.update(rejected=True,error=f'{type(exc).__name__}: {exc}')
        result['polar_rows'].append(row)
    if args.engine == 'core':
        for case in (cases['charts'][:2] if args.quick else cases['charts']):
            row = dict(case)
            try:
                subject = AstrologicalSubjectFactory.from_iso_utc_time(name=case['id'], iso_utc_time=case['iso'],
                    lat=case['lat'], lng=case['lon'], tz_str='Etc/UTC', online=False,
                    houses_system_identifier=case['system'], active_points=BODIES[:10],
                    calculate_lunar_phase=False, suppress_geonames_warning=True)
                data = subject.model_dump(mode='json')
                row['subject'] = data
                jd = subject.julian_day
                row['direct_planets'] = {name:finite_vector(engine.calc_ut(jd,body,flags)[0],6) for body,name in enumerate(BODIES[:10])}
                row['direct_cusps'] = list(engine.houses(jd,case['lat'],case['lon'],case['system'].encode())[0])
                chart = ChartDataFactory.create_natal_chart_data(subject)
                row['chart_data'] = chart.model_dump(mode='json')
            except Exception as exc:
                row['error'] = f'{type(exc).__name__}: {exc}'
                result['errors'].append({'id':row['id'], 'error':row['error'], 'traceback':traceback.format_exc()})
            result['chart_rows'].append(row)
        result['loaded_modules'] = sorted(sys.modules)
        result['guard_events'] = guard.events
        result['data_reads'] = [{'path':path, 'sha256':sha(path)} for path in sorted(guard.data_reads) if os.path.isfile(path)]
        result['unexpected_guard_events'] = [e for e in guard.events if e['phase']=='calculation']
        result['installed_swiss'] = [name for name in result['packages'] if 'swiss' in name.lower() or 'pysweph' in name.lower()]
        result['loaded_swiss'] = [name for name in sys.modules if name.split('.')[0] in ('swisseph','pysweph','pyswisseph')]
    else:
        for case in (cases['charts'][:2] if args.quick else cases['charts']):
            dt = datetime.fromisoformat(case['iso']).astimezone(timezone.utc)
            jd = (dt-datetime(2000,1,1,12,tzinfo=timezone.utc)).total_seconds()/86400+2451545.0
            cusps, angles = engine.houses(jd,case['lat'],case['lon'],case['system'].encode())
            result['chart_rows'].append(dict(case, jd=jd, cusps=list(cusps), angles=list(angles),
                planets={name:list(engine.calc_ut(jd,body,flags)[0]) for body,name in enumerate(BODIES[:10])}))
        result['swiss_files'] = [engine.get_current_file_data(i) for i in (0,1)]
    result['elapsed_seconds'] = time.perf_counter()-start
    result['completed_utc'] = datetime.now(timezone.utc).isoformat()
    dump(args.output,result)
    print(f'{args.engine}: complete; errors={len(result["errors"])}; {result["elapsed_seconds"]:.3f}s',flush=True)
    return bool(result['errors'] or result.get('unexpected_guard_events'))

if __name__ == '__main__': sys.exit(main())
