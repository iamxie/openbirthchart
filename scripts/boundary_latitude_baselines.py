# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Fixed 87 boundary cases: product results, native Swiss coverage, and explicit exclusions."""
from __future__ import annotations
import argparse
from collections import Counter
import copy
from datetime import datetime,timezone
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
import complete_regression as batch
from complete_latitude_baselines import csv_write,jsonl

WORK=ROOT/'results/numerical/boundary-dual-20261101'
FORMAL=ROOT/'regression/boundary-v2'
ORIGINAL=ROOT/'regression/cases-v2.json'
OLD=ROOT/'results/numerical/azimuth-patch-20261031'
MODES={'actual':True,'zero':False}
KINDS={'chart':57,'house':6,'aspect':5,'time':19}

def utc_calendar(value):
    match=re.fullmatch(r'(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2}(?:\.\d+)?)(?:Z|\+00:00)?',value)
    if not match:raise ValueError('Expected an explicit UTC calendar string')
    return [*map(int,match.groups()[:5]),float(match.group(6))]

def reference_route(case,old):
    if case['kind']=='time':return dict(method='native_time',reason='Swiss utc_to_jd independently computes TT and UT1; product EOP metadata has no identical Swiss contract.')
    if case['kind']=='house':return dict(method='not_comparable',reason='Product longitude-interval helper with an arbitrary supplied cusp array; no identical native Swiss API accepting that array.')
    if case['kind']=='aspect':return dict(method='not_comparable',reason='Product aspect/orb inclusion helper; Swiss has no equivalent native aspect catalogue and orb-boundary contract.')
    if 'tt_jd' in old:
        return dict(method='shared_chart',time_context={k:old[k] for k in ('utc','tt_jd','ut1_jd')})
    if case['id']=='edge-utc-leap-second-input' and case['input']['zone']=='UTC':
        return dict(method='native_leap_chart',reason='Explicit UTC leap second is accepted by Swiss utc_to_jd; the product datetime input rejects it. No shared product time is available.')
    return dict(method='not_comparable',reason='No unique physical instant: ambiguous local time without fold, or nonexistent local civil time.',time_error=old['time_error'])

def validate(suite):
    if batch.sha(ORIGINAL)!=suite['sampling_source']['sha256']:raise ValueError('Original fixture changed')
    if batch.sha(OLD/'boundary-inputs.json')!=suite['time_source']['sha256']:raise ValueError('Frozen boundary times changed')
    original=batch.read(ORIGINAL);expected=[c for c in original['cases'] if c['group']=='boundary']
    cases=suite['cases'];groups=suite['groups']
    if len(cases)!=87 or len(groups)!=87 or Counter(c['kind'] for c in cases)!=KINDS:raise ValueError('Boundary coverage mismatch')
    restored=copy.deepcopy(cases)
    for c in restored:
        c.pop('group_id')
        if c['kind']=='chart':c['input'].pop('house_latitude')
    if batch.exact(restored)!=batch.exact(expected):raise ValueError('Boundary conditions/order changed')
    old={r['id']:r for r in batch.read(OLD/'boundary-inputs.json')}
    for index,(c,g) in enumerate(zip(cases,groups,strict=True),1):
        gid=f'boundary-{index:03d}'
        wanted=dict(id=gid,suite='boundary-v2',reference=reference_route(c,old[c['id']]))
        if c['group_id']!=gid or batch.exact(g)!=batch.exact(wanted):raise ValueError('Reference routing/time changed')
    return dict(cases=87,groups=87,kinds=KINDS,reference_routes=dict(Counter(g['reference']['method'] for g in groups)))

