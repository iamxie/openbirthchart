# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""One-time fixture authoring; normal checks NEVER call this generator."""
import calendar
import copy
from dataclasses import asdict
from datetime import datetime, timedelta
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
from desktop.model import BirthInput, resolve_local

SYSTEMS = list('PKCREVXOBUHMTW')
ORBS = {'0':4., '90':3., '120':3., '180':3., '60':2., '30':1., '45':1., '72':1.5, '135':1.5, '150':1.5}
# GeoNames feature coordinates, read 2026-10-29; Ushuaia uses the cited rounded city point.
CITY_ROWS = [
    ('stockholm','北高','Stockholm',59.32938,18.06871,'Europe/Stockholm','2673730/stockholm'),
    ('edinburgh','北高','Edinburgh',55.95206,-3.19648,'Europe/London','2650225/edinburgh'),
    ('new_york','北中','New York',40.71427,-74.00597,'America/New_York','5128581/new-york-city'),
    ('tokyo','北中','Tokyo',35.68950,139.69171,'Asia/Tokyo','1850147/tokyo'),
    ('singapore','北低','Singapore',1.28967,103.85007,'Asia/Singapore','1880252/singapore'),
    ('bangkok','北低','Bangkok',13.75398,100.50144,'Asia/Bangkok','1609350/bangkok'),
    ('ushuaia','南高','Ushuaia',-54.8,-68.3,'America/Argentina/Ushuaia',None),
    ('punta_arenas','南高','Punta Arenas',-53.16282,-70.90922,'America/Punta_Arenas','3874787/punta-arenas'),
    ('sydney','南中','Sydney',-33.86785,151.20732,'Australia/Sydney','2147714/sydney'),
    ('cape_town','南中','Cape Town',-33.92584,18.42322,'Africa/Johannesburg','3369157/cape-town'),
    ('quito','南低','Quito',-0.22985,-78.52495,'America/Guayaquil','3652462/quito'),
    ('lima','南低','Lima',-12.04318,-77.02824,'America/Lima','3936456/lima'),
]
# Authoring preflight found 16 Azimuth rejections. Keep every original as an
# explicit rejection fixture; select the first valid whole-hour shift on the
# SAME date for the balanced chart. These decisions are frozen, not retried at runtime.
REVIEWED_TIMES = {
    'main-1936-03':'1936-03-02T11:58:10','main-1947-04':'1947-04-06T09:46:45',
    'main-1965-09':'1965-09-16T01:06:41','main-1967-07':'1967-07-31T04:15:12',
    'main-1977-10':'1977-10-02T21:31:11','main-1978-08':'1978-08-10T03:55:06',
    'main-1980-06':'1980-06-25T06:41:32','main-1981-12':'1981-12-07T05:22:13',
    'main-1982-05':'1982-05-22T07:09:09','main-1984-03':'1984-03-04T11:36:00',
    'main-1991-01':'1991-01-30T04:40:47','main-1994-10':'1994-10-22T11:38:00',
    'main-2002-03':'2002-03-19T23:07:11','main-2022-06':'2022-06-14T20:08:45',
    'main-2023-05':'2023-05-08T22:45:39','main-2023-11':'2023-11-15T21:04:37',
}

