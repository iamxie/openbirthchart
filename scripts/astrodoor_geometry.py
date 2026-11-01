# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Alternative geometric-coordinate diagnostic; does not change product defaults."""
import json, sys, math
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from astrodoor_compare import OUT, save
from guard import RuntimeGuard
guard=RuntimeGuard();guard.install()
from desktop.model import ChartEngine, BODIES, MINORS
import erfa
engine=ChartEngine(); e=engine.e
for path in sorted((OUT/'local').glob('*.json')):
    chart=json.loads(path.read_text(encoding='utf-8'))
    points=[]
    for ident,name,short,color in BODIES+MINORS:
        e.set_calc_mode('leb' if ident in {b[0] for b in MINORS} else 'skyfield')
        v,rf=e.calc(chart['times']['tt_jd'],ident,e.FLG_SWIEPH|e.FLG_SPEED|e.FLG_TRUEPOS)
        points.append(dict(id=ident,name=name,lon=v[0],lat=v[1],speed=v[3],returned_flags=rf))
    utc=datetime.fromisoformat(chart['utc'])
    jd0,jdf=erfa.cal2jd(utc.year,utc.month,utc.day)
    jdf+=(utc.hour*3600+utc.minute*60+utc.second)/86400
    gast=math.degrees(erfa.gst06a(jd0,jdf,chart['times']['tt_jd'],0))%360
    e.set_calc_mode('skyfield')
    cusps,angles=e.houses_armc((gast+120.2)%360,23.,chart['times']['erfa_true_obliquity_deg'],b'P')
    save(OUT/'geometric'/path.name,dict(case_id=path.stem,mode='FLG_TRUEPOS diagnostic only',points=points,
        clock_as_ut1_cusps=list(cusps),clock_as_ut1_asc=angles[0],clock_as_ut1_mc=angles[1]))
save(OUT/'geometry-runtime.json',dict(swisseph_loaded='swisseph' in sys.modules,events=guard.events))
print('100 geometric-coordinate diagnostics complete')
