# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Resumable process-isolated complete-v1 capture. Does not modify legacy baselines."""
from __future__ import annotations
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.abc
import importlib.metadata
import json
import multiprocessing
import os
from pathlib import Path
import platform
import shutil
import statistics
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
DATA=ROOT/'results/numerical/swiss-audit-1200-20261030/reference-data'
DATA_LOCK=DATA.parent/'reference-data.json'
SOURCES=['scripts/complete_regression.py','scripts/complete_latitude_baselines.py','scripts/main_latitude_baselines.py','scripts/boundary_latitude_baselines.py','scripts/compare_boundary.py','scripts/generate_complete_cases.py','scripts/compare_complete.py',
         'scripts/numerical_regression.py','scripts/swiss_reference.py','scripts/compare_reference.py','scripts/guard.py']
THREAD_ENV=('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS')

def dumps(v):return json.dumps(v,ensure_ascii=False,allow_nan=False,sort_keys=True,separators=(',',':'))
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def digest(v):
    # JSON converts integer dictionary keys to strings. Normalize before sorting
    # so a checkpoint hashes identically before and after persistence; preserve
    # exact floating values (including signed zero) rather than rounding them.
    return hashlib.sha256(dumps(exact(v)).encode()).hexdigest()
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,allow_nan=False,indent=2)+'\n',encoding='utf-8')
def exact(v):
    if isinstance(v,float):
        import math
        if not math.isfinite(v):raise ValueError('Nonfinite value')
        return {'$float':v.hex()}
    if isinstance(v,dict):return {str(k):exact(x) for k,x in v.items()}
    if isinstance(v,(tuple,list)):return [exact(x) for x in v]
    return v
def set_threads():
    for key in THREAD_ENV:os.environ[key]='1'

class ReferenceGuard(importlib.abc.MetaPathFinder):
    """Independent reference worker: no product engine, network, or child process."""
    def __init__(self):self.events=[];self.data_reads=set()
    def block(self,kind,value):
        self.events.append(dict(kind=kind,detail=str(value)))
        raise RuntimeError('Reference guard: '+kind+': '+str(value))
    def find_spec(self,fullname,path=None,target=None):
        if fullname.split('.')[0] in ('desktop','libephemeris','skyfield','jplephem','utc_times'):
            self.block('product_import',fullname)
    def audit(self,event,args):
        if event in ('socket.connect','socket.connect_ex','socket.getaddrinfo','socket.sendto','subprocess.Popen','os.system'):
            self.block('network_or_subprocess',event)
        if event=='open' and isinstance(args[0],(str,bytes,os.PathLike)):
            p=os.fsdecode(args[0]).replace('\\','/').lower()
            if '/desktop/' in p or '/vendor/libephemeris/' in p or '/data/desktop/' in p or p.endswith(('.bsp','.leb2')):
                self.block('product_file',p)
            if p.endswith('.se1'):self.data_reads.add(p)
    def install(self):sys.meta_path.insert(0,self);sys.addaudithook(self.audit)

_engine=None;_kind=None;_guard=None;_init_seconds=None;_time_cache={}

def initialize(kind):
    global _engine,_kind,_guard,_init_seconds
    start=time.perf_counter();set_threads();platform.platform();platform.machine();_kind=kind
    if kind=='product':
        from guard import RuntimeGuard
        _guard=RuntimeGuard();_guard.install()
        from desktop.model import ChartEngine
        _engine=ChartEngine()
    else:
        if not sys.flags.isolated:raise ValueError('Swiss requires the separate Python runtime with -I')
        _guard=ReferenceGuard();_guard.install()
        sys.path.insert(0,str(ROOT/'.venv-reference/Lib/site-packages'))
        import swisseph as swe
        if swe.version!='2.10.03':raise ValueError('Swiss version changed')
        swe.set_ephe_path(str(DATA.resolve()));_engine=swe
    _init_seconds=time.perf_counter()-start