def generate():
    rng = random.Random(60019272026)
    cities = [dict(id=i,band=b,name=n,latitude=lat,longitude=lon,zone=z,
                   source=f'https://www.geonames.org/{s}.html' if s else
                   'https://en.wikipedia.org/wiki/Southernmost_settlements')
              for i,b,n,lat,lon,z,s in CITY_ROWS]
    decks = []
    for c in range(12):
        deck = SYSTEMS * 7 + [SYSTEMS[(2*c)%14], SYSTEMS[(2*c+1)%14]]
        rng.shuffle(deck)
        decks.append(deck)
    cases = []
    for y in range(100):
        for m in range(12):
            c = (m+y)%12
            city = cities[c]
            # Retry only nonexistent civil times, never numerical outcomes.
            while True:
                d = rng.randint(1, calendar.monthrange(1927+y,m+1)[1])
                h,minute,sec = rng.randrange(24),rng.randrange(60),rng.randrange(60)
                birth = BirthInput(local_iso=f'{1927+y:04}-{m+1:02}-{d:02}T{h:02}:{minute:02}:{sec:02}',
                    zone=city['zone'],latitude=city['latitude'],longitude=city['longitude'],
                    system=decks[c][y],fold=0)
                try:
                    resolve_local(birth)
                    break
                except ValueError as exc:
                    if '不存在' not in str(exc): raise
            cases.append(dict(id=f'main-{1927+y}-{m+1:02}',kind='chart',group='balanced',city=city['id'],
                              input=asdict(birth),orbs=ORBS,expected='ok'))
    rejections=[]
    for case in cases:
        if case['id'] in REVIEWED_TIMES:
            original=copy.deepcopy(case)
            original.update(id='edge-azimuth-'+case['id'],group='boundary',expected='UserError')
            rejections.append(original)
            case['input']['local_iso']=REVIEWED_TIMES[case['id']]
            case['authoring_note']='Original Azimuth rejection preserved as '+original['id']
    cases.extend(rejections)
    def edge(ident, expected='ok', **kw):
        birth = BirthInput(local_iso='2024-01-01T12:00:00',zone='UTC',latitude=23.,longitude=120.2)
        values = asdict(birth); values.update(kw)
        cases.append(dict(id='edge-'+ident,kind='chart',group='boundary',input=values,orbs=ORBS,expected=expected))
    for ident,iso in [('pre-1960','1959-12-31T23:59:59'),('start-1960','1960-01-01T00:00:00'),
                     ('pre-1972','1971-12-31T23:59:59'),('start-1972','1972-01-01T00:00:00'),
                     ('leap-day','2000-02-29T00:00:00'),('century-not-leap','1900-03-01T00:00:00'),
                     ('leap-second-before','2016-12-31T23:59:59'),('leap-second-after','2017-01-01T00:00:00'),
                     ('range-first','1850-01-02T00:00:00'),('range-last','2149-12-30T23:59:59')]:
        edge(ident,local_iso=iso)
    for ident,iso in [('range-before','1850-01-01T23:59:59'),('range-after','2149-12-31T00:00:00')]:
        edge(ident,'UserError',local_iso=iso)
    for fold in (None,0,1):
        edge('fold-'+str(fold),'AmbiguousTimeError' if fold is None else 'ok',
             local_iso='2024-11-03T01:30:00',zone='America/New_York',fold=fold,latitude=40.71427,longitude=-74.00597)
    edge('dst-gap','UserError',local_iso='2024-03-10T02:30:00',zone='America/New_York')
    edge('date-line-gap','UserError',local_iso='2011-12-30T12:00:00',zone='Pacific/Apia')
    edge('quarter-hour',zone='Asia/Kathmandu',latitude=27.7,longitude=85.3)
    edge('half-hour-dst',zone='Australia/Lord_Howe',latitude=-31.55,longitude=159.08)
    for mode, enabled, minutes in [('auto',False,60),('off',False,60),('on',True,60),('negative',True,-30),('maximum',True,180)]:
        edge('manual-'+mode,local_iso='1979-07-01T12:00:00',zone='Asia/Taipei',
             manual_dst=mode!='auto',dst_enabled=enabled,dst_minutes=minutes)
    for lat in (69.65,-69.65):
        for system in ('P','K','E','W'):
            edge(f'polar-{lat}-{system}','UserError' if system in 'PK' else 'ok',latitude=lat,longitude=18.95,system=system)
    for lon in (-180.,180.,0.): edge('longitude-'+str(lon),longitude=lon,latitude=0.,system='W')
    edge('no-minors',small_bodies=False,minor_aspects=False)
    edge('utc-leap-second-input','ValueError',local_iso='2016-12-31T23:59:60')
    # Direct helper fixtures exercise exact boundaries independently of random ephemeris dates.
    for lon in (0.,360.,359.999999,29.999999,30.,30.000001):
        cases.append(dict(id='edge-cusp-'+str(lon),kind='house',group='boundary',expected='ok',
                          longitude=lon,cusps=[float(i*30) for i in range(12)]))
    for sep in (3.999999,4.,4.000001,359.999999,360.):
        cases.append(dict(id='edge-aspect-'+str(sep),kind='aspect',group='boundary',expected='ok',
                          points=[dict(name='A',lon=0.),dict(name='B',lon=sep)],orbs=ORBS))
    for instant in ('2016-12-31T23:59:59Z','2016-12-31T23:59:60Z','2017-01-01T00:00:00Z'):
        cases.append(dict(id='edge-time-'+instant,kind='time',group='boundary',expected='ok',utc=instant))
    # Adjacent seconds found once using the 0.6.0 model, then frozen. No root
    # finding during regression, since that could conceal a moving boundary.
    for label,before,after in [
        ('mercury-station','2016-04-28T17:19:43','2016-04-28T17:19:44'),
        ('day-night','2024-03-19T22:01:23','2024-03-19T22:01:24')]:
        for side,instant in [('before',before),('after',after)]:
            edge(label+'-'+side,local_iso=instant,zone='UTC',latitude=25.03,longitude=121.56,system='W')
    for transition in ('1973-01-02T00:00:00','2027-10-04T00:00:00','2026-09-02T00:00:00','2026-10-09T00:00:00'):
        for seconds in (-86401,-86400,-1,0):
            instant=(datetime.fromisoformat(transition)+timedelta(seconds=seconds)).isoformat()+'Z'
            cases.append(dict(id=f'edge-eop-{transition}-{seconds}',kind='time',group='boundary',expected='ok',utc=instant))
    return dict(schema=1,seed=60019272026,baseline_version='0.6.0',house_systems=SYSTEMS,
                latitude_bands='Testing bands: low abs(lat)<23.5; middle 23.5<=abs(lat)<50; high 50<=abs(lat)<66.5. Not polar-circle definitions.',
                cities=cities,cases=cases)

if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as stream:
        json.dump(generate(),stream,ensure_ascii=False,indent=2,allow_nan=False)
        stream.write('\n')
