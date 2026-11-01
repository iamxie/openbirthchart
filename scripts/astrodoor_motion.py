# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Station-sign diagnostics: instantaneous vs previous-day geometric motion."""
import json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from astrodoor_compare import OUT, save
from guard import RuntimeGuard
guard=RuntimeGuard();guard.install()
from desktop.model import ChartEngine, BODIES, MINORS
engine=ChartEngine();e=engine.e;rows=[]
for path in sorted((OUT/'local').glob('*.json')):
    chart=json.loads(path.read_text(encoding='utf-8'))
    geo=json.loads((OUT/'geometric'/path.name).read_text(encoding='utf-8'))
    for point in geo['points']:
        ident=point['id']
        if ident==11:continue
        e.set_calc_mode('leb' if ident in {b[0] for b in MINORS} else 'skyfield')
        old,rf=e.calc(chart['times']['tt_jd']-1,ident,e.FLG_SWIEPH|e.FLG_TRUEPOS)
        daily=((point['lon']-old[0]+180)%360-180)
        rows.append(dict(case_id=path.stem,name=point['name'],instantaneous_speed_deg_day=point['speed'],
                         preceding_day_displacement_deg=daily))
    if path.stem=='061':
        e.set_calc_mode('skyfield');t=chart['times']['tt_jd'];h=1/24
        a=e.calc(t-h,9,e.FLG_SWIEPH)[0][0];b=e.calc(t+h,9,e.FLG_SWIEPH)[0][0]
        save(OUT/'station-finite-difference.json',dict(case_id='061',step_days=h,lon_before=a,lon_after=b,
             speed_deg_day=((b-a+180)%360-180)/(2*h)))
save(OUT/'motion-diagnostics.json',dict(rows=rows,guard_events=guard.events))
print('100 local motion diagnostics complete')