def calculate_group(task):
    group,cases=task;start=time.perf_counter();rows=[]
    if group.get('suite')=='boundary-v2':
        from boundary_latitude_baselines import calculate_case
        for case in cases:
            tick=time.perf_counter();row=calculate_case(_engine,_kind,case,group)
            row['elapsed_seconds']=time.perf_counter()-tick;rows.append(row)
        return dict(group_id=group['id'],records=rows,elapsed_seconds=time.perf_counter()-start,
            pid=os.getpid(),initialization_seconds=_init_seconds,guard_events=list(_guard.events),data_reads=sorted(_guard.data_reads))
    if _kind=='product':
        from desktop.model import BirthInput,resolve_local
        from numerical_regression import execute_case
        birth=BirthInput(**cases[0]['input']);resolved=resolve_local(birth);times,_=_engine.times(resolved['utc'])
        actual=dict(utc=resolved['utc'].isoformat(),tt_jd=times['tt_jd'],ut1_jd=times['ut1_jd'])
        frozen={k:group[k] for k in actual}
        if exact(actual)!=exact(frozen):raise ValueError('Frozen time conversion changed: '+group['id'])
    else:
        from swiss_reference import calculate
        actual={k:group[k] for k in ('utc','tt_jd','ut1_jd')}
    for case in cases:
        tick=time.perf_counter()
        if _kind=='product':
            row=execute_case(_engine,case);row.pop('expected_outcome_met')
            row['status']=row['result']['status']
            if row['status']=='ok':
                c=row['raw']
                if c['utc']!=actual['utc'] or any(c['times'][k]!=actual[k] for k in ('tt_jd','ut1_jd')):
                    raise ValueError('Chart time mismatch')
            source=row['raw'].get('source','') if row['status']!='ok' else ''
            domain=(row['status']=='UserError' and source in (
                '此緯度無法使用 {system}，請改選 Equal 或 Whole Sign。',
                '此地點的分宮計算出現警示；請改選 Equal 或 Whole Sign。',
                '此時間／地點的 Polich–Page 宮頭順序交錯或重疊，無法形成連續、不重疊的十二宮，因此停止排盤。請改選其他宮位制（例如 Equal 或 Whole Sign）後重新排盤。',
                '此時間／地點的 Polich–Page 宮位制因幾何多解、折返或退化，無法取得唯一且連續的歸宮結果，因此停止整張排盤。即使只有個別天體無法唯一歸宮，也不輸出星盤。請改選其他宮位制後重新排盤。',
                'Polich–Page 個別點的原始求解值與已驗證的宮位邊界不一致，或精度不足以判定邊界哪一側，因此無法確認歸宮結果，停止整張排盤。請改選其他宮位制後重新排盤。',
                '此時間／地點的宮位無法形成有效十二宮，請改選 Equal 或 Whole Sign。'))
        else:
            item=dict(id=case['id'],input=case['input'],**actual)
            try:
                raw=calculate(_engine,item);status='ok';domain=False
            except Exception as exc:
                status=type(exc).__name__;raw=dict(type=status,error=str(exc))
                domain=isinstance(exc,_engine.Error) and str(exc).startswith('swisseph.houses_armc:')
            row=dict(id=case['id'],status=status,raw=raw,result=exact(raw))
        row.update(input=case['input'],time_context=actual,
                   outcome_kind='ok' if row['status']=='ok' else 'geometry_rejection' if domain else 'unexpected_error',
                   elapsed_seconds=time.perf_counter()-tick)
        rows.append(row)
    return dict(group_id=group['id'],records=rows,elapsed_seconds=time.perf_counter()-start,
        pid=os.getpid(),initialization_seconds=_init_seconds,guard_events=list(_guard.events),
        data_reads=sorted(_guard.data_reads))

def environment(kind):
    set_threads();platform.platform();platform.machine()
    if kind=='product':
        from numerical_regression import provenance
        result=provenance()
    else:
        if not sys.flags.isolated:raise ValueError('Swiss requires -I')
        sys.path.insert(0,str(ROOT/'.venv-reference/Lib/site-packages'))
        import swisseph as swe
        if swe.version!='2.10.03':raise ValueError('Swiss version changed')
        data=read(DATA_LOCK)
        for item in data:
            if sha(DATA/item['name'])!=item['sha256']:raise ValueError('Swiss data integrity: '+item['name'])
        result=dict(swiss_version=swe.version,pyswisseph_version=importlib.metadata.version('pyswisseph'),
            module_sha256=sha(swe.__file__),data=data,data_lock_sha256=sha(DATA_LOCK),
            reference_lock_sha256=sha(ROOT/'requirements/reference.lock'))
    result.update(engine=kind,python=sys.version,executable=str(Path(sys.executable).resolve()),
        executable_sha256=sha(sys.executable),platform=platform.platform(),
        tool_sources={p:sha(ROOT/p) for p in SOURCES},thread_environment={k:os.environ[k] for k in THREAD_ENV})
    return result

