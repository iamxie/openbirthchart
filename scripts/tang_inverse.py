# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Fit one coordinate on May 17, then test untouched coordinates on May 16."""
import json, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
sys.stdout.reconfigure(encoding='utf-8')
from guard import RuntimeGuard
guard=RuntimeGuard();guard.install()
from desktop.model import ChartEngine, BirthInput, zodiac_text

engine=ChartEngine()
dates=['1979-05-17T08:30:00','1979-05-16T08:30:00']
targets=[90+11+13/60+40/3600,90+10+21/60+3/3600]
charts=[engine.calculate(BirthInput(local_iso=d,longitude=120+13/60,latitude=23.,small_bodies=False)) for d in dates]

def delta(a,b): return (a-b+180)%360-180

def asc(index,lon,lat):
    t=charts[index]['times']
    _,angles=engine.e.houses_armc((t['erfa_gast_deg']+lon)%360,lat,t['erfa_true_obliquity_deg'],b'P')
    return angles[0]

def bisect(fn,lo,hi):
    flo,fhi=fn(lo),fn(hi)
    if flo*fhi>0: raise ValueError('No bracketed local root')
    for _ in range(70):
        mid=(lo+hi)/2;fm=fn(mid)
        if abs(fm)<1e-12 or hi-lo<1e-12:return mid
        if flo*fm<=0: hi=mid
        else:lo=mid;flo=fm
    raise RuntimeError('No convergence')

def dms(value):
    total=round(abs(value)*3600,5)
    d=int(total//3600);m=int((total-d*3600)//60);s=total-d*3600-m*60
    return f'{d}°{m:02}′{s:08.5f}″'

for i,c in enumerate(charts):
    assert abs(delta(asc(i,c['input']['longitude'],c['input']['latitude']),c['asc']))<1e-10

fitted_lon=bisect(lambda lon:delta(asc(0,lon,23.),targets[0]),119.,121.)
fitted_lat=bisect(lambda lat:delta(asc(0,120+13/60,lat),targets[0]),22.,24.)
rows=[]
for name,lon,lat in [('website_displayed_coordinates',120+13/60,23.),('fix_latitude_solve_longitude',fitted_lon,23.),('fix_longitude_solve_latitude',120+13/60,fitted_lat)]:
    values=[]
    for i in range(2):
        value=asc(i,lon,lat)
        values.append(dict(local=dates[i],utc=charts[i]['utc'],target_deg=targets[i],target_text=zodiac_text(targets[i]),
            asc_deg=value,asc_text=zodiac_text(value),signed_arcsec=delta(value,targets[i])*3600))
    rows.append(dict(method=name,longitude=lon,latitude=lat,longitude_dms=dms(lon),latitude_dms=dms(lat),values=values))

# Fit-only numerical checks; do not tune coordinates to the validation day.
assert all(abs(r['values'][0]['signed_arcsec'])<1e-7 for r in rows[1:])
# A future screenshot at a different hour would provide a more discriminating check.
# These are predictions only, not another observed/validated chart.
prediction_date='1979-05-17T14:30:00'
predictions=[]
for row in rows[1:]:
    c=engine.calculate(BirthInput(local_iso=prediction_date,longitude=row['longitude'],latitude=row['latitude'],small_bodies=False))
    predictions.append(dict(method=row['method'],asc_deg=c['asc'],asc_text=zodiac_text(c['asc'])))
result=dict(fit_date=dates[0],validation_date=dates[1],house_system='Placidus',timezone='Asia/Taipei',
    seconds_assumed=0,coordinate_search_brackets=dict(longitude=[119,121],latitude=[22,24]),
    source='Two user-provided official numeric tables; ASC displayed to integer arcseconds',
    note='Numerical roots fit the displayed May 17 ASC exactly; not recovered official coordinates. Unknown display rounding/truncation. May 16 held out.',
    rows=rows,time_inputs=[c['times'] for c in charts],guard_events=guard.events,
    unvalidated_prediction=dict(local=prediction_date,rows=predictions,
        separation_arcsec=abs(delta(predictions[0]['asc_deg'],predictions[1]['asc_deg']))*3600))
(ROOT/'results/tang/inverse-crosscheck.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
