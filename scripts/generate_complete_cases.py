# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Author complete-v1 once from a pinned GeoNames extract; never used by regression runs."""
import argparse
import calendar
from collections import Counter
from dataclasses import asdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
import platform
import random
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]
SEED = 20261031
RANGES = [(1900,1910),(1911,1920),(1930,1939),(1940,1949),(1950,1959),(1960,1969),
          (1970,1979),(1980,1989),(2000,2000),(2001,2009),(2010,2019),(2027,2029)]
# Deliberately small, explicit inhabited-city candidate pools, not a claim of
# uniform sampling over all cities on Earth. GeoNames IDs avoid ambiguous names.
POOLS = {
    'north_high': [3133895,3413829,638936,643492],
    'north_mid': [5128581,1850147,2988507,3169070],
    'north_low': [1880252,1609350,1701668,1668341],
    'south_argentina': [3833367,3838854],
    'south_newzealand': [2189529,2191562],
    'south_mid': [2147714,3369157,2158177,3435910],
    'south_low': [3652462,3936456,2073124,3390760],
}
SYSTEMS = list('PKCREVXOBUHMTW')
ORBS = {'0':4.,'90':3.,'120':3.,'180':3.,'60':2.,'30':1.,'45':1.,'72':1.5,'135':1.5,'150':1.5}

def sha(path):
    with Path(path).open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()

def validate(suite):
    years=suite['years']; cities=suite['cities']; groups=suite['groups']; cases=suite['cases']
    assert len(years)==len(set(years))==12 and len(cities)==12
    assert all(a<=y<=b for y,(a,b) in zip(years,RANGES,strict=True))
    assert any(calendar.isleap(y) and y!=2000 for y in years)
    assert set(suite['house_systems'])==set(SYSTEMS)
    assert len(groups)==144 and len(cases)==2016 and len({c['id'] for c in cases})==2016
    assert len({g['id'] for g in groups})==144
    bycity={c['id']:c for c in cities}
    assert len(bycity)==12
    assert Counter(c['band'] for c in cities)==dict.fromkeys(
        ['north_high','north_mid','north_low','south_high','south_mid','south_low'],2)
    assert {c['country'] for c in cities if c['band']=='south_high'}=={'AR','NZ'}
    for c in cities:
        lat=c['latitude']; band=c['band']
        assert (lat>0)==band.startswith('north')
        if band=='north_high': assert lat>=60
        elif band.endswith('_mid'): assert 30<=abs(lat)<60
        elif band.endswith('_low'): assert abs(lat)<30
        else: assert c['country'] in ('AR','NZ') and lat < -45
    assert Counter((g['year'],g['city']) for g in groups)=={
        (y,c):1 for y in years for c in bycity}
    assert Counter((g['month'],g['city']) for g in groups)=={
        (m,c):1 for m in range(1,13) for c in bycity}
    assert Counter((g['year'],g['month']) for g in groups)=={
        (y,m):1 for y in years for m in range(1,13)}
    bygroup={g['id']:[] for g in groups}
    for c in cases: bygroup[c['group_id']].append(c)
    for g in groups:
        dt=datetime.fromisoformat(g['local_iso'])
        assert (dt.year,dt.month)==(g['year'],g['month'])
        if calendar.isleap(dt.year) and dt.month==2: assert dt.day==29
        assert {c['input']['system'] for c in bygroup[g['id']]}==set(SYSTEMS)
        assert len(bygroup[g['id']])==14
        for c in bygroup[g['id']]:
            assert c['city']==g['city'] and c['input']['local_iso']==g['local_iso']
            assert c['orbs']==ORBS
            assert c['input']['fold']==0 and not c['input']['manual_dst']
            assert all(c['input'][k]==bycity[g['city']][k] for k in ('latitude','longitude','zone'))
    return dict(cases=len(cases),groups=len(groups),cities=12,years=years,
                leap_years=[y for y in years if calendar.isleap(y)],
                cases_per_city=168,cases_per_system=144,cases_per_month_city=14)

