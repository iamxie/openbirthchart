# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Offline reference diagnostics only; never imported by the desktop."""
import json, sys, math
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from astrodoor_compare import OUT, MAJOR, save
import swisseph as swe
swe.set_ephe_path(str(ROOT/'data/reference'))
variants={'apparent':0,'no_aberration':swe.FLG_NOABERR,'true_position':swe.FLG_TRUEPOS,
          'no_nutation':swe.FLG_NONUT,'astrometric':swe.FLG_NOABERR|swe.FLG_NOGDEFL}
rows=[]; house_rows=[]
for path in sorted((OUT/'parsed').glob('*.json')):
    site=json.loads(path.read_text(encoding='utf-8'))
    own=json.loads((OUT/'local'/path.name).read_text(encoding='utf-8'))
    utc=datetime.fromisoformat(own['utc'])
    clock_jd=swe.julday(utc.year,utc.month,utc.day,utc.hour+utc.minute/60+utc.second/3600)
    for label,jd in [('shared_ut1',own['times']['ut1_jd']),('utc_clock_as_ut1',clock_jd)]:
        cusps,_=swe.houses(jd,23.,120.2,b'P')
        for n,lon in enumerate(cusps,1):
            website=site['cusps'][str(n)]['lon']
            d=((lon-website+180)%360-180)*3600
            house_rows.append(dict(case_id=path.stem,cusp=n,mode=label,lon=lon,signed_arcsec=d,
                interval_excess=max(-d,d-60,0),floor_match=abs(math.floor(lon*60)/60-website)<1e-8))
    for ident,name in enumerate(MAJOR):
        original=next(p for p in own['points'] if p['name']==name)['lon']
        for mode,extra in variants.items():
            v,rf=swe.calc(own['times']['tt_jd'],ident,swe.FLG_SWIEPH|swe.FLG_SPEED|extra)
            assert rf&7 == swe.FLG_SWIEPH
            delta=((v[0]-site['points'][name]['lon']+180)%360-180)*3600
            rows.append(dict(case_id=path.stem,name=name,mode=mode,lon=v[0],
                speed_deg_day=v[3],
                signed_arcsec=delta,interval_excess=max(-delta,delta-60,0),
                local_vs_reference_arcsec=((original-v[0]+180)%360-180)*3600,
                floor_match=abs(math.floor(v[0]*60)/60-site['points'][name]['lon'])<1e-8))
summary={m:dict(n=len([r for r in rows if r['mode']==m]),
    floor_matches=sum(r['floor_match'] for r in rows if r['mode']==m),
    max_interval_excess=max(r['interval_excess'] for r in rows if r['mode']==m)) for m in variants}
house_summary={m:dict(n=len([r for r in house_rows if r['mode']==m]),
    floor_matches=sum(r['floor_match'] for r in house_rows if r['mode']==m),
    max_interval_excess=max(r['interval_excess'] for r in house_rows if r['mode']==m)) for m in ['shared_ut1','utc_clock_as_ut1']}
save(OUT/'reference-diagnostics.json',dict(swiss_version=swe.version,summary=summary,rows=rows,house_summary=house_summary,house_rows=house_rows))
print(json.dumps(summary,indent=2))
print(json.dumps(house_summary,indent=2))

# Reproduce the station-boundary finding without another website request.
if (OUT/'local/061.json').exists():
    chart=json.loads((OUT/'local/061.json').read_text(encoding='utf-8'))
    station=[]
    for offset in [-1,-.5,0,.5,1]:
        record={'offset_days':offset}
        for mode,extra in [('apparent',0),('geometric',swe.FLG_TRUEPOS)]:
            v,rf=swe.calc(chart['times']['tt_jd']+offset,9,swe.FLG_SWIEPH|swe.FLG_SPEED|extra)
            record[mode]=dict(lon=v[0],speed_deg_day=v[3],speed_arcsec_day=v[3]*3600,flags=rf)
        station.append(record)
    save(OUT/'station-diagnostic.json',dict(case_id='061',tt_jd=chart['times']['tt_jd'],swiss_version=swe.version,rows=station))