def validate_suite(suite):
    if suite.get('baseline_suite')=='boundary-v2':
        from boundary_latitude_baselines import validate
    elif suite.get('baseline_suite')=='main-v2':
        from main_latitude_baselines import validate
    else:
        from generate_complete_cases import validate
    house_latitude_mode(suite)
    return validate(suite)

def house_latitude_mode(suite):
    flags=[c['input'].get('house_latitude',True) for c in suite['cases'] if c.get('kind','chart')=='chart']
    if not flags or any(type(flag) is not bool for flag in flags) or len(set(flags))!=1:
        raise ValueError('A complete suite must use one explicit boolean latitude mode')
    mode='actual' if flags[0] else 'zero'
    if suite.get('house_latitude_mode',mode)!=mode:
        raise ValueError('Latitude mode metadata disagrees with case inputs')
    if suite.get('baseline_suite') in ('complete-v2','main-v2','boundary-v2') and any('house_latitude' not in c['input'] for c in suite['cases'] if c.get('kind','chart')=='chart'):
        raise ValueError('Dual-mode suites require an explicit latitude flag in every case')
    return mode

def checkpoint(path,payload,fingerprint):
    wrapper=dict(fingerprint=fingerprint,payload_sha256=digest(payload),payload=payload)
    temp=path.with_suffix('.tmp')
    write(temp,wrapper)
    # Never replace a previously committed checkpoint.
    if path.exists():raise FileExistsError(path)
    temp.rename(path)

def read_checkpoint(path,fingerprint,ids):
    c=read(path)
    if c['fingerprint']!=fingerprint or c['payload_sha256']!=digest(c['payload']):raise ValueError('Checkpoint integrity: '+str(path))
    p=c['payload']
    if [r['id'] for r in p['records']]!=ids:raise ValueError('Checkpoint case inventory: '+str(path))
    return p

