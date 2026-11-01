# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Compare equal instants and distinguish observed time data from extrapolation."""
from collections import defaultdict,Counter
import csv
from common import ROOT,read,dump,sha,angular_delta,finite_vector
from compare import keyed,stats

def coverage(rows,expected):
    found=keyed(rows)
    if set(found)!=expected: raise ValueError('Incomplete UTC comparison coverage')
    return found

def band(time):
    if time['measured_time']: return 'observed'
    if time['ut1_source']=='model_outside_eop' or time['leap_table_assumption']: return 'model_scenario'
    return 'iers_prediction'

def main():
    cases=read(ROOT/'utc-cases.json');core=read(ROOT/'results/utc/core.json');ref=read(ROOT/'results/utc/reference.json')
    digest=sha(ROOT/'utc-cases.json')
    if any(result['cases_sha256']!=digest for result in (core,ref)): raise ValueError('Different time inputs')
    times=keyed(cases['times']); hcases=keyed(cases['houses'])
    pkeys={f'{epoch}:{stage}:{body}' for epoch in times for stage in ('native','split') for body in range(10)}
    hkeys={f'{case}:{stage}' for case in hcases for stage in ('native','split','standard')}
    cp=coverage(core['planets'],pkeys);rp=coverage(ref['planets'],pkeys)
    ch=coverage(core['houses'],hkeys);rh=coverage(ref['houses'],hkeys)
    for result in (core,ref):
        checks=coverage(result['time_checks'],set(times))
        if any(abs(row['delta_t_seconds']-times[key]['delta_t_seconds'])>1e-8 for key,row in checks.items()):
            raise ValueError('TT-UT1 override not effective')
    planets=[];houses=[]
    for key,a in cp.items():
        b=rp[key];x=finite_vector(a['values'],6);y=finite_vector(b['values'],6);t=times[a['epoch']]
        planets.append(dict(id=key,epoch=a['epoch'],utc=t['utc'],band=band(t),stage=a['stage'],body=a['body'],
            longitude_arcsec=angular_delta(x[0],y[0])*3600,latitude_arcsec=(x[1]-y[1])*3600,
            distance_au=x[2]-y[2],speed_arcsec_per_day=(x[3]-y[3])*3600))
    comparisons={'native':('native','native'),'split':('split','split'),
        'split_vs_swiss_default':('split','native'),'standard_control':('standard','standard'),
        'standard_vs_swiss_split':('standard','split'),'standard_vs_swiss_default':('standard','native')}
    for case,info in hcases.items():
        t=times[info['epoch']]
        for name,(cm,rm) in comparisons.items():
            a=ch[f'{case}:{cm}'];b=rh[f'{case}:{rm}']
            for field,length in [('cusps',12),('angles',8)]:
                x=finite_vector(a[field],length);y=finite_vector(b[field],length)
                for index,(v,w) in enumerate(zip(x,y,strict=True)):
                    houses.append(dict(id=f'{case}:{name}:{field}:{index}',case=case,epoch=info['epoch'],
                        utc=t['utc'],band=band(t),stage=name,system=info['system'],location=info['location'],
                        field=field,index=index,difference_arcsec=angular_delta(v,w)*3600))
    for filename,rows in [('planet-differences.csv',planets),('house-differences.csv',houses)]:
        with (ROOT/'results/utc'/filename).open('w',encoding='utf-8',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    statistics={};targets=cases['thresholds']
    gates={}
    for group in ('observed','iers_prediction','model_scenario','all'):
        summary={'planets':{},'houses':{}}
        for stage in ('native','split'):
            rows=[r for r in planets if r['stage']==stage and (group=='all' or r['band']==group)]
            if not rows: continue
            metrics={metric:stats([r[metric] for r in rows]) for metric in ('longitude_arcsec','latitude_arcsec','distance_au','speed_arcsec_per_day')}
            summary['planets'][stage]=metrics
            if stage=='split':
                gates[group+'_split_positions_1arcsec']=max(metrics['longitude_arcsec']['max'],metrics['latitude_arcsec']['max'])<=targets['position_arcsec']
                gates[group+'_split_distance_1e-6au']=metrics['distance_au']['max']<=targets['distance_au']
                gates[group+'_split_speed_1arcsec_day']=metrics['speed_arcsec_per_day']['max']<=targets['speed_arcsec_per_day']
        for stage in comparisons:
            rows=[r for r in houses if r['stage']==stage and (group=='all' or r['band']==group)]
            if not rows: continue
            summary['houses'][stage]=stats([r['difference_arcsec'] for r in rows])
            gates[group+'_'+stage+'_houses_1arcsec']=summary['houses'][stage]['max']<=targets['house_arcsec']
        statistics[group]=summary
    by_body={}
    for body in sorted({r['body'] for r in planets}):
        by_body[body]={stage:stats([r['longitude_arcsec'] for r in planets if r['body']==body and r['stage']==stage]) for stage in ('native','split')}
    independence=not(core['installed_swiss'] or core['loaded_swiss'] or core['unexpected_guard_events'] or cases['guard_events']) and all(core['guard_self_test'].values())
    summary=dict(statistics=statistics,gates=gates,by_body=by_body,independence_pass=independence,
        time_counts=dict(Counter(band(t) for t in times.values())),time_source_counts=dict(Counter(t['ut1_source'] for t in times.values())),
        house_counts=dict(Counter(band(times[h['epoch']]) for h in hcases.values())),
        planet_rows_each=len(cp),house_rows_each=len(ch),epochs=len(times),house_cases=len(hcases),
        max_independent_tt_check_seconds=max(abs(t['independent_skyfield_tt_difference_seconds']) for t in times.values()),
        worst_planets=sorted(planets,key=lambda r:abs(r['longitude_arcsec']),reverse=True)[:20],
        worst_split_houses=sorted([r for r in houses if r['stage']=='split'],key=lambda r:abs(r['difference_arcsec']),reverse=True)[:20],
        user_birth=dict(time=times['user_birth'],planet_rows=[r for r in planets if r['epoch']=='user_birth'],
            house_rows=[r for r in houses if r['epoch']=='user_birth' and r['location']=='Tainan']),
        elapsed_seconds=dict(core=core['elapsed_seconds'],reference=ref['elapsed_seconds']),
        thresholds=cases['thresholds'],
        caveat='Observed-data acceptance is separate from model scenarios. Standard control forces the same independent ERFA angles; it does not prove default Swiss house agreement. Kerykeion high-level factory is not yet wired to this experimental entry point.')
    dump(ROOT/'results/utc/summary.json',summary)
    for group in statistics:
        print(group, 'planet longitude', {k:v['longitude_arcsec']['max'] for k,v in statistics[group]['planets'].items()},
              'houses',{k:v['max'] for k,v in statistics[group]['houses'].items()})
    if not independence: raise RuntimeError('Independence failure')
    # Preserve the full-grid gate; scenarios cannot be renamed observed passes.
    return 0 if all(gates[f'all_split_{key}'] for key in ('positions_1arcsec','distance_1e-6au','speed_1arcsec_day','houses_1arcsec')) else 2

if __name__=='__main__':raise SystemExit(main())
