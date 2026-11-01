# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Recalculate and seal ONLY the fixed 1200 balanced cases in two latitude modes."""
from __future__ import annotations
import argparse
from collections import Counter
import copy
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
import complete_regression as batch
from complete_latitude_baselines import csv_write,jsonl

WORK=ROOT/'results/numerical/main-dual-20261031'
FORMAL=ROOT/'regression/main-v2'
ORIGINAL=ROOT/'regression/cases-v2.json'
OLD_REFERENCE=ROOT/'regression/references/swiss-2.10.03-0.6.3'
MODES={'actual':True,'zero':False}

def validate(suite):
    from numerical_regression import coverage
    counts=coverage(suite)
    if counts['balanced']!=1200 or counts['boundary']!=0 or len(suite['groups'])!=1200:
        raise ValueError('main-v2 must contain exactly the original 1200 main cases and no boundary cases')
    if batch.sha(ORIGINAL)!=suite['sampling_source']['sha256']:
        raise ValueError('Original fixture hash changed')
    original=batch.read(ORIGINAL)
    expected=[c for c in original['cases'] if c['group']=='balanced']
    restored=copy.deepcopy(suite['cases'])
    for case in restored:
        case['input'].pop('house_latitude');case.pop('group_id')
    if batch.exact(restored)!=batch.exact(expected):raise ValueError('Original main conditions/order changed')
    if batch.exact(suite['cities'])!=batch.exact(original['cities']):raise ValueError('Original cities changed')
    if batch.sha(OLD_REFERENCE/'inputs.jsonl.gz')!=suite['time_source']['sha256']:
        raise ValueError('Frozen time source changed')
    times=jsonl(OLD_REFERENCE/'inputs.jsonl.gz')
    if len(times)!=1200:raise ValueError('Time inventory')
    for group,case,time in zip(suite['groups'],suite['cases'],times,strict=True):
        if group['id']!=case['group_id'] or case['id']!=time['id'] or group['id']!=case['id']:
            raise ValueError('Group/case/time inventory mismatch')
        if any(batch.exact(group[k])!=batch.exact(time[k]) for k in ('utc','tt_jd','ut1_jd')):
            raise ValueError('Frozen times changed')
    return dict(counts,cases=1200,groups=1200)