def run(cases_path,output,kind,workers,subset='full',resume=False):
    start=time.perf_counter();output=Path(output);suite_bytes=Path(cases_path).read_bytes()
    suite=json.loads(suite_bytes);coverage=validate_suite(suite)
    groups=suite['groups'] if subset=='full' else [g for g in suite['groups'] if g['id'] in suite['benchmark_groups']]
    groupids={g['id'] for g in groups};cases=[c for c in suite['cases'] if c['group_id'] in groupids]
    bygroup={g['id']:[c for c in cases if c['group_id']==g['id']] for g in groups}
    before=environment(kind)
    identity=dict(schema='complete-run-v1',suite_sha256=hashlib.sha256(suite_bytes).hexdigest(),
                  subset=subset,case_ids=[c['id'] for c in cases],environment=before)
    fingerprint=digest(identity)
    if resume:
        if not output.is_dir() or (output/'manifest.json').exists():raise ValueError('Resume requires an incomplete run')
        if read(output/'identity.json')!=identity:raise ValueError('Resume environment/input mismatch')
        if (output/'cases.json').read_bytes()!=suite_bytes:raise ValueError('Resume suite mismatch')
    else:
        output.mkdir(parents=True,exist_ok=False);(output/'checkpoints').mkdir();(output/'source').mkdir()
        (output/'cases.json').write_bytes(suite_bytes);write(output/'identity.json',identity);write(output/'environment.json',before)
        for rel in dict.fromkeys([*SOURCES,*before.get('core_sources',{})]):
            target=output/'source'/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/rel,target)
    lock=output/'RUNNING.lock'
    with lock.open('x',encoding='utf-8') as f:f.write(str(os.getpid()))
    session=dict(started_utc=datetime.now(timezone.utc).isoformat(),workers=workers,resumed=resume,complete=False)
    batches={};pending=[]
    try:
        existing={p.stem for p in (output/'checkpoints').glob('*.json')}
        if existing-groupids:raise ValueError('Unexpected checkpoint groups')
        for g in groups:
            path=output/'checkpoints'/(g['id']+'.json')
            if path.exists():batches[g['id']]=read_checkpoint(path,fingerprint,[c['id'] for c in bygroup[g['id']]])
            else:pending.append((g,bygroup[g['id']]))
        session['reused_groups']=len(batches);session['computed_groups']=len(pending)
        pool_start=time.perf_counter()
        if pending:
            with ProcessPoolExecutor(max_workers=workers,mp_context=multiprocessing.get_context('spawn'),
                                     initializer=initialize,initargs=(kind,)) as pool:
                futures={pool.submit(calculate_group,task):task[0]['id'] for task in pending}
                for future in as_completed(futures):
                    gid=futures[future];payload=future.result()
                    if payload['group_id']!=gid:raise ValueError('Worker ID mismatch')
                    checkpoint(output/'checkpoints'/(gid+'.json'),payload,fingerprint);batches[gid]=payload
                    if len(batches)%12==0 or len(batches)==len(groups):
                        print(f'{kind} workers={workers}: {len(batches)}/{len(groups)} groups; {time.perf_counter()-pool_start:.6f}s',flush=True)
        session['pool_wall_seconds']=time.perf_counter()-pool_start
        records=[r for g in groups for r in batches[g['id']]['records']]
        if [r['id'] for r in records]!=[c['id'] for c in cases]:raise ValueError('Output case order/inventory mismatch')
        for c,r in zip(cases,records,strict=True):
            if c.get('input')!=r['input']:raise ValueError('Output input mismatch')
        # All source, dependency, input and data checks occur again before completion.
        after=environment(kind)
        if after!=before or Path(cases_path).read_bytes()!=suite_bytes:raise ValueError('Environment changed during run')
        for rel,h in {**before['tool_sources'],**before.get('core_sources',{})}.items():
            if sha(output/'source'/rel)!=h:raise ValueError('Source snapshot mismatch')
        with gzip.open(output/'results.jsonl.gz','wt',encoding='utf-8',newline='\n') as f:
            for r in records:f.write(dumps(r)+'\n')
        session['complete']=True;session['wall_seconds']=time.perf_counter()-start
        session['record_elapsed_seconds_sum']=sum(r['elapsed_seconds'] for r in records)
        session['worker_initialization_seconds']={str(v['pid']):v['initialization_seconds'] for v in batches.values()}
        write(output/f'session-{time.time_ns()}.json',session)
        all_sessions=[read(p) for p in sorted(output.glob('session-*.json'))]
        events=[e for b in batches.values() for e in b['guard_events']]
        manifest=dict(schema='complete-run-v1',complete=True,engine=kind,subset=subset,workers=workers,
            baseline_suite=suite.get('baseline_suite','complete-v1'),house_latitude_mode=house_latitude_mode(suite),
            cases=len(records),groups=len(groups),coverage=coverage,fingerprint=fingerprint,
            outcomes=dict(Counter(r['outcome_kind'] for r in records)),statuses=dict(Counter(r['status'] for r in records)),
            unexpected_errors=[r['id'] for r in records if r['outcome_kind']=='unexpected_error'],
            guard_events=events,data_reads=sorted({p for b in batches.values() for p in b['data_reads']}),
            numerical_and_raw_sha256=digest([exact(semantic(r)) for r in records]),
            pool_wall_seconds=session['pool_wall_seconds'],wall_seconds=session['wall_seconds'],sessions=all_sessions)
        manifest['artifacts_sha256']={p.relative_to(output).as_posix():sha(p) for p in output.rglob('*')
            if p.is_file() and p.name!='RUNNING.lock' and p.suffix!='.tmp'}
        write(output/'manifest.json',manifest)
        print(dumps({k:manifest[k] for k in ('engine','cases','workers','pool_wall_seconds','wall_seconds','outcomes','statuses','unexpected_errors')}),flush=True)
        return manifest
    finally:
        if not session['complete']:
            session['wall_seconds']=time.perf_counter()-start
            write(output/f'session-{time.time_ns()}.json',session)
        lock.unlink()

