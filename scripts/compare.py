# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Strict keyed comparison: missing, duplicated or non-finite results never pass."""
from __future__ import annotations
from collections import defaultdict
import csv
import math
import statistics
from common import ROOT, BODIES, HOUSES, read, dump, sha, angular_delta, finite_vector

def keyed(rows):
    found={r['id']:r for r in rows}
    if len(found) != len(rows): raise ValueError('Duplicate result IDs')
    return found

def stats(values):
    values=sorted(abs(x) for x in values)
    if not values or not all(math.isfinite(x) for x in values): raise ValueError('Invalid statistics input')
    return {'n':len(values),'max':values[-1],'p95':values[math.ceil(.95*len(values))-1],
            'median':statistics.median(values)}

def main():
    core=read(ROOT/'results/core.json'); ref=read(ROOT/'results/reference.json'); cases=read(ROOT/'cases.json')
    if core['cases_sha256'] != ref['cases_sha256'] or core['cases_sha256'] != sha(ROOT/'cases.json'):
        raise ValueError('Cases differ')
    thresholds=cases['thresholds']
    expected_planet={f'{e["id"]}:{scale}:{body}' for e in cases['epochs'] for scale in ('TT','UT1') for body in range(12)}
    cp=keyed(core['planet_rows']); rp=keyed(ref['planet_rows'])
    if set(cp)!=expected_planet or set(rp)!=expected_planet: raise ValueError('Incomplete planetary coverage')
    rows=[]; grouped=defaultdict(lambda:defaultdict(list)); failures=[]; disagreements=[]
    for key in sorted(cp):
        a,b=cp[key],rp[key]
        if 'error' in a or 'error' in b:
            failures.append({'id':key,'core':a.get('error'),'reference':b.get('error')}); continue
        x,y=finite_vector(a['values'],6),finite_vector(b['values'],6)
        row={'id':key,'scale':a['scale'],'body':a['name'],'jd':a['jd'],
             'longitude_arcsec':angular_delta(x[0],y[0])*3600,'latitude_arcsec':(x[1]-y[1])*3600,
             'distance_au':x[2]-y[2], 'speed_arcsec_per_day':(x[3]-y[3])*3600,
             'core_longitude':x[0],'reference_longitude':y[0],
             'core_speed':x[3],'reference_speed':y[3]}
        for metric in ('longitude_arcsec','latitude_arcsec','distance_au','speed_arcsec_per_day'):
            if not math.isfinite(row[metric]): raise ValueError(f'Nonfinite result: {key}')
            grouped[f'{a["scale"]}/{a["name"]}'][metric].append(row[metric])
        if (x[3]<0)!=(y[3]<0): disagreements.append({'id':key,'kind':'retrograde'})
        if int(x[0]//30)!=int(y[0]//30): disagreements.append({'id':key,'kind':'sign'})
        rows.append(row)
    with (ROOT/'results/planet-differences.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    summaries={name:{metric:stats(values) for metric,values in metrics.items()} for name,metrics in grouped.items()}
    house_rows=[]; house_groups=defaultdict(list)
    ch=keyed(core['house_rows']); rh=keyed(ref['house_rows'])
    expected_houses={h['id'] for h in cases['houses']}
    if set(ch)!=expected_houses or set(rh)!=expected_houses: raise ValueError('Incomplete house coverage')
    for key in sorted(ch):
        a,b=ch[key],rh[key]
        if 'error' in a or 'error' in b:
            failures.append({'id':key,'core':a.get('error'),'reference':b.get('error')}); continue
        for field in ('cusps','angles'):
            for row in (a,b): finite_vector(row[field],12 if field=='cusps' else 8)
            for i,(x,y) in enumerate(zip(a[field],b[field],strict=True)):
                delta=angular_delta(x,y)*3600
                row={'id':key,'system':a['system'],'location':a['location'],'field':field,'index':i,
                     'core':x,'reference':y,'difference_arcsec':delta}
                house_rows.append(row)
                house_groups[f'{a["system"]}/{field}'].append(delta)
    with (ROOT/'results/house-differences.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(house_rows[0])); writer.writeheader(); writer.writerows(house_rows)
    integration=[]; chart_reference=[]; cc=keyed(core['chart_rows']); rc=keyed(ref['chart_rows'])
    if set(cc)!={c['id'] for c in cases['charts']} or set(rc)!=set(cc): raise ValueError('Incomplete chart coverage')
    source_labels=set()
    for key,a in cc.items():
        if 'error' in a:
            failures.append({'id':key,'core':a['error']}); continue
        b=rc[key]; subject=a['subject']
        if abs(subject['julian_day']-b['jd'])>1e-8: failures.append({'id':key,'error':'UTC to JD mismatch'})
        for name in BODIES[:10]:
            point=subject[name.lower()]
            if point is None: failures.append({'id':key,'missing':name}); continue
            source_labels.add(point.get('source'))
            integration.append(angular_delta(point['abs_pos'],a['direct_planets'][name][0])*3600)
            chart_reference.append(angular_delta(point['abs_pos'],b['planets'][name][0])*3600)
        for i,name in enumerate(HOUSES):
            integration.append(angular_delta(subject[name]['abs_pos'],a['direct_cusps'][i])*3600)
    # Primary gate covers ten physical bodies at a common TT instant. UT1 is a separate end-to-end gate.
    gates={}
    for scale in ('TT','UT1'):
        relevant=[r for r in rows if r['scale']==scale and r['body'] in BODIES[:10]]
        gates[scale+'_positions_1arcsec']=all(max(abs(r['longitude_arcsec']),abs(r['latitude_arcsec']))<=thresholds['position_arcsec'] for r in relevant)
        gates[scale+'_speed_1arcsec_per_day']=all(abs(r['speed_arcsec_per_day'])<=thresholds['speed_arcsec_per_day'] for r in relevant)
        gates[scale+'_distance_1e-6au']=all(abs(r['distance_au'])<=thresholds['distance_au'] for r in relevant)
    gates['houses_1arcsec']=all(abs(r['difference_arcsec'])<=thresholds['house_arcsec'] for r in house_rows)
    gates['kerykeion_integration']=max(map(abs,integration))<=thresholds['integration_arcsec']
    for result in (core,ref):
        if set(keyed(result['polar_rows']))!={r['id'] for r in cases['polar']}: raise ValueError('Incomplete polar coverage')
    gates['polar_rejected']=all(row['rejected'] for row in core['polar_rows']+ref['polar_rows'])
    gates['offline_no_swiss']=not (core['installed_swiss'] or core['loaded_swiss'] or core['unexpected_guard_events']) and all(core['guard_self_test'].values())
    gates['no_execution_errors']=not (failures or core['errors'] or ref['errors'])
    summary={'gates':gates,'thresholds':thresholds,'planetary_statistics':summaries,
        'house_statistics':{k:stats(v) for k,v in house_groups.items()},'integration_arcsec':stats(integration),
        'chart_vs_swiss_longitude_arcsec':stats(chart_reference),'chart_sources':sorted(source_labels),
        'errors':failures,'categorical_disagreements':disagreements,
        'worst_planet_rows':sorted(rows,key=lambda r:abs(r['longitude_arcsec']),reverse=True)[:30],
        'worst_house_rows':sorted(house_rows,key=lambda r:abs(r['difference_arcsec']),reverse=True)[:15],
        'counts':{'epochs':len(cases['epochs']),'planet_rows_each':len(cp),'house_cases_each':len(ch),'charts':len(cc)},
        'wall_seconds':{'core':core['elapsed_seconds'],'reference':ref['elapsed_seconds']},
        'caveat':'Agreement with Swiss is not absolute accuracy. TT removes Delta-T differences; underlying DE440 vs DE441 and models can differ. Nodes exploratory.'}
    dump(ROOT/'results/summary.json',summary)
    print(summary['gates'])
    print('max house arcsec',max(abs(r['difference_arcsec']) for r in house_rows))
    print('max physical TT longitude arcsec',max(abs(r['longitude_arcsec']) for r in rows if r['scale']=='TT' and r['body'] in BODIES[:10]))
    return 0 if all(gates.values()) else 2

if __name__ == '__main__': raise SystemExit(main())
