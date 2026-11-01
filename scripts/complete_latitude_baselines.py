# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Author, recalculate and seal the two latitude modes of the fixed 2016 cases.

No resampling, library repair, or replacement of historical files. Each of the
four datasets requires two independent complete captures before publication.
"""
from __future__ import annotations
import argparse
from collections import Counter
import copy
import csv
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
import complete_regression as batch

WORK=ROOT/'results/numerical/complete-dual-20261031'
FORMAL=ROOT/'regression/complete-v2'
MODES={'actual':True,'zero':False}

def jsonl(path):
    with gzip.open(path,'rt',encoding='utf-8') as stream:
        return [json.loads(line) for line in stream]

def csv_write(path,rows):
    with path.open('x',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(dict.fromkeys(k for r in rows for k in r)))
        writer.writeheader();writer.writerows(rows)

def prepare():
    WORK.mkdir(parents=True,exist_ok=False)
    old=ROOT/'regression/complete-v1/cases.json'
    original=batch.read(old)
    # Hash before publication, including all old suites/seals and app sources.
    prior=batch.read(ROOT/'results/numerical/latitude-mode-20261031/protected-before.json')
    paths={ROOT/p for p in prior if not p.startswith('scripts/') and p not in ('HANDOFF.md','TODO.md','DESKTOP_README.md','verify-complete-numerics.ps1')}
    for rel in ('regression','desktop','requirements'):
        paths.update(p for p in (ROOT/rel).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc')
    batch.write(WORK/'protected-before.json',{p.relative_to(ROOT).as_posix():batch.sha(p) for p in sorted(paths)})
    (WORK/'inputs').mkdir()
    for mode,enabled in MODES.items():
        suite=copy.deepcopy(original)
        suite.update(baseline_suite='complete-v2',house_latitude_mode=mode,
            sampling_source=dict(path=old.relative_to(ROOT).as_posix(),sha256=batch.sha(old)),
            house_latitude_policy='Only house_pos input latitude changes; true coordinates and fixed conditions are retained.')
        for case in suite['cases']:case['input']['house_latitude']=enabled
        batch.validate_suite(suite)
        # Strip only the newly declared fields; everything else must be exact.
        restored=copy.deepcopy(suite)
        for key in ('baseline_suite','house_latitude_mode','sampling_source','house_latitude_policy'):restored.pop(key)
        for case in restored['cases']:case['input'].pop('house_latitude')
        if batch.exact(restored)!=batch.exact(original):raise ValueError('Sampling changed')
        batch.write(WORK/'inputs'/f'{mode}.json',suite)
    batch.write(WORK/'sampling-verification.json',dict(cases_per_mode=2016,same_physical_inputs=True,
        source_sha256=batch.sha(old),only_case_input_addition='house_latitude: true/false',
        inputs_sha256={m:batch.sha(WORK/'inputs'/f'{m}.json') for m in MODES}))

def capture():
    # Separate processes/interpreters prevent accidental sharing of ephemerides.
    pinned=batch.read(ROOT/'regression/complete-v1/swiss-2.10.03/environment.json')
    reference_python=Path(pinned['executable'])
    if batch.sha(reference_python)!=pinned['executable_sha256']:
        raise ValueError('Pinned Swiss interpreter changed')
    commands={'product':[str(ROOT/'.venv-desktop/Scripts/python.exe')],
              'swiss':[str(reference_python),'-I']}
    for engine in ('product','swiss'):
        for mode in MODES:
            for repeat in ('first','repeat'):
                output=WORK/'runs-final'/f'{engine}-{mode}-{repeat}'
                command=[*commands[engine],str(ROOT/'scripts/complete_regression.py'),'run',
                    '--cases',str(WORK/'inputs'/f'{mode}.json'),'--engine',engine,
                    '--workers','12' if engine=='product' else '4','--output',str(output)]
                print('CAPTURE',engine,mode,repeat,flush=True)
                subprocess.run(command,cwd=ROOT,check=True)

def mode_invariants(engine,actual,zero):
    changes=[];coordinate_pairs=0;axis_pairs=0
    for a,b in zip(actual,zero,strict=True):
        if a['id']!=b['id'] or a['status']!=b['status']:raise ValueError('Mode changed case/status')
        if a['status']!='ok':
            if batch.exact(a['raw'])!=batch.exact(b['raw']):raise ValueError('Mode changed error')
            continue
        x,y=a['raw'],b['raw']
        fixed=('cusps','asc','mc','utc','day_chart')
        fixed+=('times','aspects','orbs') if engine=='product' else ('tt_jd','ut1_jd','armc','obliquity','nutation','angles','returned_flags')
        for key in fixed:
            if batch.exact(x[key])!=batch.exact(y[key]):raise ValueError(f'Mode changed {key}: {a["id"]}')
        for p,q in zip(x['all_points'],y['all_points'],strict=True):
            if batch.exact({k:v for k,v in p.items() if k!='house'})!=batch.exact({k:v for k,v in q.items() if k!='house'}):
                raise ValueError('Mode changed real coordinates/point attributes')
            coordinate_pairs+=1
            if p['id'] in (-2,-3):
                axis_pairs+=1
                if p['house']!=q['house']:raise ValueError('Mode changed ASC/MC house')
            if p['house']!=q['house']:
                key=str(p['id'])
                changes.append(dict(engine=engine,case=a['id'],local_iso=a['input']['local_iso'],system=a['input']['system'],
                    point_id=p['id'],name=p.get('name',str(p['id'])),longitude=p['lon'],true_latitude=p['lat'],
                    actual_house=p['house'],zero_house=q['house'],actual_position=x['house_positions'][key]['position'],
                    zero_position=y['house_positions'][key]['position'],undefined_transition=p['house'] is None or q['house'] is None))
    csv_write(WORK/f'{engine}-mode-changes.csv',changes)
    return dict(cases=len(actual),coordinate_pairs=coordinate_pairs,axis_house_pairs=axis_pairs,
        unchanged_coordinates_and_axes=True,changed_charts=len({r['case'] for r in changes}),changed_points=len(changes),
        undefined_transitions=sum(r['undefined_transition'] for r in changes),
        by_system=dict(Counter(r['system'] for r in changes)))

def publish():
    from compare_complete import compare
    FORMAL.mkdir(parents=True,exist_ok=False)
    (WORK/'exact').mkdir()
    runs={};seals={};timings=[]
    for engine in ('product','swiss'):
        for mode in MODES:
            key=f'{engine}-{mode}';first=WORK/'runs-final'/f'{key}-first';repeat=WORK/'runs-final'/f'{key}-repeat'
            exact=batch.compare_exact(first,repeat,WORK/'exact'/f'{key}.json')
            if not exact['equal'] or not exact['environment_equal']:raise ValueError('Repeat failed: '+key)
            destination=FORMAL/engine/mode
            batch.seal(first,repeat,destination)
            seals[key]=batch.verify_seal(destination)
            m,s,rows=batch.load_run(destination);runs[engine,mode]=rows
            for round_name,path in (('first',first),('repeat',repeat)):
                manifest=batch.read(path/'manifest.json')
                timings.append(dict(engine=engine,mode=mode,round=round_name,workers=manifest['workers'],
                    pool_wall_seconds=manifest['pool_wall_seconds'],wall_seconds=manifest['wall_seconds'],
                    record_elapsed_seconds_sum=manifest['sessions'][0]['record_elapsed_seconds_sum']))
    invariants={engine:mode_invariants(engine,runs[engine,'actual'],runs[engine,'zero']) for engine in ('product','swiss')}
    # Exact product continuity against the already accepted latitude-mode QA.
    continuity={}
    for mode,suffix in (('actual','on'),('zero','off')):
        prior=jsonl(ROOT/f'results/numerical/latitude-mode-20261031/final/complete-{suffix}/results.jsonl.gz')
        current=runs['product',mode]
        if len(prior)!=2016:raise ValueError('Prior QA inventory')
        for a,b in zip(prior,current,strict=True):
            if a['id']!=b['id'] or batch.exact(a['raw'])!=batch.exact(b['raw']) or a['result']!=b['result']:
                raise ValueError('Product changed since accepted QA: '+b['id'])
        continuity[mode]=dict(cases=2016,raw_and_numeric_exact=True)
    # Actual-latitude Swiss values must remain identical to historical reference.
    _,_,prior=batch.load_run(ROOT/'regression/complete-v1/swiss-2.10.03')
    for a,b in zip(prior,runs['swiss','actual'],strict=True):
        raw=copy.deepcopy(b['raw'])
        if 'input' in raw:raw['input'].pop('house_latitude')
        if a['id']!=b['id'] or batch.exact(a['raw'])!=batch.exact(raw):raise ValueError('Swiss actual calculation drift')
    comparisons={};maxima={};mismatch_patterns={}
    for mode in MODES:
        output=FORMAL/'comparison'/mode
        comparisons[mode]=compare(FORMAL/'product'/mode,FORMAL/'swiss'/mode,output)
        rows=jsonl(output/'all-comparisons.jsonl.gz')
        differences=[r for r in rows if r.get('house_crossing')]
        csv_write(WORK/f'{mode}-house-differences.csv',differences)
        charts=[]
        for case in dict.fromkeys(r['case'] for r in differences):
            points=[r for r in differences if r['case']==case];r=points[0]
            charts.append({**{k:r[k] for k in ('case','local_iso','city_name','system','house_latitude_mode')},
                'different_points':len(points),'point_ids':','.join(str(p['point_id']) for p in points)})
        csv_write(WORK/f'{mode}-different-charts.csv',charts)
        mismatch_patterns[mode]=dict(by_system=dict(Counter(r['system'] for r in differences)),
            by_point=dict(Counter(r['name'] for r in differences)),
            axis_points=sum(r['point_id'] in (-2,-3) for r in differences),
            modulo_house_shift=dict(Counter(str((r['product_house']-r['reference_house'])%12) for r in differences)))
        maxima[mode]={}
        for label,selected in (
            ('sun_through_pluto',[r for r in rows if r['kind']=='point' and 0<=r['point_id']<=9]),
            ('direct16',[r for r in rows if r.get('scope')=='direct16']),
            ('all20',[r for r in rows if r['kind']=='point']),
            ('cusps',[r for r in rows if r['kind']=='cusp'])):
            maxima[mode][label]={field:max(selected,key=lambda r:r[field]) for field in
                ('longitude_delta_arcsec','latitude_delta_arcsec','separation_arcsec')}
    protected=batch.read(WORK/'protected-before.json')
    changed=[p for p,h in protected.items() if not (ROOT/p).is_file() or batch.sha(ROOT/p)!=h]
    if changed:raise ValueError('Protected files changed: '+repr(changed))
    verification=dict(seals=seals,mode_invariants=invariants,product_continuity=continuity,
        swiss_actual_continuity=dict(cases=2016,exact_except_added_input_flag=True),
        preservation=dict(files=len(protected),changed=changed),sampling=batch.read(WORK/'sampling-verification.json'))
    batch.write(WORK/'verification.json',verification)
    batch.write(WORK/'summary.json',dict(comparisons=comparisons,mode_invariants=invariants,
        angular_maxima=maxima,mismatch_patterns=mismatch_patterns,timings=timings))
    csv_write(WORK/'timings.csv',timings)
    registry=dict(schema='complete-current-v1',active_suite='complete-v2',cases_per_dataset=2016,
        updated_utc=datetime.now(timezone.utc).isoformat(),modes={mode:{engine:dict(
            path=(FORMAL/engine/mode).relative_to(ROOT).as_posix(),
            seal_sha256=batch.sha(FORMAL/engine/mode/'SHA256SUMS.json'),
            cases_sha256=batch.sha(FORMAL/engine/mode/'cases.json')) for engine in ('product','swiss')} for mode in MODES},
        superseded=[dict(path='regression/complete-v1/product-0.6.5',status='obsolete'),
                    dict(path='regression/complete-v1/swiss-2.10.03',status='obsolete')],
        supersession_policy='Old 2016 outputs are obsolete and retained unchanged as history. Fixed case conditions and legacy 1287 baselines remain valid.',
        report='results/numerical/complete-dual-20261031/REPORT.md')
    # The active pointer is published only after captures, comparisons and checks.
    pointer=ROOT/'regression/complete-current.json'
    if pointer.exists():raise FileExistsError(pointer)
    batch.write(pointer,registry)
    print(batch.dumps(dict(published=registry['active_suite'],verification=verification)),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['prepare','capture','publish'])
    args=parser.parse_args()
    {'prepare':prepare,'capture':capture,'publish':publish}[args.command]()