def semantic(row):return {k:v for k,v in row.items() if k!='elapsed_seconds'}

def load_run(folder):
    folder=Path(folder);m=read(folder/'manifest.json')
    if m.get('schema')!='complete-run-v1' or not m['complete']:raise ValueError('Incomplete run')
    inventory={p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file() and p.name not in ('manifest.json','SHA256SUMS.json','BASELINE.json')}
    if inventory!=set(m['artifacts_sha256']):raise ValueError('Run artifact inventory mismatch')
    for rel,h in m['artifacts_sha256'].items():
        if sha(folder/rel)!=h:raise ValueError('Run artifact changed: '+rel)
    rows=[json.loads(s) for s in gzip.open(folder/'results.jsonl.gz','rt',encoding='utf-8')]
    identity=read(folder/'identity.json')
    if len(rows)!=m['cases'] or [r['id'] for r in rows]!=identity['case_ids']:raise ValueError('Run case inventory mismatch')
    if len({r['id'] for r in rows})!=len(rows):raise ValueError('Duplicate result IDs')
    if digest([exact(semantic(r)) for r in rows])!=m['numerical_and_raw_sha256']:raise ValueError('Result digest mismatch')
    return m,read(folder/'cases.json'),rows

def compare_exact(first,second,output=None):
    ma,sa,a=load_run(first);mb,sb,b=load_run(second)
    if ma['engine']!=mb['engine'] or sa!=sb or [r['id'] for r in a]!=[r['id'] for r in b]:raise ValueError('Comparison inputs differ')
    differences=[]
    def walk(x,y,path):
        if type(x)!=type(y):differences.append(dict(path=path,first=x,second=y));return
        if isinstance(x,dict):
            for k in sorted(x.keys()|y.keys()):
                if k not in x or k not in y:differences.append(dict(path=path+'/'+k,first=x.get(k),second=y.get(k)))
                else:walk(x[k],y[k],path+'/'+k)
        elif isinstance(x,list):
            if len(x)!=len(y):differences.append(dict(path=path,first_length=len(x),second_length=len(y)))
            else:
                for i,(u,v) in enumerate(zip(x,y)):walk(u,v,path+'/'+str(i))
        elif x!=y:differences.append(dict(path=path,first=x,second=y))
    for x,y in zip(a,b,strict=True):walk(exact(semantic(x)),exact(semantic(y)),x['id'])
    env_a=read(Path(first)/'environment.json');env_b=read(Path(second)/'environment.json')
    report=dict(first=str(first),second=str(second),cases=len(a),equal=not differences,
        differences=differences,environment_equal=env_a==env_b,
        first_manifest_sha256=sha(Path(first)/'manifest.json'),second_manifest_sha256=sha(Path(second)/'manifest.json'))
    if output:
        output=Path(output)
        if output.exists():raise FileExistsError(output)
        write(output,report)
    return report

def benchmark(cases,output,kind):
    output=Path(output);output.mkdir(parents=True,exist_ok=False);runs=[];first=None
    # Two rounds, reversed order, reduce warm-cache/order bias. Same inputs always.
    for roundno,order in enumerate(((1,4,8,12),(12,8,4,1)),1):
        for workers in order:
            path=output/f'round-{roundno}-workers-{workers}'
            m=run(cases,path,kind,workers,'benchmark')
            if m['unexpected_errors'] or m['guard_events']:raise ValueError('Benchmark has unexpected errors')
            if first is None:first=path
            c=compare_exact(first,path,output/f'exact-round-{roundno}-workers-{workers}.json')
            if not c['equal'] or not c['environment_equal']:raise ValueError('Parallel numerical/raw/environment mismatch')
            runs.append(dict(round=roundno,workers=workers,pool_wall_seconds=m['pool_wall_seconds'],wall_seconds=m['wall_seconds'],
                record_elapsed_seconds_sum=m['sessions'][-1]['record_elapsed_seconds_sum'],cases=m['cases'],exact_equal=True))
            write(output/'progress.json',runs)
    medians={str(w):statistics.median(r['pool_wall_seconds'] for r in runs if r['workers']==w) for w in (1,4,8,12)}
    best=int(min(medians,key=medians.get))
    summary=dict(engine=kind,runs=runs,median_pool_wall_seconds=medians,selected_workers=best,
        all_exact_equal=True,selection_rule='Minimum median end-to-end pool wall time of two rounds, including startup and checkpoint writes.',
        speedup={w:medians['1']/v for w,v in medians.items()})
    write(output/'summary.json',summary);print(dumps(summary),flush=True)
    return summary