def calculate_case(engine,kind,case,group):
    route=group['reference'];context=route.get('time_context');ident=case['id'];native_time=None
    if kind=='product':
        from numerical_regression import execute_case
        if context is not None:
            from desktop.model import BirthInput,resolve_local
            resolved=resolve_local(BirthInput(**case['input']));times,_=engine.times(resolved['utc'])
            current=dict(utc=resolved['utc'].isoformat(),tt_jd=times['tt_jd'],ut1_jd=times['ut1_jd'])
            if batch.exact(context)!=batch.exact(current):raise ValueError('Frozen physical time changed: '+ident)
        row=execute_case(engine,case);met=row.pop('expected_outcome_met');row['status']=row['result']['status']
        # The frozen fixture expected datetime's generic ValueError. Recognize
        # only the explicitly approved, explanatory replacement refusal; retain
        # the old fixture and let exact comparison report the changed error.
        if (ident=='edge-utc-leap-second-input' and case['expected']=='ValueError' and
            row['status']=='UserError' and row['raw'].get('source')==
            '此時間包含閏秒（秒數為 60）。本程式目前不支援閏秒輸入，因此無法排盤。原輸入時間未變更。'):
            met=True
        row['outcome_kind']='ok' if met and row['status']=='ok' else 'expected_error' if met else 'unexpected_error'
        if row['status']=='ok' and case['kind']=='chart':
            raw=row['raw'];actual=dict(utc=raw['utc'],tt_jd=raw['times']['tt_jd'],ut1_jd=raw['times']['ut1_jd'])
            if batch.exact(actual)!=batch.exact(context):raise ValueError('Successful chart time mismatch')
    else:
        method=route['method'];status='ok';outcome='ok'
        if method=='not_comparable':
            status='not_comparable';outcome='not_comparable';raw=dict(reason=route['reason'],time_error=route.get('time_error'))
        else:
            try:
                if method in ('native_time','native_leap_chart'):
                    utc=case['utc'] if method=='native_time' else case['input']['local_iso']+'Z'
                    calendar=utc_calendar(utc);arguments=[*calendar,engine.GREG_CAL]
                    tt,ut1=engine.utc_to_jd(*arguments)
                    native_time=dict(function='swisseph.utc_to_jd',arguments=arguments,tt_jd=tt,ut1_jd=ut1)
                    if method=='native_time':raw=dict(utc=utc,calendar=calendar,tt_jd=tt,ut1_jd=ut1,function='swisseph.utc_to_jd',arguments=arguments)
                    else:context=dict(utc=utc,tt_jd=tt,ut1_jd=ut1)
                if method in ('shared_chart','native_leap_chart'):
                    from swiss_reference import calculate
                    raw=calculate(engine,dict(id=ident,input=case['input'],**context))
            except Exception as exc:
                status=type(exc).__name__;raw=dict(type=status,error=str(exc))
                domain=case['kind']=='chart' and ident.startswith('edge-polar-') and isinstance(exc,engine.Error) and str(exc).startswith('swisseph.houses_armc:')
                outcome='geometry_rejection' if domain else 'unexpected_error'
        row=dict(id=ident,status=status,raw=raw,result=batch.exact(raw),outcome_kind=outcome)
    row.update(input=case.get('input'),kind=case['kind'],time_context=context,reference_method=route['method'],reference_reason=route.get('reason'))
    if native_time is not None:row['native_time_conversion']=native_time
    return row

