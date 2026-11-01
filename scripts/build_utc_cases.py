# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Retain prior grid where modern UTC is meaningful, and label extrapolation."""
from common import ROOT, read, dump, sha, configure_core

def main():
    configure_core()
    from guard import RuntimeGuard
    guard=RuntimeGuard(); guard.install()
    from utc_times import TimeAuthority
    authority=TimeAuthority()
    old=read(ROOT/'cases.json')
    times=[]; excluded=[]
    for epoch in old['epochs']:
        if epoch['calendar_label'][:4]<'1972':
            excluded.append(dict(epoch,reason='Modern UTC experiment starts 1972; do not invent historical UTC'))
            continue
        row=authority.convert(epoch['calendar_label'],allow_model=True)
        times.append(dict(row,id=epoch['id'],previous_epoch=epoch['id']))
    for name,iso in [('user_birth','1999-04-25T13:25:31Z'),
                     ('leap_before','2016-12-31T23:59:59Z'),('leap_second','2016-12-31T23:59:60Z'),
                     ('leap_after','2017-01-01T00:00:00Z'),('recent','2026-10-15T12:00:00Z')]:
        times.append(dict(authority.convert(iso,allow_model=False),id=name,previous_epoch=None))
    available={row['id'] for row in times}
    houses=[dict(row,id='utc_'+row['id']) for row in old['houses'] if row['epoch'] in available]
    locations=[('Tainan',22.9999,120.2269),('Greenwich',51.4779,0),('Sydney',-33.8688,151.2093),
               ('Equator',0,0),('NearPolarN',65.5,25),('NearPolarS',-65.5,-70)]
    for epoch in ('user_birth','leap_before','leap_second','leap_after','recent'):
        for name,lat,lon in locations:
            for system in ('P','K','O','E','W'):
                houses.append(dict(id=f'{epoch}:{name}:{system}',epoch=epoch,location=name,lat=lat,lon=lon,system=system))
    for row in houses: row.pop('jd',None)  # no stale UTC-as-UT1 JD can enter a worker
    result=dict(times=times,houses=houses,excluded=excluded,thresholds=old['thresholds'],
        time_manifest=authority.manifest,previous_cases_sha256=sha(ROOT/'cases.json'),
        eop_mjd_range=[authority.mjds[0],authority.mjds[-1]],
        stages={'native':'same independently derived UT1, engine default Delta T',
                'split':'explicit UTC-derived TT for planets; explicit TT-UT1 override for native house models',
                'standard':'additional diagnostic: ERFA IAU 2006/2000A angles, then houses_armc in each engine'},
        guard_events=guard.events)
    if guard.events: raise RuntimeError('Time conversion touched forbidden dependency')
    dump(ROOT/'utc-cases.json',result)
    from collections import Counter
    print('UTC time records:',len(times),'houses:',len(houses),'excluded pre-1972:',len(excluded))
    print(Counter(row['ut1_source'] for row in times))

if __name__=='__main__': main()