def seal(source,repeat,destination):
    source=Path(source);destination=Path(destination)
    m,s,rows=load_run(source);mr,_,_=load_run(repeat)
    c=compare_exact(source,repeat)
    if not c['equal'] or not c['environment_equal']:raise ValueError('Independent repeat differs')
    required_cases=validate_suite(s)['cases']
    for x in (m,mr):
        if x['subset']!='full' or x['cases']!=required_cases or x['unexpected_errors'] or x['guard_events']:raise ValueError('Unsealable run')
    if destination.exists():raise FileExistsError(destination)
    shutil.copytree(source,destination)
    prefix='87 邊界例' if s.get('baseline_suite')=='boundary-v2' else '1200 例' if s.get('baseline_suite')=='main-v2' else '完全'
    write(destination/'BASELINE.json',dict(name=prefix+('基準資料' if m['engine']=='product' else '基準對照資料'),
        engine=m['engine'],suite=s.get('baseline_suite','complete-v1'),house_latitude_mode=house_latitude_mode(s),
        product_version='0.6.5',reference_version='2.10.03' if m['engine']=='swiss' else None,
        product_description='LibEphemeris based with application fixes; exact source and policy captured' if m['engine']=='product' else None,
        created_utc=datetime.now(timezone.utc).isoformat(),independent_repeat=c,
        interpretation='Fixed observed product/reference behavior, including geometry rejections and undefined positions; not a claim of correctness.'))
    write(destination/'SHA256SUMS.json',{p.relative_to(destination).as_posix():sha(p) for p in destination.rglob('*') if p.is_file()})
    verify_seal(destination)

def verify_seal(folder):
    folder=Path(folder);index=read(folder/'SHA256SUMS.json')
    actual={p.relative_to(folder).as_posix():sha(p) for p in folder.rglob('*') if p.is_file() and p.name!='SHA256SUMS.json'}
    if index!=actual:raise ValueError('Sealed inventory/hash mismatch')
    load_run(folder)
    return dict(files=len(index),verified=True)

def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='command',required=True)
    for name in ('run','benchmark'):
        q=s.add_parser(name);q.add_argument('--cases',type=Path,required=True);q.add_argument('--output',type=Path,required=True)
        q.add_argument('--engine',choices=['product','swiss'],required=True)
        if name=='run':
            q.add_argument('--workers',type=int,choices=range(1,13),required=True);q.add_argument('--subset',choices=['full','benchmark'],default='full');q.add_argument('--resume',action='store_true')
    q=s.add_parser('exact');q.add_argument('--first',type=Path,required=True);q.add_argument('--second',type=Path,required=True);q.add_argument('--output',type=Path,required=True)
    q=s.add_parser('seal');q.add_argument('--source',type=Path,required=True);q.add_argument('--repeat',type=Path,required=True);q.add_argument('--destination',type=Path,required=True)
    q=s.add_parser('verify');q.add_argument('folder',type=Path)
    a=p.parse_args();set_threads()
    if a.command=='run':
        m=run(a.cases,a.output,a.engine,a.workers,a.subset,a.resume)
        return 2 if m['unexpected_errors'] or m['guard_events'] else 0
    if a.command=='benchmark':benchmark(a.cases,a.output,a.engine);return 0
    if a.command=='exact':
        c=compare_exact(a.first,a.second,a.output);print(dumps({k:v for k,v in c.items() if k!='differences'}));return 0 if c['equal'] else 1
    if a.command=='seal':seal(a.source,a.repeat,a.destination);return 0
    if a.command=='verify':print(dumps(verify_seal(a.folder)));return 0

if __name__=='__main__':raise SystemExit(main())