def prepare():
    WORK.mkdir(parents=True,exist_ok=False);(WORK/'inputs').mkdir()
    previous=batch.read(ROOT/'results/numerical/main-dual-20261031/protected-before.json')
    previous.update(batch.read(ROOT/'results/numerical/main-dual-20261031/EVIDENCE-SHA256.json')['sha256'])
    paths={ROOT/p for p in previous if not p.startswith('scripts/') and p not in ('HANDOFF.md','TODO.md','DESKTOP_README.md')}
    for folder in ('regression','desktop','requirements'):
        paths.update(p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc')
    paths.update([ROOT/'verify-numerics.ps1',ROOT/'verify-complete-numerics.ps1'])
    paths.update(OLD/name for name in ('boundary-inputs.json','boundary-swiss.json','boundary-comparisons.csv','boundary-comparisons.json','boundary-outcomes.csv','swiss_boundary.py','EVIDENCE-SHA256.json'))
    batch.write(WORK/'protected-before.json',{p.relative_to(ROOT).as_posix():batch.sha(p) for p in sorted(paths)})
    write_inputs()

def write_inputs():
    original=batch.read(ORIGINAL);old={r['id']:r for r in batch.read(OLD/'boundary-inputs.json')}
    for mode,enabled in MODES.items():
        suite=copy.deepcopy(original);suite['cases']=[c for c in suite['cases'] if c['group']=='boundary']
        suite.update(baseline_suite='boundary-v2',house_latitude_mode=mode,
            sampling_source=dict(path=ORIGINAL.relative_to(ROOT).as_posix(),sha256=batch.sha(ORIGINAL)),
            time_source=dict(path=(OLD/'boundary-inputs.json').relative_to(ROOT).as_posix(),sha256=batch.sha(OLD/'boundary-inputs.json')),
            time_policy='Charts use frozen shared TT/UT1 where a unique product civil instant exists. Explicit UTC leap-second chart uses native Swiss conversion only; 19 time helpers independently compare UTC to TT/UT1.',
            house_latitude_policy='Actual/zero latitude applies only to chart placements; all other fixed helper inputs are unchanged.')
        suite['groups']=[]
        for index,case in enumerate(suite['cases'],1):
            # Original time-helper IDs contain colons; retain IDs in records,
            # use a separate stable filename-safe checkpoint key on Windows.
            case['group_id']=f'boundary-{index:03d}'
            if case['kind']=='chart':
                if batch.exact(case['input'])!=batch.exact(old[case['id']]['input']):raise ValueError('Historical input mismatch')
                case['input']['house_latitude']=enabled
            suite['groups'].append(dict(id=case['group_id'],suite='boundary-v2',reference=reference_route(case,old[case['id']])))
        suite['benchmark_groups']=[g['id'] for g in suite['groups']]
        coverage=batch.validate_suite(suite);batch.write(WORK/'inputs'/f'{mode}.json',suite)
    batch.write(WORK/'sampling-verification.json',dict(no_resampling=True,coverage=coverage,
        source_sha256=batch.sha(ORIGINAL),frozen_time_source_sha256=batch.sha(OLD/'boundary-inputs.json'),
        cases_sha256={m:batch.sha(WORK/'inputs'/f'{m}.json') for m in MODES}))

def capture():
    pinned=batch.read(ROOT/'regression/main-v2/swiss/actual/environment.json')
    if batch.sha(pinned['executable'])!=pinned['executable_sha256']:raise ValueError('Swiss interpreter changed')
    commands={'product':[str(ROOT/'.venv-desktop/Scripts/python.exe')],'swiss':[pinned['executable'],'-I']}
    for engine in commands:
        for mode in MODES:
            for repeat in ('first','repeat'):
                print('CAPTURE',engine,mode,repeat,flush=True)
                subprocess.run([*commands[engine],str(ROOT/'scripts/complete_regression.py'),'run','--cases',str(WORK/'inputs'/f'{mode}.json'),
                    '--engine',engine,'--workers','12' if engine=='product' else '4','--output',str(WORK/'runs'/f'{engine}-{mode}-{repeat}')],cwd=ROOT,check=True)

def publish():
    from compare_boundary import compare
    import complete_latitude_baselines as shared
    FORMAL.mkdir(parents=True,exist_ok=False);(WORK/'exact').mkdir();records={};seals={};timings=[]
    for engine in ('product','swiss'):
        for mode in MODES:
            key=f'{engine}-{mode}';first=WORK/'runs'/f'{key}-first';repeat=WORK/'runs'/f'{key}-repeat';destination=FORMAL/engine/mode
            batch.seal(first,repeat,destination)
            batch.write(WORK/'exact'/f'{key}.json',batch.read(destination/'BASELINE.json')['independent_repeat'])
            records[engine,mode]=jsonl(destination/'results.jsonl.gz')
            seals[key]=dict(files=len(batch.read(destination/'SHA256SUMS.json')),verified=True)
            for label,path in (('first',first),('repeat',repeat)):
                m=batch.read(path/'manifest.json');timings.append(dict(engine=engine,mode=mode,round=label,workers=m['workers'],
                    pool_wall_seconds=m['pool_wall_seconds'],wall_seconds=m['wall_seconds'],record_elapsed_seconds_sum=m['sessions'][0]['record_elapsed_seconds_sum']))
            print('SEALED',key,flush=True)
    continuity={}
    for mode,suffix in (('actual','on'),('zero','off')):
        prior={r['id']:r for r in jsonl(ROOT/f'results/numerical/latitude-mode-20261031/final/legacy-{suffix}/results.jsonl.gz')}
        for r in records['product',mode]:
            if batch.exact(r['raw'])!=batch.exact(prior[r['id']]['raw']) or r['result']!=prior[r['id']]['result']:raise ValueError('Product continuity: '+r['id'])
        continuity[mode]=dict(cases=87,raw_and_numeric_exact=True)
    old={r['id']:r for r in batch.read(OLD/'boundary-swiss.json')['rows'] if r['status']=='ok'}
    for r in records['swiss','actual']:
        if r['id'] not in old:continue
        raw=copy.deepcopy(r['raw']);raw['input'].pop('house_latitude')
        if batch.exact(raw)!=batch.exact(batch.semantic(old[r['id']])):raise ValueError('Historical Swiss chart drift: '+r['id'])
    shared.WORK=WORK;invariants={}
    for engine in ('product','swiss'):
        a=records[engine,'actual'];z=records[engine,'zero'];helper_count=0
        for x,y in zip(a,z,strict=True):
            if x['status']!=y['status']:raise ValueError('Mode changed status')
            if x['kind']!='chart':
                if batch.exact(x['raw'])!=batch.exact(y['raw']):raise ValueError('Mode changed a non-placement helper')
                helper_count+=1
        ac=[r for r in a if r['kind']=='chart'];zc=[r for r in z if r['kind']=='chart']
        invariants[engine]=shared.mode_invariants(engine,ac,zc);invariants[engine]['unchanged_helper_records']=helper_count
    comparisons={m:compare(FORMAL/'product'/m,FORMAL/'swiss'/m,FORMAL/'comparison'/m) for m in MODES}
    protected=batch.read(WORK/'protected-before.json');changed=[p for p,h in protected.items() if not (ROOT/p).is_file() or batch.sha(ROOT/p)!=h]
    if changed:raise ValueError('Protected files changed: '+repr(changed))
    batch.write(WORK/'verification.json',dict(seals=seals,product_continuity=continuity,swiss_actual_historical_chart_continuity=len(old),
        mode_invariants=invariants,preservation=dict(files=len(protected),changed=changed),sampling=batch.read(WORK/'sampling-verification.json')))
    batch.write(WORK/'summary.json',dict(comparisons=comparisons,mode_invariants=invariants,timings=timings));csv_write(WORK/'timings.csv',timings)
    registry=dict(schema='boundary-current-v1',active_suite='boundary-v2',cases_per_dataset=87,updated_utc=datetime.now(timezone.utc).isoformat(),
        modes={m:{engine:dict(path=(FORMAL/engine/m).relative_to(ROOT).as_posix(),seal_sha256=batch.sha(FORMAL/engine/m/'SHA256SUMS.json'),cases_sha256=batch.sha(FORMAL/engine/m/'cases.json')) for engine in ('product','swiss')} for m in MODES},
        superseded=[dict(path='regression/baselines/0.6.5',scope='boundary 87 only',status='obsolete'),
            dict(path=(OLD/'boundary-swiss.json').relative_to(ROOT).as_posix(),scope='historical supplemental boundary reference',status='obsolete')],
        preserved='Historical bytes and current main-v2 1200/complete-v2 2016 baselines and routes are unchanged.',
        report='results/numerical/boundary-dual-20261101/REPORT.md')
    pointer=ROOT/'regression/boundary-current.json'
    if pointer.exists():raise FileExistsError(pointer)
    batch.write(pointer,registry);print(batch.dumps(dict(published='boundary-v2',seals=seals,mode_invariants=invariants)),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=['prepare','inputs','capture','publish'])
    args=parser.parse_args();{'prepare':prepare,'inputs':write_inputs,'capture':capture,'publish':publish}[args.command]()
