# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Compare the user-provided Tang chart, without changing product settings."""
import sys,json,math,argparse
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from guard import RuntimeGuard
guard=RuntimeGuard();guard.install()
from desktop.model import BirthInput,ChartEngine,HOUSE_SYSTEMS,zodiac_text,house_number
engine=ChartEngine();e=engine.e
# Manually transcribed from the user's attached numeric table (degrees/minutes/seconds).
observed=[(0,30,25,31,51,11),(1,270,29,27,14,7),(2,30,10,59,53,11),
 (3,0,28,47,27,10),(4,30,0,37,44,10),(5,120,2,55,18,1),
 (6,150,7,7,25,3),(7,210,18,42,9,5),(8,240,19,45,42,6),(9,180,16,51,49,4)]
parser=argparse.ArgumentParser()
parser.add_argument('--longitude',type=float,default=120+13/60)
parser.add_argument('--latitude',type=float,default=23.)
args=parser.parse_args()
birth=BirthInput(local_iso='1979-05-17T08:30:00',longitude=args.longitude,latitude=args.latitude,small_bodies=False)
chart=engine.calculate(birth); rows=[]
e.set_topo(birth.longitude,birth.latitude,0.)
for body,sign,d,m,s,house in observed:
    target=sign+d+m/60+s/3600
    entry=dict(body=body,name=chart['points'][body]['name'],target=target,website_house=house)
    for label,flags in [('apparent',0),('geometric',e.FLG_TRUEPOS),('topocentric_apparent',e.FLG_TOPOCTR)]:
        v,_=e.calc(chart['times']['tt_jd'],body,e.FLG_SWIEPH|e.FLG_SPEED|flags)
        entry[label]=dict(lon=v[0],text=zodiac_text(v[0]),delta_arcsec=((v[0]-target+180)%360-180)*3600)
    rows.append(entry)
houses=[]
for code,name in HOUSE_SYSTEMS.items():
    cusp,angles=e.houses_armc((chart['times']['erfa_gast_deg']+birth.longitude)%360,birth.latitude,chart['times']['erfa_true_obliquity_deg'],code.encode())
    placements=[house_number(r['target'],cusp) for r in rows]
    houses.append(dict(code=code,name=name,cusps=list(cusp),placements=placements,
        matches=sum(h==r['website_house'] for h,r in zip(placements,rows))))
result=dict(input=chart['input'],utc=chart['utc'],dst_minutes=chart['dst_minutes'],times=chart['times'],
    asc=chart['asc'],asc_text=zodiac_text(chart['asc']),asc_target=90+11+13/60+40/3600,
    mc=chart['mc'],mc_text=zodiac_text(chart['mc']),points=rows,house_candidates=houses,guard_events=guard.events)
(ROOT/'results/tang/comparison.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(result,ensure_ascii=False,indent=2))