def generate(source):
    platform.platform();platform.machine()
    from guard import RuntimeGuard
    guard=RuntimeGuard();guard.install()
    from desktop.model import BirthInput,ChartEngine,resolve_local
    rng=random.Random(SEED)
    attempts=[]
    while True:
        years=[rng.randint(a,b) for a,b in RANGES];attempts.append(years)
        if any(calendar.isleap(y) and y!=2000 for y in years):break
    with zipfile.ZipFile(source) as z:
        records={int(r[0]):r for r in (line.split('\t') for line in z.read('cities15000.txt').decode().splitlines())}
    cities=[];candidates={}
    for pool,ids in POOLS.items():
        candidates[pool]=[records[i] for i in ids]
        for ident in rng.sample(ids,1 if pool in ('south_argentina','south_newzealand') else 2):
            r=records[ident]
            cities.append(dict(id='geonames-'+r[0],geonames_id=ident,name=r[1],ascii_name=r[2],
                latitude=float(r[4]),longitude=float(r[5]),zone=r[17],country=r[8],
                band='south_high' if pool in ('south_argentina','south_newzealand') else pool,
                selection_pool=pool,source=f'https://www.geonames.org/{ident}/',source_row=r))
    rng.shuffle(cities)
    engine=ChartEngine();groups=[];cases=[];retries=[]
    for yi,year in enumerate(years):
        for month in range(1,13):
            city=cities[(month-1+5*yi)%12]
            day=29 if month==2 and calendar.isleap(year) else rng.randint(1,calendar.monthrange(year,month)[1])
            while True:
                hour,minute,second=rng.randrange(24),rng.randrange(60),rng.randrange(60)
                iso=f'{year:04}-{month:02}-{day:02}T{hour:02}:{minute:02}:{second:02}'
                b=BirthInput(local_iso=iso,zone=city['zone'],latitude=city['latitude'],longitude=city['longitude'],fold=0)
                try: resolved=resolve_local(b);break
                except ValueError as exc:
                    if '不存在' not in str(exc):raise
                    retries.append(dict(local_iso=iso,city=city['id'],reason=str(exc)))
            times,notes=engine.times(resolved['utc'])
            gid=f'complete-{year}-{month:02}'
            groups.append(dict(id=gid,year=year,month=month,city=city['id'],local_iso=iso,
                utc=resolved['utc'].isoformat(),tt_jd=times['tt_jd'],ut1_jd=times['ut1_jd'],
                time_details=times,time_notes=notes,fold=0))
            for system in SYSTEMS:
                values=asdict(b);values['system']=system
                cases.append(dict(id=gid+'-'+system,group_id=gid,kind='chart',group='complete',city=city['id'],
                    input=values,orbs=ORBS,expected='capture'))
    suite=dict(schema='complete-cases-v1',seed=SEED,created_local_date='2026-10-31',
        year_ranges=RANGES,year_draws=attempts,years=years,rotation_step=5,
        latitude_policy='north high >=60; mid 30<=abs(lat)<60; low abs(lat)<30; south high is a relative southern-city category, one AR and one NZ city, not >=60.',
        time_policy='Local civil time; fold=0; redraw only nonexistent time on the same selected day. Shared product TT/UT1, not independent civil-time validation.',
        source=dict(url='https://download.geonames.org/export/dump/cities15000.zip',sha256=sha(source),
            license='GeoNames CC BY 4.0',retrieved_local_date='2026-10-31'),
        candidate_pools=POOLS,candidate_source_rows=candidates,cities=cities,house_systems=SYSTEMS,
        groups=groups,cases=cases,nonexistent_time_redraws=retries,
        benchmark_groups=[g['id'] for g in groups if g['year'] in (years[0],years[-1])],
        authoring_guard_events=guard.events)
    suite['coverage']=validate(suite)
    return suite

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();s=generate(a.source);a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x',encoding='utf-8') as f:json.dump(s,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps(s['coverage'],ensure_ascii=False))
