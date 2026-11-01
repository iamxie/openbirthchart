# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Isolated Swiss reference capture; no imports or positions from the product.

Run with the pinned CPython 3.11 executable and -I. The input contains the
original birth conditions and the shared TT/UT1 time conversion only.
"""
from pathlib import Path
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.metadata
import json
import math
import platform
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
PHYSICAL = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 15, 19, 18, 20, 17)


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def calculate(swe, item):
    b = item['input']; tt = item['tt_jd']; ut = item['ut1_jd']
    house_latitude = b.get('house_latitude', True)
    if type(house_latitude) is not bool:
        raise ValueError('house_latitude must be a boolean')
    mask = swe.FLG_JPLEPH | swe.FLG_SWIEPH | swe.FLG_MOSEPH
    def calc(body, flags):
        values, returned = swe.calc(tt, body, flags | swe.FLG_SWIEPH)
        if returned & mask != swe.FLG_SWIEPH:
            raise ValueError(f'Ephemeris fallback: body={body}, flags={returned}')
        if not all(math.isfinite(x) for x in values):
            raise ValueError('Nonfinite Swiss output')
        return values, returned
    # Own obliquity, nutation and sidereal time at the shared physical instant.
    nutation, nutation_flags = swe.calc(tt, swe.ECL_NUT, swe.FLG_SWIEPH)
    eps = nutation[0]
    armc = (swe.sidtime0(ut, eps, nutation[2])*15 + b['longitude']) % 360
    cusps, angles = swe.houses_armc(armc, b['latitude'], eps, b['system'].encode('ascii'))
    if len(cusps) != 12 or not all(math.isfinite(x) for x in (*cusps, *angles)):
        raise ValueError('Invalid Swiss house geometry')
    points = []; flags = {}
    for ident in PHYSICAL:
        values, returned = calc(ident, swe.FLG_SPEED)
        flags[str(ident)] = returned
        points.append(dict(id=ident, lon=values[0], lat=values[1], speed=values[3],
                           retrograde=values[3] < 0, vector=list(values)))
    node = next(p for p in points if p['id'] == 11)
    points.append(dict(id=-11, lon=(node['lon']+180) % 360, lat=-node['lat'],
                       speed=node['speed'], retrograde=node['retrograde']))
    eq, flags['sun_equatorial'] = calc(swe.SUN, swe.FLG_EQUATORIAL)
    hour = math.radians(armc-eq[0]); phi = math.radians(b['latitude']); dec = math.radians(eq[1])
    day = math.sin(phi)*math.sin(dec)+math.cos(phi)*math.cos(dec)*math.cos(hour) >= 0
    asc, mc = angles[:2]
    sun, moon = points[0]['lon'], points[1]['lon']
    fortune = (asc+moon-sun if day else asc+sun-moon) % 360
    for ident, lon in ((-1, fortune), (-2, asc), (-3, mc)):
        points.append(dict(id=ident, lon=lon, lat=0., speed=None, retrograde=False))
    audits = {}
    for p in points:
        placement_latitude = p['lat'] if house_latitude else 0.0
        raw = float(swe.house_pos(armc, b['latitude'], eps, (p['lon'], placement_latitude), b['system'].encode('ascii')))
        valid = math.isfinite(raw) and 1 <= raw < 13
        undefined = raw == 0 and b['system'] == 'K'
        if not valid and not undefined:
            raise ValueError(f'Invalid Swiss house_pos: {raw}')
        p['house'] = math.floor(raw) if valid else None
        audits[str(p['id'])] = dict(raw_position=raw, position=raw, house=p['house'],
            status='ok' if valid else 'undefined', correction=None,
            arguments=[armc, b['latitude'], eps, p['lon'], placement_latitude, b['system']])
    return dict(id=item['id'], status='ok', input=b, utc=item['utc'],
                tt_jd=tt, ut1_jd=ut, armc=armc, obliquity=eps, nutation=list(nutation),
                nutation_flags=nutation_flags, cusps=list(cusps), angles=list(angles),
                asc=asc, mc=mc, day_chart=day, all_points=points, house_positions=audits,
                returned_flags=flags)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--ephemeris-dir', type=Path, required=True)
    parser.add_argument('--data-lock', type=Path, required=True)
    args = parser.parse_args(); out = args.output
    if not sys.flags.isolated:
        raise ValueError('Run this worker with -I in the separate reference runtime')
    sys.path.insert(0, str(ROOT/'.venv-reference/Lib/site-packages'))
    import swisseph as swe
    if swe.version != '2.10.03':
        raise ValueError('Reference engine version changed; explicitly review before creating another reference')
    setup = read(out/'input-manifest.json')
    for name, digest in setup['artifacts_sha256'].items():
        if sha(out/name) != digest: raise ValueError('Input integrity failure: '+name)
    data = read(args.data_lock)
    def environment():
        for entry in data:
            if sha(args.ephemeris_dir/entry['name']) != entry['sha256']:
                raise ValueError('Reference data integrity failure: '+entry['name'])
        return dict(swiss_version=swe.version, pyswisseph_version=importlib.metadata.version('pyswisseph'),
                    module_sha256=sha(swe.__file__), worker_sha256=sha(__file__), data=data,
                    python=sys.version, executable_sha256=sha(sys.executable), platform=platform.platform())
    before = environment()
    swe.set_ephe_path(str(args.ephemeris_dir.resolve()))
    items = [json.loads(line) for line in gzip.open(out/'inputs.jsonl.gz', 'rt', encoding='utf-8')]
    cases = read(out/'cases.json')['cases']
    if len(items) != 1200 or len({i['id'] for i in items}) != 1200:
        raise ValueError('Reference requires the fixed 1200 unique cases')
    if [(i['id'],i['input']) for i in items] != [(c['id'],c['input']) for c in cases]:
        raise ValueError('Reference input/case mismatch')
    if (out/'manifest.json').exists(): raise FileExistsError('Reference already sealed')
    errors = []; start = time.perf_counter()
    with gzip.open(out/'results.jsonl.gz', 'xt', encoding='utf-8', newline='\n') as f:
        for index, item in enumerate(items, 1):
            tick = time.perf_counter()
            try: row = calculate(swe, item)
            except Exception as exc:
                row = dict(id=item['id'], status='error', error_type=type(exc).__name__, error=str(exc))
                errors.append(row)
            row['elapsed_seconds'] = time.perf_counter()-tick
            f.write(json.dumps(row, ensure_ascii=False, allow_nan=False)+'\n'); f.flush()
            if index % 100 == 0:
                print(f'{index}/1200; {time.perf_counter()-start:.3f}s; errors={len(errors)}', flush=True)
    if before != environment(): raise ValueError('Reference environment changed during capture')
    for name, digest in setup['artifacts_sha256'].items():
        if sha(out/name) != digest: raise ValueError('Inputs changed during capture')
    write(out/'environment.json', before)
    (out/'worker-source.py').write_bytes(Path(__file__).read_bytes())
    write(out/'manifest.json', dict(schema=1, complete=not errors, charts=len(items), errors=errors,
        created_utc=datetime.now(timezone.utc).isoformat(), elapsed_seconds=time.perf_counter()-start,
        policy='Independent Swiss coordinates, geometry and actual-latitude house_pos. Common TT/UT1 only. No longitude-interval assignment or latitude-zero variant.',
        artifacts_sha256={p.name:sha(p) for p in out.iterdir() if p.is_file()}))
    if errors: return 1
    print('Swiss reference captured and sealed.', flush=True)
    return 0


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