def prepare():
    from compare_reference import load_reference
    load_reference(OLD_REFERENCE)
    WORK.mkdir(parents=True,exist_ok=False);(WORK/'inputs').mkdir()
    prior=batch.read(ROOT/'results/numerical/complete-dual-20261031/protected-before.json')
    paths={ROOT/p for p in prior if not p.startswith('scripts/') and p not in
        ('HANDOFF.md','TODO.md','DESKTOP_README.md','verify-numerics.ps1')}
    for rel in ('regression','desktop','requirements','results/numerical/complete-dual-20261031'):
        paths.update(p for p in (ROOT/rel).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc')
    paths.add(ROOT/'verify-complete-numerics.ps1')
    batch.write(WORK/'protected-before.json',{p.relative_to(ROOT).as_posix():batch.sha(p) for p in sorted(paths)})
    original=batch.read(ORIGINAL);times=jsonl(OLD_REFERENCE/'inputs.jsonl.gz')
    for mode,enabled in MODES.items():
        suite=copy.deepcopy(original)
        suite['cases']=[c for c in suite['cases'] if c['group']=='balanced']
        suite.update(baseline_suite='main-v2',house_latitude_mode=mode,
            sampling_source=dict(path=ORIGINAL.relative_to(ROOT).as_posix(),sha256=batch.sha(ORIGINAL)),
            time_source=dict(path=(OLD_REFERENCE/'inputs.jsonl.gz').relative_to(ROOT).as_posix(),sha256=batch.sha(OLD_REFERENCE/'inputs.jsonl.gz')),
            time_policy='Unchanged original civil conditions and shared frozen TT/UT1; product recomputes and verifies time conversion; Swiss independently calculates positions.',
            house_latitude_policy='Only placement input latitude changes; true coordinates are retained.')
        suite['groups']=[]
        for case,time in zip(suite['cases'],times,strict=True):
            if case['id']!=time['id'] or batch.exact(case['input'])!=batch.exact(time['input']) or case['orbs']!=time['orbs']:
                raise ValueError('Original product/reference conditions disagree')
            case['input']['house_latitude']=enabled;case['group_id']=case['id']
            suite['groups'].append(dict(id=case['id'],**{k:time[k] for k in ('utc','tt_jd','ut1_jd')}))
        suite['benchmark_groups']=[g['id'] for g in suite['groups'][:24]]
        batch.validate_suite(suite)
        batch.write(WORK/'inputs'/f'{mode}.json',suite)
    batch.write(WORK/'sampling-verification.json',dict(cases_per_mode=1200,no_resampling=True,
        excluded_boundary_cases=87,original_cases_sha256=batch.sha(ORIGINAL),
        frozen_time_input_sha256=batch.sha(OLD_REFERENCE/'inputs.jsonl.gz'),
        modes={m:batch.sha(WORK/'inputs'/f'{m}.json') for m in MODES}))

def capture():
    pinned=batch.read(ROOT/'regression/complete-v2/swiss/actual/environment.json')
    reference_python=Path(pinned['executable'])
    if batch.sha(reference_python)!=pinned['executable_sha256']:raise ValueError('Swiss interpreter changed')
    commands={'product':[str(ROOT/'.venv-desktop/Scripts/python.exe')],'swiss':[str(reference_python),'-I']}
    for engine in commands:
        for mode in MODES:
            for repeat in ('first','repeat'):
                print('CAPTURE',engine,mode,repeat,flush=True)
                subprocess.run([*commands[engine],str(ROOT/'scripts/complete_regression.py'),'run',
                    '--cases',str(WORK/'inputs'/f'{mode}.json'),'--engine',engine,
                    '--workers','12' if engine=='product' else '4',
                    '--output',str(WORK/'runs-final'/f'{engine}-{mode}-{repeat}')],cwd=ROOT,check=True)

def publish():
    from compare_complete import compare
    from compare_reference import load_reference
    import complete_latitude_baselines as shared
    FORMAL.mkdir(parents=True,exist_ok=False);(WORK/'exact').mkdir()
    records={};timings=[];seals={}
    for engine in ('product','swiss'):
        for mode in MODES:
            key=f'{engine}-{mode}';first=WORK/'runs-final'/f'{key}-first';repeat=WORK/'runs-final'/f'{key}-repeat'
            destination=FORMAL/engine/mode
            batch.seal(first,repeat,destination)
            baseline=batch.read(destination/'BASELINE.json')
            batch.write(WORK/'exact'/f'{key}.json',baseline['independent_repeat'])
            records[engine,mode]=jsonl(destination/'results.jsonl.gz')
            seals[key]=dict(verified=True,files=len(batch.read(destination/'SHA256SUMS.json')))
            for name,path in (('first',first),('repeat',repeat)):
                m=batch.read(path/'manifest.json')
                timings.append(dict(engine=engine,mode=mode,round=name,workers=m['workers'],
                    pool_wall_seconds=m['pool_wall_seconds'],wall_seconds=m['wall_seconds'],
                    record_elapsed_seconds_sum=m['sessions'][0]['record_elapsed_seconds_sum']))
            print('SEALED',key,flush=True)
    # Reuse the already audited invariance checker without touching its old output.
    shared.WORK=WORK
    invariants={engine:shared.mode_invariants(engine,records[engine,'actual'],records[engine,'zero']) for engine in ('product','swiss')}
    continuity={}
    for mode,suffix in (('actual','on'),('zero','off')):
        prior={r['id']:r for r in jsonl(ROOT/f'results/numerical/latitude-mode-20261031/final/legacy-{suffix}/results.jsonl.gz')}
        for row in records['product',mode]:
            old=prior[row['id']]
            if batch.exact(old['raw'])!=batch.exact(row['raw']) or old['result']!=row['result']:
                raise ValueError('Product drift from accepted mode QA: '+row['id'])
        continuity[mode]=dict(cases=1200,raw_and_numeric_exact=True)
    old_reference=load_reference(OLD_REFERENCE)
    for row in records['swiss','actual']:
        raw=copy.deepcopy(row['raw']);raw['input'].pop('house_latitude')
        # The legacy CLI stored per-case timing inside the reference record;
        # current batch captures store it outside raw. Only timing is excluded.
        if batch.exact(raw)!=batch.exact(batch.semantic(old_reference[row['id']])):raise ValueError('Swiss actual drift')
    comparisons={};maxima={};patterns={}
    for mode in MODES:
        output=FORMAL/'comparison'/mode
        comparisons[mode]=compare(FORMAL/'product'/mode,FORMAL/'swiss'/mode,output)
        rows=jsonl(output/'all-comparisons.jsonl.gz');different=[r for r in rows if r.get('house_crossing')]
        csv_write(WORK/f'{mode}-house-differences.csv',different)
        charts=[]
        for case in dict.fromkeys(r['case'] for r in different):
            points=[r for r in different if r['case']==case];r=points[0]
            charts.append({**{k:r[k] for k in ('case','local_iso','city_name','system','house_latitude_mode')},
                'different_points':len(points),'point_ids':','.join(str(p['point_id']) for p in points)})
        csv_write(WORK/f'{mode}-different-charts.csv',charts)
        patterns[mode]=dict(by_system=dict(Counter(r['system'] for r in different)),
            by_point=dict(Counter(r['name'] for r in different)),
            asc_points=sum(r['point_id']==-2 for r in different),mc_points=sum(r['point_id']==-3 for r in different),
            modulo_house_shift=dict(Counter(str((r['product_house']-r['reference_house'])%12) for r in different)))
        maxima[mode]={}
        for label,selected in (
            ('sun_through_pluto',[r for r in rows if r['kind']=='point' and 0<=r['point_id']<=9]),
            ('direct16',[r for r in rows if r.get('scope')=='direct16']),
            ('all20',[r for r in rows if r['kind']=='point']),('cusps',[r for r in rows if r['kind']=='cusp']),
            ('azimuth_cusps',[r for r in rows if r['kind']=='cusp' and r['system']=='H'])):
            maxima[mode][label]={field:max(selected,key=lambda r:r[field]) for field in
                ('longitude_delta_arcsec','latitude_delta_arcsec','separation_arcsec')}
    protected=batch.read(WORK/'protected-before.json')
    changed=[p for p,h in protected.items() if not (ROOT/p).is_file() or batch.sha(ROOT/p)!=h]
    if changed:raise ValueError('Protected files changed: '+repr(changed))
    verification=dict(seals=seals,mode_invariants=invariants,product_continuity=continuity,
        swiss_actual_continuity=dict(cases=1200,exact_except_added_input_flag_and_timing_location=True),
        preservation=dict(files=len(protected),changed=changed),sampling=batch.read(WORK/'sampling-verification.json'))
    batch.write(WORK/'verification.json',verification)
    batch.write(WORK/'summary.json',dict(comparisons=comparisons,mode_invariants=invariants,angular_maxima=maxima,
        mismatch_patterns=patterns,timings=timings));csv_write(WORK/'timings.csv',timings)
    registry=dict(schema='main-current-v1',active_suite='main-v2',cases_per_dataset=1200,
        updated_utc=datetime.now(timezone.utc).isoformat(),modes={mode:{engine:dict(
            path=(FORMAL/engine/mode).relative_to(ROOT).as_posix(),seal_sha256=batch.sha(FORMAL/engine/mode/'SHA256SUMS.json'),
            cases_sha256=batch.sha(FORMAL/engine/mode/'cases.json')) for engine in ('product','swiss')} for mode in MODES},
        superseded=[dict(path='regression/baselines/0.6.5',scope='balanced 1200 only',status='obsolete'),
                    dict(path=OLD_REFERENCE.relative_to(ROOT).as_posix(),scope='all 1200',status='obsolete')],
        preserved='All historical bytes, all 87 boundary cases, complete-v2 baselines and routing, application/library code and packages are unchanged.',
        report='results/numerical/main-dual-20261031/REPORT.md')
    pointer=ROOT/'regression/main-current.json'
    if pointer.exists():raise FileExistsError(pointer)
    batch.write(pointer,registry)
    print(batch.dumps(dict(published='main-v2',verification=verification)),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=['prepare','capture','publish'])
    args=parser.parse_args();{'prepare':prepare,'capture':capture,'publish':publish}[args.command]()
